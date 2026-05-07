"""
Logging structuré ZASKA — Loguru + filtre données sensibles.

Configuration :
  - Sortie JSON en production (ENV=production)
  - Sortie lisible en dev
  - Champs sensibles masqués automatiquement (OTP, password, token)
  - user_id et request_id injectés via contexte

Usage :
    from app.core.observability.logger import logger, bind_context
    bind_context(user_id="abc", request_id="xyz")
    logger.info("action", extra={"amount": 100})
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from typing import Any

from loguru import logger as _loguru

from app.core.config import settings

# Contexte de requête propagé via contextvars (thread-safe + async-safe)
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

_SENSITIVE_KEYS = frozenset(
    {"password", "password_hash", "otp", "otp_code", "token", "access_token", "refresh_token", "secret"}
)

_OTP_MOCK_LOG = "/tmp/zaska-otp.log"

# Computed once at import time — never changes at runtime.
_IS_DEVELOPMENT: bool = str(settings.env).strip().lower() == "development"


def _sanitize(record: dict[str, Any]) -> bool:
    """Mask sensitive extra fields and hard-block any OTP mock trace outside development."""
    # Defense-in-depth: drop [OTP MOCK] records unconditionally outside development,
    # even if auth_service raises before reaching the log call.
    if not _IS_DEVELOPMENT and "[OTP MOCK]" in record.get("message", ""):
        return False
    for key in list(record.get("extra", {}).keys()):
        if key.lower() in _SENSITIVE_KEYS:
            record["extra"][key] = "***"
    record["extra"]["request_id"] = _request_id_var.get()
    record["extra"]["user_id"] = _user_id_var.get()
    return True


def _configure_logger() -> None:
    _loguru.remove()
    if settings.is_production:
        fmt = (
            '{{"time":"{time:YYYY-MM-DDTHH:mm:ss.SSSZ}",'
            '"level":"{level}",'
            '"name":"{name}",'
            '"message":"{message}",'
            '"request_id":"{extra[request_id]}",'
            '"user_id":"{extra[user_id]}"}}'
        )
    else:
        fmt = (
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "[req={extra[request_id]} user={extra[user_id]}] "
            "<level>{message}</level>"
        )

    try:
        _loguru.add(
            sys.stdout,
            format=fmt,
            level="DEBUG" if not settings.is_production else "INFO",
            filter=_sanitize,
            colorize=not settings.is_production,
            enqueue=True,
        )
    except (PermissionError, OSError):
        _loguru.add(
            sys.stdout,
            format=fmt,
            level="DEBUG" if not settings.is_production else "INFO",
            filter=_sanitize,
            colorize=not settings.is_production,
            enqueue=False,
        )

    # OTP mock log file: strictly development only, never staging or production.
    if _IS_DEVELOPMENT:
        try:
            _loguru.add(
                _OTP_MOCK_LOG,
                format="{time:YYYY-MM-DDTHH:mm:ssZ} {message}",
                level="INFO",
                filter=lambda r: "[OTP MOCK]" in r["message"],
                colorize=False,
                enqueue=True,
                mode="a",
            )
        except OSError:
            pass


_configure_logger()

logger = _loguru


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def set_user_id(user_id: str) -> None:
    _user_id_var.set(user_id)


def get_request_id() -> str:
    return _request_id_var.get()
