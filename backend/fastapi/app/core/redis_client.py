from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import settings

# Retry policy: exponential backoff, up to 3 attempts
# Covers transient Redis restart / network blip without cascading to 500s
_RETRY = Retry(ExponentialBackoff(cap=1.0, base=0.1), retries=3)

_COMMON_KWARGS = dict(
    decode_responses=True,
    socket_keepalive=True,              # TCP keepalive — prevents NAT/LB from dropping idle connections
    socket_keepalive_options={},
    socket_timeout=5,                   # Max wait for any single Redis operation
    socket_connect_timeout=3,
    retry_on_timeout=True,
    retry_on_error=[ConnectionError, TimeoutError],
    retry=_RETRY,
    health_check_interval=30,
)

redis_sync = Redis.from_url(settings.redis_url, **_COMMON_KWARGS)

# max_connections caps the async connection pool.
# Without this, 10k concurrent WebSocket coroutines each awaiting redis_async could
# each open their own connection, exhausting Redis's client limit (default 10k).
# 200 connections leaves ample room for Celery workers and sync clients while
# preventing pool explosion on WS storms.
redis_async = AsyncRedis.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_async_connections,
    **_COMMON_KWARGS,
)
