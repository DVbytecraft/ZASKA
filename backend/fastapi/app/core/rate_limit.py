import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.redis_client import redis_async
from app.core.responses import error_response

# Atomic INCR + conditional EXPIRE — eliminates the TOCTOU window where a crash
# between INCR and EXPIRE would leave the key without a TTL (permanent lock).
_LUA_RATE_LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiting per client IP via Redis (atomic Lua, async-safe)."""

    def __init__(self, app, prefix: str = "rl:http", max_requests: int = 180, window_seconds: int = 60):
        super().__init__(app)
        self.prefix = prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        window = int(time.time() // self.window_seconds)
        key = f"{self.prefix}:{client}:{window}"

        try:
            # redis_async is AsyncRedis — await is non-blocking on the event loop.
            n = await redis_async.eval(_LUA_RATE_LIMIT, 1, key, str(self.window_seconds + 5))
        except Exception:
            # Redis unavailable — fail open (let request through) rather than hard-blocking.
            return await call_next(request)

        if n > self.max_requests:
            return JSONResponse(
                status_code=429,
                content=error_response("Too many requests — réessayez dans quelques secondes"),
            )

        return await call_next(request)


def endpoint_rate_limit(key_prefix: str, max_requests: int, window_seconds: int):
    """Return a FastAPI dependency that enforces a per-IP rate limit on a specific endpoint.

    Usage:
        _limit = endpoint_rate_limit("trust:report", max_requests=5, window_seconds=300)

        @router.post("/report")
        async def my_endpoint(_: None = Depends(_limit)):
            ...
    """
    async def _check(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        window = int(time.time() // window_seconds)
        key = f"rl:ep:{key_prefix}:{client}:{window}"
        try:
            n = await redis_async.eval(_LUA_RATE_LIMIT, 1, key, str(window_seconds + 5))
            if int(n) > max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Trop de requêtes — réessayez dans {window_seconds // 60} minutes",
                )
        except HTTPException:
            raise
        except Exception:
            pass  # fail open — Redis unavailable, let request through

    return _check
