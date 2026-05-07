import json
import uuid

from app.core.config import settings
from app.core.redis_client import redis_sync


def create_ws_ticket(user_id: str, task_id: str | None = None) -> str:
    """Create a one-time WebSocket ticket.

    When task_id is provided it is embedded so the connection handler can verify
    the ticket was issued for the specific task being joined.
    """
    ticket = str(uuid.uuid4())
    payload = json.dumps({"user_id": user_id, "task_id": task_id or ""})
    redis_sync.setex(f"ws_ticket:{ticket}", settings.ws_ticket_ttl_seconds, payload)
    return ticket


def consume_ws_ticket(ticket: str, expected_task_id: str | None = None) -> str | None:
    """Consume a one-time ticket and return the user_id.

    Returns None if the ticket is invalid, already used, or the task_id
    does not match expected_task_id (when provided).
    """
    key = f"ws_ticket:{ticket}"
    raw = redis_sync.get(key)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        user_id: str = data.get("user_id", "")
        ticket_task_id: str = data.get("task_id", "")
    except (json.JSONDecodeError, AttributeError):
        redis_sync.delete(key)
        return None

    if expected_task_id and ticket_task_id and ticket_task_id != expected_task_id:
        return None

    redis_sync.delete(key)
    return user_id or None
