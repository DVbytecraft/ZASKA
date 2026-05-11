import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.redis_client import redis_async

logger = logging.getLogger(__name__)

# Hard caps prevent a single misbehaving client or DDoS from exhausting memory.
# At ~1KB per WS state entry, 10k entries ≈ 10MB — well within limits.
_MAX_CHAT_CONNECTIONS_PER_TASK = 50
_MAX_CALL_NOTIFICATION_CONNECTIONS = 10_000


# ── Chat WebSocket manager ─────────────────────────────────────────────────────

class TaskChatWebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def start(self) -> None:
        asyncio.create_task(self._redis_subscriber())

    async def stop(self) -> None:
        return

    async def connect(self, task_id: str, websocket: WebSocket) -> bool:
        """Accept connection. Returns False if room is at capacity."""
        room = self.connections[task_id]
        if len(room) >= _MAX_CHAT_CONNECTIONS_PER_TASK:
            return False
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()
        room.add(websocket)
        return True

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        self.connections[task_id].discard(websocket)
        if not self.connections[task_id]:
            self.connections.pop(task_id, None)

    async def publish(self, task_id: str, payload: dict) -> None:
        """Publish a chat message via Redis for cross-instance fan-out.

        Falls back to local broadcast if Redis is unavailable.
        """
        raw = json.dumps(payload)
        redis_ok = False
        try:
            await redis_async.publish(f"task-chat:{task_id}", raw)
            redis_ok = True
        except Exception as exc:
            logger.warning("chat_ws: Redis publish failed for task %s — %s", task_id, exc)

        if not redis_ok:
            await self._broadcast_local(task_id, raw)

    async def _broadcast_local(self, task_id: str, raw: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.connections.get(task_id, set())):
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(task_id, ws)

    async def _redis_subscriber(self) -> None:
        while True:
            try:
                pubsub = redis_async.pubsub()
                await pubsub.psubscribe("task-chat:*")
                logger.info("chat_ws: Redis pubsub subscriber started")
                async for message in pubsub.listen():
                    if message.get("type") not in ("pmessage", "message"):
                        continue
                    channel: str = message.get("channel", "")
                    raw: str = message.get("data", "")
                    if not raw or not channel:
                        continue
                    task_id = channel.split(":", 1)[1] if ":" in channel else channel
                    await self._broadcast_local(task_id, raw)
            except Exception as exc:
                logger.error("chat_ws: Redis subscriber crashed — %s. Restarting in 5s.", exc)
                await asyncio.sleep(5)


chat_ws_manager = TaskChatWebSocketManager()


async def websocket_loop(task_id: str, websocket: WebSocket, user_id: str) -> None:
    accepted = await chat_ws_manager.connect(task_id, websocket)
    if not accepted:
        await websocket.close(code=1008, reason="Room full")
        return
    try:
        while True:
            text = await websocket.receive_text()

            stripped = text.strip()
            if stripped in ("ping", '{"type":"ping"}'):
                try:
                    await websocket.send_text('{"type":"pong"}')
                except Exception:
                    pass
                continue

            try:
                data = json.loads(text)
                msg_text: str = data.get("message", "").strip()
            except (json.JSONDecodeError, AttributeError):
                msg_text = text.strip()

            if not msg_text:
                continue

            try:
                from app.db.session import SessionLocal
                from app.services.chat_service import ChatService
                db = SessionLocal()
                try:
                    svc = ChatService(db)
                    svc.assert_participant(task_id, user_id)
                    msg = svc.create_message(task_id, user_id, msg_text)
                    payload = {
                        "id": msg.id,
                        "taskId": msg.task_id,
                        "senderId": msg.sender_id,
                        "message": msg.message,
                        "mediaUrl": None,
                        "mediaType": None,
                        "createdAt": msg.created_at.isoformat(),
                    }
                    await chat_ws_manager.publish(task_id, payload)
                except Exception as exc:
                    logger.warning("chat_ws: persist failed task=%s — %s", task_id, exc)
                finally:
                    db.close()
            except Exception as exc:
                logger.error("chat_ws: unexpected error task=%s — %s", task_id, exc)

    except WebSocketDisconnect:
        chat_ws_manager.disconnect(task_id, websocket)


# ── Call signaling WebSocket manager ──────────────────────────────────────────
# Relays WebRTC signals (offer/answer/ice/hangup) between the two call participants.
# At most 2 connections per call_id (caller + callee).
#
# MULTI-INSTANCE DESIGN:
# In a multi-replica deployment, caller and callee may land on different pods.
# Local relay works when both are on the same pod.  When the peer is on a different
# pod, relay() publishes to Redis channel "signaling:relay:{call_id}".  Each pod
# runs a _relay_subscriber() that receives the Redis message and delivers it to
# any local connections for that call.  This closes the gap where ICE candidates
# sent after the initial SDP exchange would silently drop on cross-pod connections.
#
# The SDP queue (signaling:queue:{call_id}) remains as a fallback for the case
# where the callee hasn't connected yet when the offer arrives.

class CallSignalingManager:
    def __init__(self) -> None:
        # call_id → list of at most 2 (WebSocket, user_id) pairs
        self.rooms: dict[str, list[tuple[WebSocket, str]]] = defaultdict(list)

    @staticmethod
    def _queue_key(call_id: str) -> str:
        return f"signaling:queue:{call_id}"

    @staticmethod
    def _relay_channel(call_id: str) -> str:
        return f"signaling:relay:{call_id}"

    async def start(self) -> None:
        """Start cross-instance relay subscriber (called on app startup)."""
        asyncio.create_task(self._relay_subscriber())

    async def _relay_subscriber(self) -> None:
        """Receive signals published by other API instances and deliver locally.

        When relay() on another pod can't find the peer locally, it publishes
        to "signaling:relay:{call_id}".  This subscriber picks it up and delivers
        to any WS connections for that call on THIS instance.
        """
        while True:
            try:
                pubsub = redis_async.pubsub()
                await pubsub.psubscribe("signaling:relay:*")
                logger.info("call_signaling: cross-instance relay subscriber started")
                async for message in pubsub.listen():
                    if message.get("type") not in ("pmessage", "message"):
                        continue
                    channel: str = message.get("channel", "")
                    raw: str = message.get("data", "")
                    if not channel or not raw:
                        continue
                    call_id = channel[len("signaling:relay:"):]
                    try:
                        envelope = json.loads(raw)
                        from_user: str | None = envelope.get("_from_user")
                        payload: str = envelope.get("_payload", raw)
                    except (json.JSONDecodeError, AttributeError):
                        payload = raw
                        from_user = None

                    # Deliver to every local connection EXCEPT the sender
                    for ws, uid in list(self.rooms.get(call_id, [])):
                        if uid != from_user:
                            try:
                                await ws.send_text(
                                    payload if isinstance(payload, str) else json.dumps(payload)
                                )
                            except Exception:
                                self.disconnect(call_id, ws)
            except Exception as exc:
                logger.error(
                    "call_signaling: relay subscriber crashed — %s. Restarting in 5s.", exc
                )
                await asyncio.sleep(5)

    async def connect(self, call_id: str, ws: WebSocket, user_id: str) -> bool:
        """Accept connection. Returns False if the room is already full."""
        room = self.rooms[call_id]
        if len(room) >= 2:
            return False
        if any(uid == user_id for _, uid in room):
            return False
        if ws.client_state == WebSocketState.CONNECTING:
            await ws.accept()
        room.append((ws, user_id))
        return True

    def disconnect(self, call_id: str, ws: WebSocket) -> None:
        room = self.rooms.get(call_id, [])
        self.rooms[call_id] = [(w, u) for w, u in room if w is not ws]
        if not self.rooms[call_id]:
            self.rooms.pop(call_id, None)

    async def relay(self, call_id: str, sender: WebSocket, raw: str) -> None:
        """Forward a signal from sender to the other participant.

        Delivery order:
          1. Local delivery to the peer on THIS instance (zero latency).
          2. If no local peer found, publish to Redis relay channel so a peer
             on ANOTHER instance can receive it (cross-instance relay).
          3. For SDP signals (offer/answer/ice), also maintain the Redis queue
             as a fallback for peers that haven't connected yet (drain on join).
        """
        # Look up sender's user_id so the Redis relay envelope can exclude echo
        room = self.rooms.get(call_id, [])
        sender_user_id = next((uid for ws, uid in room if ws is sender), None)

        delivered = False
        for ws, _ in list(room):
            if ws is not sender:
                try:
                    await ws.send_text(raw)
                    delivered = True
                except Exception:
                    self.disconnect(call_id, ws)

        if not delivered:
            # Peer is not connected locally — publish for cross-instance delivery.
            try:
                envelope = json.dumps({"_from_user": sender_user_id, "_payload": raw})
                await redis_async.publish(self._relay_channel(call_id), envelope)
            except Exception as exc:
                logger.warning("call_signaling: cross-instance relay failed call=%s — %s", call_id, exc)

            # Also queue SDP signals for late-joining peers (drain_signal_queue reads this)
            try:
                msg = json.loads(raw)
                if msg.get("type") in ("offer", "answer", "ice"):
                    key = self._queue_key(call_id)
                    await redis_async.rpush(key, raw)
                    await redis_async.expire(key, 60)
            except Exception:
                pass

    async def drain_signal_queue(self, call_id: str, ws: WebSocket) -> None:
        """Deliver any Redis-queued signals to a newly connected participant.

        Called immediately after a peer connects so they receive the SDP offer
        (or ICE candidates) that were published before they joined the room.
        """
        try:
            key = self._queue_key(call_id)
            while True:
                raw = await redis_async.lpop(key)
                if raw is None:
                    break
                data = raw if isinstance(raw, str) else raw.decode()
                await ws.send_text(data)
        except Exception as exc:
            logger.warning("call_signaling: drain_signal_queue failed call=%s — %s", call_id, exc)

    async def broadcast_hangup(self, call_id: str, exclude: WebSocket | None = None) -> None:
        """Notify all remaining participants that the call ended."""
        msg = json.dumps({"type": "hangup"})
        for ws, _ in list(self.rooms.get(call_id, [])):
            if ws is not exclude:
                try:
                    await ws.send_text(msg)
                except Exception:
                    pass
        try:
            await redis_async.delete(self._queue_key(call_id))
        except Exception:
            pass
        self.rooms.pop(call_id, None)


call_signaling_manager = CallSignalingManager()


async def call_signaling_loop(call_id: str, websocket: WebSocket) -> None:
    try:
        while True:
            raw = await websocket.receive_text()

            stripped = raw.strip()
            if stripped in ("ping", '{"type":"ping"}'):
                try:
                    await websocket.send_text('{"type":"pong"}')
                except Exception:
                    pass
                continue

            await call_signaling_manager.relay(call_id, websocket, raw)
    except WebSocketDisconnect:
        call_signaling_manager.disconnect(call_id, websocket)
        await call_signaling_manager.broadcast_hangup(call_id)


# ── User call notification WebSocket manager ───────────────────────────────────

class UserCallNotificationManager:
    """Push incoming-call events to a specific user.

    DS-05 fix: In a multi-instance deployment the callee may be connected to a
    *different* API replica than the caller.  After the local WS delivery fails,
    we publish to Redis so any replica that holds the callee's WS can deliver it.
    """

    _CHAN_PREFIX = "user:call_notify:"

    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}

    async def start(self) -> None:
        asyncio.create_task(self._redis_subscriber())

    async def _redis_subscriber(self) -> None:
        while True:
            try:
                pubsub = redis_async.pubsub()
                await pubsub.psubscribe(f"{self._CHAN_PREFIX}*")
                async for message in pubsub.listen():
                    if message.get("type") not in ("pmessage", "message"):
                        continue
                    channel: str = message.get("channel", "")
                    raw: str = message.get("data", "")
                    if not raw or not channel:
                        continue
                    user_id = channel[len(self._CHAN_PREFIX):]
                    ws = self.connections.get(user_id)
                    if ws:
                        try:
                            await ws.send_text(raw if isinstance(raw, str) else raw.decode())
                        except Exception:
                            self.connections.pop(user_id, None)
            except Exception as exc:
                logger.error("user_call_notify: Redis subscriber crashed — %s. Restarting in 5s.", exc)
                await asyncio.sleep(5)

    async def connect(self, user_id: str, ws: WebSocket) -> bool:
        """Register WS connection. Returns False if global connection limit is reached."""
        if len(self.connections) >= _MAX_CALL_NOTIFICATION_CONNECTIONS:
            return False
        if ws.client_state == WebSocketState.CONNECTING:
            await ws.accept()
        old = self.connections.get(user_id)
        if old and old is not ws:
            try:
                await old.close()
            except Exception:
                pass
        self.connections[user_id] = ws
        return True

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        if self.connections.get(user_id) is ws:
            self.connections.pop(user_id, None)

    async def notify(self, user_id: str, payload: dict) -> bool:
        """Send a call event to the user if connected locally or on another instance."""
        raw = json.dumps(payload)

        ws = self.connections.get(user_id)
        if ws:
            try:
                await ws.send_text(raw)
                return True
            except Exception:
                self.connections.pop(user_id, None)

        try:
            subscribers = await redis_async.publish(f"{self._CHAN_PREFIX}{user_id}", raw)
            return subscribers > 0
        except Exception as exc:
            logger.warning("user_call_notify: Redis publish failed for user %s — %s", user_id, exc)
            return False


user_call_notification_manager = UserCallNotificationManager()


async def user_call_notification_loop(user_id: str, websocket: WebSocket) -> None:
    try:
        while True:
            text = await websocket.receive_text()
            stripped = text.strip()
            if stripped in ("ping", '{"type":"ping"}'):
                try:
                    await websocket.send_text('{"type":"pong"}')
                except Exception:
                    pass
    except WebSocketDisconnect:
        user_call_notification_manager.disconnect(user_id, websocket)
