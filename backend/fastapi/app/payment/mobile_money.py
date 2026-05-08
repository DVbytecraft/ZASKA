"""
Mobile Money resilience layer for African telco networks.

Handles intermittent connectivity, telco-side temporary failures, and
delayed payment confirmations (MM webhooks arrive minutes/hours later).

Retry policy:
  - NETWORK_TIMEOUT, PROVIDER_UNAVAILABLE, TEMPORARY_FAILURE → retry
  - INSUFFICIENT_FUNDS, INVALID_PHONE, PERMANENT_FAILURE → raise immediately
  - Max 3 attempts with exponential backoff (2s, 4s, cap 30s)

NOT handled here (handled by the Celery periodic poller):
  - Long-running pending payments awaiting async webhook confirmation
"""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

import httpx

T = TypeVar("T")


class TelcoErrorType(enum.Enum):
    NETWORK_TIMEOUT = "network_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # 5xx
    INSUFFICIENT_FUNDS = "insufficient_funds"       # 402 or telco-specific
    INVALID_PHONE = "invalid_phone"                 # 400 phone validation
    TEMPORARY_FAILURE = "temporary_failure"         # generic retry-able (429, etc.)
    PERMANENT_FAILURE = "permanent_failure"         # do not retry


@dataclass(frozen=True)
class MobileMoneyRetryConfig:
    max_attempts: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 30.0
    retryable: frozenset[TelcoErrorType] = field(default_factory=lambda: frozenset({
        TelcoErrorType.NETWORK_TIMEOUT,
        TelcoErrorType.PROVIDER_UNAVAILABLE,
        TelcoErrorType.TEMPORARY_FAILURE,
    }))


MM_RETRY_CONFIG = MobileMoneyRetryConfig()


def classify_mm_error(exc: Exception) -> TelcoErrorType:
    """Map a raw exception to a TelcoErrorType for retry decisions."""
    if isinstance(exc, httpx.TimeoutException):
        return TelcoErrorType.NETWORK_TIMEOUT
    if isinstance(exc, httpx.ConnectError):
        return TelcoErrorType.NETWORK_TIMEOUT
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        body = exc.response.text.lower()
        if code == 402 or "insufficient" in body:
            return TelcoErrorType.INSUFFICIENT_FUNDS
        if code in {400, 422} and "phone" in body:
            return TelcoErrorType.INVALID_PHONE
        if code == 429:
            return TelcoErrorType.TEMPORARY_FAILURE
        if code >= 500:
            return TelcoErrorType.PROVIDER_UNAVAILABLE
        return TelcoErrorType.PERMANENT_FAILURE
    if isinstance(exc, (ConnectionError, OSError)):
        return TelcoErrorType.NETWORK_TIMEOUT
    return TelcoErrorType.TEMPORARY_FAILURE


async def retry_mm_call(
    coro_fn: Callable[[], Awaitable[T]],
    *,
    config: MobileMoneyRetryConfig = MM_RETRY_CONFIG,
    operation_name: str = "mm_call",
) -> T:
    """
    Execute an async Mobile Money API call with exponential backoff.

    Retries only on transient telco errors. Raises the last exception
    on final failure so the orchestrator can decide to fallback.

    Usage:
        result = await retry_mm_call(
            lambda: provider.create_payment_intent(...),
            operation_name="create_intent:fedapay",
        )
    """
    from app.core.observability import logger

    last_exc: Exception = RuntimeError("No attempts made")  # satisfies type-checker
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            error_type = classify_mm_error(exc)
            if error_type not in config.retryable or attempt == config.max_attempts:
                logger.warning(
                    "mm_resilience:{} attempt={}/{} error_type={} final=True exc={}",
                    operation_name, attempt, config.max_attempts, error_type.value, exc,
                )
                raise
            delay = min(
                config.base_delay_seconds * (2 ** (attempt - 1)),
                config.max_delay_seconds,
            )
            logger.warning(
                "mm_resilience:{} attempt={}/{} error_type={} — retrying in {:.1f}s",
                operation_name, attempt, config.max_attempts, error_type.value, delay,
            )
            await asyncio.sleep(delay)

    raise last_exc  # pragma: no cover
