import json
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.redis_client import redis_async


class TaskChatWebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def start(self) -> None:
        """Redis PubSub listener is optional for multi-worker setups; fan-out happens in publish()."""
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
            await chat_ws_manager.publish(task_id, {"taskId": task_id, "senderId": user_id, "message": text})
    except WebSocketDisconnect:
        chat_ws_manager.disconnect(task_id, websocket)
