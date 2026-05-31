from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import settings

_RETRY = Retry(ExponentialBackoff(cap=1.0, base=0.1), retries=3)

_COMMON_KWARGS = dict(
    decode_responses=True,
    socket_keepalive=True,
    socket_keepalive_options={},
    socket_timeout=5,
    socket_connect_timeout=3,
    retry_on_timeout=True,
    retry_on_error=[ConnectionError, TimeoutError],
    retry=_RETRY,
    health_check_interval=30,
)

# Lighter kwargs for Sentinel connections (short timeout for discovery).
_SENTINEL_NODE_KWARGS = dict(socket_timeout=0.5, socket_connect_timeout=0.5)

# Client kwargs for master connections via Sentinel (no retry object — Sentinel handles reconnect).
_SENTINEL_MASTER_KWARGS = dict(
    decode_responses=True,
    socket_keepalive=True,
    socket_timeout=5,
    socket_connect_timeout=3,
    retry_on_timeout=True,
    health_check_interval=30,
)


def _parse_sentinel_hosts(raw: str) -> list[tuple[str, int]]:
    hosts = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        host, _, port_str = item.rpartition(":")
        hosts.append((host or item, int(port_str or 26379)))
    return hosts


_sentinel_raw = settings.redis_sentinel_hosts.strip()

if _sentinel_raw:
    # ── High-availability mode: Redis Sentinel ────────────────────────────
    # The Sentinel discovers the current master and handles automatic failover.
    # Connections are transparently re-routed when a new master is elected.
    from redis.sentinel import Sentinel as _SyncSentinel
    from redis.asyncio.sentinel import Sentinel as _AsyncSentinel  # type: ignore[import-untyped]

    _hosts = _parse_sentinel_hosts(_sentinel_raw)
    _master_name = settings.redis_sentinel_master_name

    _sync_sentinel = _SyncSentinel(_hosts, **_SENTINEL_NODE_KWARGS)
    redis_sync: Redis = _sync_sentinel.master_for(_master_name, **_SENTINEL_MASTER_KWARGS)

    _async_sentinel = _AsyncSentinel(_hosts, **_SENTINEL_NODE_KWARGS)
    redis_async: AsyncRedis = _async_sentinel.master_for(
        _master_name,
        max_connections=settings.redis_max_async_connections,
        **_SENTINEL_MASTER_KWARGS,
    )
else:
    # ── Standard mode: single Redis URL ──────────────────────────────────
    redis_sync = Redis.from_url(settings.redis_url, **_COMMON_KWARGS)
    redis_async = AsyncRedis.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_async_connections,
        **_COMMON_KWARGS,
    )
