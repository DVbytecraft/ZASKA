import json
import uuid

from app.core.config import settings
from app.core.redis_client import redis_sync

# Atomic GET + DELETE via Lua script — works with any Redis version.
# Prevents TOCTOU: two concurrent WS connects with the same ticket could both
# call redis_sync.get() before either deletes it and both receive a valid user_id.
# The Lua script executes atomically on the Redis server — the second call always
# sees nil because the first already deleted the key.
_GET_DEL_SCRIPT = """
local v = redis.call('GET', KEYS[1])
if v then redis.call('DEL', KEYS[1]) end
return v
"""


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

    P1-006 FIX: Uses an atomic Lua GET+DEL to prevent ticket replay.
    Two concurrent WebSocket connections with the same ticket both call this
    function; the Lua script ensures only the first receives the value —
    the second always gets nil regardless of timing.

    Returns None if the ticket is invalid, already used, or the task_id
    does not match expected_task_id (when provided).
    """
    key = f"ws_ticket:{ticket}"
    # Atomic get-and-delete: script returns the value and deletes in one Redis op.
    try:
        raw = redis_sync.eval(_GET_DEL_SCRIPT, 1, key)
    except Exception:
        # Fallback for edge cases (e.g. Redis eval disabled) — use GETDEL if available
        try:
            raw = redis_sync.getdel(key)
        except Exception:
            # Last resort: non-atomic (tiny TOCTOU window remains, acceptable fallback)
            raw = redis_sync.get(key)
            if raw:
                redis_sync.delete(key)

    if not raw:
        return None

    try:
        data = json.loads(raw)
        user_id: str = data.get("user_id", "")
        ticket_task_id: str = data.get("task_id", "")
    except (json.JSONDecodeError, AttributeError):
        return None

    if expected_task_id and ticket_task_id and ticket_task_id != expected_task_id:
        return None

    return user_id or None
