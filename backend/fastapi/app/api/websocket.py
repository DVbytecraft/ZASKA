import json
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.redis_client import redis_async


# ── Chat WebSocket manager ─────────────────────────────────────────────────────

class TaskChatWebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        return

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()
        self.connections[task_id].add(websocket)

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        self.connections[task_id].discard(websocket)

    async def publish(self, task_id: str, payload: dict) -> None:
        raw = json.dumps(payload)
        try:
            await redis_async.publish(f"task-chat:{task_id}", raw)
        except Exception:
            pass
        dead: list[WebSocket] = []
        for ws in list(self.connections.get(task_id, set())):
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(task_id, ws)


chat_ws_manager = TaskChatWebSocketManager()


async def websocket_loop(task_id: str, websocket: WebSocket, user_id: str) -> None:
    await chat_ws_manager.connect(task_id, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            await chat_ws_manager.publish(
                task_id, {"taskId": task_id, "senderId": user_id, "message": text}
            )
    except WebSocketDisconnect:
        chat_ws_manager.disconnect(task_id, websocket)


# ── Call signaling WebSocket manager ──────────────────────────────────────────
# Relays WebRTC signals (offer/answer/ice/hangup) between the two call participants.
# At most 2 connections per call_id (caller + callee).

class CallSignalingManager:
    def __init__(self) -> None:
        # call_id → list of at most 2 WebSockets
        self.rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, call_id: str, ws: WebSocket) -> bool:
        """Accept connection. Returns False if the room is already full."""
        room = self.rooms[call_id]
        if len(room) >= 2:
            return False
        if ws.client_state == WebSocketState.CONNECTING:
            await ws.accept()
        room.append(ws)
        return True

    def disconnect(self, call_id: str, ws: WebSocket) -> None:
        room = self.rooms.get(call_id, [])
        if ws in room:
            room.remove(ws)
        if not room:
            self.rooms.pop(call_id, None)

    async def relay(self, call_id: str, sender: WebSocket, raw: str) -> None:
        """Forward a message from sender to the other participant."""
        for ws in list(self.rooms.get(call_id, [])):
            if ws is not sender:
                try:
                    await ws.send_text(raw)
                except Exception:
                    self.disconnect(call_id, ws)

    async def broadcast_hangup(self, call_id: str, exclude: WebSocket | None = None) -> None:
        """Notify all remaining participants that the call ended."""
        msg = json.dumps({"type": "hangup"})
        for ws in list(self.rooms.get(call_id, [])):
            if ws is not exclude:
                try:
                    await ws.send_text(msg)
                except Exception:
                    pass
        self.rooms.pop(call_id, None)


call_signaling_manager = CallSignalingManager()


async def call_signaling_loop(call_id: str, websocket: WebSocket) -> None:
    """Relay loop for one participant in a call signaling room."""
    try:
        while True:
            raw = await websocket.receive_text()
            await call_signaling_manager.relay(call_id, websocket, raw)
    except WebSocketDisconnect:
        call_signaling_manager.disconnect(call_id, websocket)
        # Notify the remaining peer that their partner disconnected
        await call_signaling_manager.broadcast_hangup(call_id)


# ── User call notification WebSocket manager ───────────────────────────────────
# Each user can have one active notification WebSocket.
# Used to push "incoming_call" events when the user is online.

class UserCallNotificationManager:
    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        if ws.client_state == WebSocketState.CONNECTING:
            await ws.accept()
        # Close any previous connection for this user
        old = self.connections.get(user_id)
        if old and old is not ws:
            try:
                await old.close()
            except Exception:
                pass
        self.connections[user_id] = ws

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        if self.connections.get(user_id) is ws:
            self.connections.pop(user_id, None)

    async def notify(self, user_id: str, payload: dict) -> bool:
        """Send a call event to the user if they are connected. Returns True if sent."""
        ws = self.connections.get(user_id)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(payload))
            return True
        except Exception:
            self.connections.pop(user_id, None)
            return False


user_call_notification_manager = UserCallNotificationManager()


async def user_call_notification_loop(user_id: str, websocket: WebSocket) -> None:
    """Keep-alive loop for the user call notification channel."""
    try:
        while True:
            # We only send to the client; ignore any incoming data (ping frames handled by Starlette)
            await websocket.receive_text()
    except WebSocketDisconnect:
        user_call_notification_manager.disconnect(user_id, websocket)
