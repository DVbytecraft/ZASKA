"""Device fingerprint middleware.

Captures X-Device-ID header on every authenticated request and records
the device_id → user_id association in Redis for multi-account detection.

The client (mobile app) generates a persistent UUID on first install and
sends it as X-Device-ID on every request. This lets the backend track
which physical devices have logged into multiple accounts.

Fail-open: if Redis is unavailable or the header is missing, the request
continues normally — fingerprinting is advisory, not a gate.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability import logger
from app.services.multi_account_service import MultiAccountService


class DeviceFingerprintMiddleware(BaseHTTPMiddleware):
    """Record X-Device-ID + authenticated user_id in Redis on every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        device_id = request.headers.get("X-Device-ID", "").strip()
        if device_id:
            # Extract user_id from Bearer token if present — non-blocking, fail-open
            user_id: str | None = None
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                try:
                    from app.core.security import decode_token
                    payload = decode_token(auth[7:])
                    if payload.get("type") == "access":
                        raw = payload.get("sub")
                        if raw:
                            user_id = str(raw)
                except Exception:
                    pass

            if user_id:
                try:
                    ip = request.client.host if request.client else None
                    result = MultiAccountService().register_device(user_id, device_id, ip)
                    if result.get("risk_flag"):
                        logger.warning(
                            "device_fingerprint:multi_account_risk user_id={} device_id={} count={}",
                            user_id,
                            device_id,
                            result.get("device_user_count"),
                        )
                except Exception as exc:
                    logger.debug("device_fingerprint:error {}", exc)

        return await call_next(request)
