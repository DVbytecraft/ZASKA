"""
Payment provider factory — provider-agnostic adapter pattern.

The canonical provider interface is:
    app.services.payment.base_provider.PaymentProvider

All providers (Stripe, FedaPay, Flutterwave, Paystack, Mock) implement
this interface and are fully interchangeable. No business logic in the
orchestrator depends on any single provider.

To add a new provider:
  1. Implement PaymentProvider in app/services/payment/<name>_provider.py
  2. Add it to PROVIDER_CLASS_MAP in app/services/payment/provider_factory.py
  3. Wire the country in app/core/country_engine/definitions.py
"""
from __future__ import annotations

from app.services.payment.base_provider import (
    PaymentIntentResult,
    PaymentProvider,
    PayoutResult,
)


def get_payment_provider(*, payment_mode: str, country_code: str) -> PaymentProvider:
    """
    Return the canonical PaymentProvider for the given mode and country.

    - mock/dev mode or real_money_enabled=False → MockProvider (no network calls)
    - sandbox/production → canonical provider resolved from CountryConfig
    """
    from app.core.config import settings
    from app.services.payment.mock_provider import MockProvider
    from app.services.payment.provider_factory import get_provider as _canonical

    if settings.payments_disabled:
        return MockProvider()

    mode = payment_mode.strip().lower()
    if mode in {"dev", "mock"} or not settings.real_money_enabled:
        return MockProvider()

    return _canonical(country_code)


__all__ = [
    "PaymentProvider",
    "PaymentIntentResult",
    "PayoutResult",
    "get_payment_provider",
]
