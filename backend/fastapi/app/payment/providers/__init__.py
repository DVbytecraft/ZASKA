from __future__ import annotations

from app.core.country_engine.definitions import get_config
from app.core.config import settings

from .base import PaymentProvider, PaymentResult
from .mobile_money_provider import MobileMoneyProvider
from .mock_provider import MockPaymentProvider
from .stripe_provider import StripePaymentProvider


def get_payment_provider(*, payment_mode: str, country_code: str) -> PaymentProvider:
    if settings.payments_disabled:
        return MockPaymentProvider()

    mode = payment_mode.strip().lower()
    if mode == "dev":
        mode = "mock"

    if mode == "mock" or not settings.real_money_enabled:
        return MockPaymentProvider()

    config = get_config(country_code)
    provider_name = config.payment_providers[0] if config.payment_providers else "stripe"
    if provider_name == "stripe":
        return StripePaymentProvider()
    if provider_name in {"fedapay", "flutterwave"}:
        return MobileMoneyProvider()
    raise ValueError(f"Unsupported payment provider '{provider_name}' for country '{country_code}'")


__all__ = [
    "PaymentProvider",
    "PaymentResult",
    "MockPaymentProvider",
    "StripePaymentProvider",
    "MobileMoneyProvider",
    "get_payment_provider",
]
