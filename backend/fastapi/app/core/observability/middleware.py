"""
RequestID middleware — injecte un UUID unique dans chaque requête.

- Lit X-Request-ID depuis le header si fourni par le reverse proxy
- Sinon génère un UUID4 court (8 chars)
- Expose le request_id dans X-Request-ID de la réponse
- Bind le request_id et user_id dans le contexte de log Loguru
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logger import set_request_id, set_user_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
        set_request_id(req_id)

        # user_id extrait du JWT si présent (best-effort, pas d'auth ici)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                from app.core.security import decode_token
                payload = decode_token(auth[7:])
                set_user_id(payload.get("sub", "-"))
            except Exception:
                set_user_id("-")
        else:
            set_user_id("-")

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class SentryStub:
    """
    Stub Sentry — à remplacer par `import sentry_sdk; sentry_sdk.init(dsn=...)`.
    Capture les exceptions et les log via Loguru en attendant l'intégration réelle.
    """

    @staticmethod
    def capture_exception(exc: Exception) -> None:
        from .logger import logger
        logger.exception("Sentry stub captured exception: {}", exc)

    @staticmethod
    def capture_message(message: str, level: str = "info") -> None:
        from .logger import logger
        getattr(logger, level, logger.info)(f"[Sentry stub] {message}")
