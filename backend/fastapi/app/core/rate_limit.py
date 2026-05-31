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
    """Return a FastAPI dependency that enforces per-IP and per-user rate limits.

    Checks two Redis keys — one for the client IP and one for the authenticated
    user_id (extracted from the Bearer JWT when present). Both must be under the
    limit for the request to proceed. Falls open if Redis is unavailable.

    Usage:
        _limit = endpoint_rate_limit("trust:report", max_requests=5, window_seconds=300)

        @router.post("/report")
        async def my_endpoint(_: None = Depends(_limit)):
            ...
    """
    async def _check(request: Request) -> None:
        from app.core.security import decode_token

        client = request.client.host if request.client else "unknown"
        window = int(time.time() // window_seconds)
        ip_key = f"rl:ep:{key_prefix}:{client}:{window}"

        # Extract user_id from JWT if present — silently ignored if missing/invalid
        user_id: str | None = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                payload = decode_token(auth[7:])
                if payload.get("type") == "access":
                    raw_sub = payload.get("sub")
                    if raw_sub:
                        user_id = str(raw_sub)
            except Exception:
                pass

        try:
            n_ip = await redis_async.eval(_LUA_RATE_LIMIT, 1, ip_key, str(window_seconds + 5))
            if int(n_ip) > max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Trop de requêtes — réessayez dans {window_seconds // 60} minutes",
                )
            if user_id:
                uid_key = f"rl:ep:{key_prefix}:uid:{user_id}:{window}"
                n_uid = await redis_async.eval(_LUA_RATE_LIMIT, 1, uid_key, str(window_seconds + 5))
                if int(n_uid) > max_requests:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Trop de requêtes — réessayez dans {window_seconds // 60} minutes",
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # fail open — Redis unavailable, let request through

    return _check
