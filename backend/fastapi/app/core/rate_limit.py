import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.redis_client import redis_sync
from app.core.responses import error_response


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiting per client IP via Redis."""

    def __init__(self, app, prefix: str = "rl:http", max_requests: int = 180, window_seconds: int = 60):
        super().__init__(app)
        self.prefix = prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = int(now // self.window_seconds)
        key = f"{self.prefix}:{client}:{window}"

        n = redis_sync.incr(key)
        if n == 1:
            redis_sync.expire(key, self.window_seconds + 5)

        if n > self.max_requests:
            return JSONResponse(
                status_code=429,
                content=error_response("Too many requests — réessayez dans quelques secondes"),
            )

        return await call_next(request)
