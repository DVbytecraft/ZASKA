import json
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.redis_client import redis_sync

# Atomic GET + DELETE via Lua script - works with any Redis version.
# Prevents TOCTOU: two concurrent WS connects with the same ticket could both
# call redis_sync.get() before either deletes it and both receive a valid user_id.
# The Lua script executes atomically on the Redis server - the second call always
# sees nil because the first already deleted the key.
_GET_DEL_SCRIPT = """
local v = redis.call('GET', KEYS[1])
if v then redis.call('DEL', KEYS[1]) end
return v
"""

_LOCAL_TICKETS: dict[str, tuple[str, datetime]] = {}
_LOCAL_TICKETS_LOCK = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _prune_local_tickets(now: datetime) -> None:
    expired = [key for key, (_value, expiry) in _LOCAL_TICKETS.items() if expiry <= now]
    for key in expired:
        _LOCAL_TICKETS.pop(key, None)


def _store_local_ticket(ticket: str, payload: str) -> None:
    now = _utcnow()
    expires_at = now + timedelta(seconds=settings.ws_ticket_ttl_seconds)
    with _LOCAL_TICKETS_LOCK:
        _prune_local_tickets(now)
        _LOCAL_TICKETS[ticket] = (payload, expires_at)


def _consume_local_ticket(ticket: str) -> str | None:
    now = _utcnow()
    with _LOCAL_TICKETS_LOCK:
        _prune_local_tickets(now)
        entry = _LOCAL_TICKETS.pop(ticket, None)
    if entry is None:
        return None
    payload, expires_at = entry
    if expires_at <= now:
        return None
    return payload


def create_ws_ticket(user_id: str, task_id: str | None = None) -> str:
    """Create a one-time WebSocket ticket."""
    ticket = str(uuid.uuid4())
    payload = json.dumps({"user_id": user_id, "task_id": task_id or ""})
    try:
        redis_sync.setex(f"ws_ticket:{ticket}", settings.ws_ticket_ttl_seconds, payload)
    except Exception:
        _store_local_ticket(ticket, payload)
    return ticket


def consume_ws_ticket(ticket: str, expected_task_id: str | None = None) -> str | None:
    """Consume a one-time ticket and return the user_id."""
    key = f"ws_ticket:{ticket}"
    raw = None
    try:
        raw = redis_sync.eval(_GET_DEL_SCRIPT, 1, key)
    except Exception:
        try:
            raw = redis_sync.getdel(key)
        except Exception:
            try:
                raw = redis_sync.get(key)
                if raw:
                    redis_sync.delete(key)
            except Exception:
                raw = _consume_local_ticket(ticket)

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
