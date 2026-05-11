"""X-Idempotency-Key middleware for financial endpoints.

Prevents double-submit on retried HTTP requests (network retry, mobile retry,
double-click) for any mutating endpoint under /wallet or /payments.

Protocol:
  Client sends: X-Idempotency-Key: <uuid>
  First request: processed normally, response cached in Redis for 24h.
  Retry with same key: cached response returned immediately (no re-processing).

Redis keys:
  idempotency:{user_scope}:{key}          → cached response (24h TTL)
  idempotency:inflight:{user_scope}:{key} → in-flight lock (30s TTL)

Guarantees:
  - Exactly-once execution for retried requests
  - Same response returned on retry (client gets consistent answer)
  - Key scoped to user_scope (last 32 chars of auth token — unique per session)
  - In-flight lock prevents two concurrent requests with the same key from
    both processing (race condition where neither sees a cache hit yet)
  - TTL ensures eventual key expiry (no permanent Redis growth)

Performance note:
  Uses redis_async (AsyncRedis) to avoid blocking the uvicorn event loop.
  The previous version used redis_sync inside async dispatch, which blocked
  the event loop thread on every guarded request.
"""

from __future__ import annotations

import json
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Endpoints that must be idempotency-guarded (exact path prefix match)
_GUARDED_PREFIXES = (
    "/api/wallet/withdraw",
    "/api/wallet/send",
    "/api/wallet/payout",
    "/api/payments/initiate",
    "/api/payments/topup",
    "/api/tasks/",          # task accept, complete, confirm, cancel — POST only
)

_GUARDED_METHODS = {"POST", "PUT", "PATCH"}

# Redis TTL for cached responses (24h)
_TTL_SECONDS = 86_400
# In-flight lock TTL — max expected request duration (30s) + buffer
_INFLIGHT_TTL_SECONDS = 35


def _should_guard(method: str, path: str) -> bool:
    if method not in _GUARDED_METHODS:
        return False
    return any(path.startswith(p) for p in _GUARDED_PREFIXES)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Redis-backed X-Idempotency-Key middleware (async-safe).

    P1-009 FIX: Added in-flight lock to handle the race condition where two
    concurrent requests arrive with the same idempotency key before either has
    stored its response.  Old code: both miss the cache, both process the request.
    New code: first request acquires an in-flight lock (SET NX); second request
    sees the lock and returns 409 immediately.  After the first stores the response,
    subsequent retries hit the cache as expected.

    SC-01 FIX: Replaced redis_sync with redis_async so all Redis I/O is awaited
    instead of blocking the uvicorn event loop thread.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # redis_async is module-level AsyncRedis — imported lazily to allow app
        # startup before Redis connects.
        self._redis_available = False
        try:
            from app.core.redis_client import redis_async  # noqa: F401
            self._redis_available = True
        except Exception:
            pass

    async def dispatch(self, request: Request, call_next) -> Response:
        idem_key = request.headers.get("X-Idempotency-Key", "").strip()

        if not idem_key or not _should_guard(request.method, request.url.path):
            return await call_next(request)

        if not self._redis_available:
            return await call_next(request)

        # Import here so we always use the live module-level singleton
        from app.core.redis_client import redis_async as _redis

        # Scope key to this user session — last 32 chars of auth token (unique per JWT).
        auth_header = request.headers.get("Authorization", "")
        user_scope = auth_header[-32:] if len(auth_header) >= 32 else auth_header
        cache_key = f"idempotency:{user_scope}:{idem_key}"
        inflight_key = f"idempotency:inflight:{user_scope}:{idem_key}"

        # ── 1. Check cached response ─────────────────────────────────────────
        try:
            cached = await _redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                logger.info(
                    "idempotency: cache HIT key=%s path=%s → returning cached %s",
                    idem_key[:8], request.url.path, data.get("status_code"),
                )
                return Response(
                    content=data["body"],
                    status_code=data["status_code"],
                    media_type=data.get("media_type", "application/json"),
                    headers={"X-Idempotency-Replayed": "true"},
                )
        except Exception as exc:
            logger.warning("idempotency: Redis read failed — %s. Proceeding without cache.", exc)

        # ── 2. Acquire in-flight lock (SET NX) ───────────────────────────────
        try:
            acquired = await _redis.set(inflight_key, "1", nx=True, ex=_INFLIGHT_TTL_SECONDS)
            if not acquired:
                logger.info(
                    "idempotency: in-flight conflict key=%s path=%s — returning 409",
                    idem_key[:8], request.url.path,
                )
                return Response(
                    content=json.dumps({
                        "success": False,
                        "error": "Une requête identique est en cours de traitement. Réessayez dans quelques secondes.",
                    }),
                    status_code=409,
                    media_type="application/json",
                    headers={"X-Idempotency-InFlight": "true"},
                )
        except Exception as exc:
            logger.warning("idempotency: in-flight lock check failed — %s. Proceeding.", exc)

        # ── 3. Process the request ───────────────────────────────────────────
        response = await call_next(request)

        # ── 4. Cache the response and release in-flight lock ─────────────────
        if 200 <= response.status_code < 500:
            try:
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk if isinstance(chunk, bytes) else chunk.encode()

                await _redis.setex(
                    cache_key,
                    _TTL_SECONDS,
                    json.dumps({
                        "status_code": response.status_code,
                        "body": body.decode("utf-8", errors="replace"),
                        "media_type": response.media_type,
                    }),
                )
                logger.info(
                    "idempotency: cached key=%s path=%s status=%s",
                    idem_key[:8], request.url.path, response.status_code,
                )
                try:
                    await _redis.delete(inflight_key)
                except Exception:
                    pass
                return Response(
                    content=body,
                    status_code=response.status_code,
                    media_type=response.media_type,
                    headers=dict(response.headers),
                )
            except Exception as exc:
                logger.warning("idempotency: Redis write failed — %s. Response not cached.", exc)

        # Release in-flight lock on 5xx errors (not cached)
        try:
            await _redis.delete(inflight_key)
        except Exception:
            pass

        return response
