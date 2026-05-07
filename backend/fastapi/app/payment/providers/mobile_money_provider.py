from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.country_engine.definitions import get_config
from app.services.payment.fedapay_provider import FedaPayProvider
from app.services.payment.flutterwave_provider import FlutterwaveProvider

from .base import PaymentProvider, PaymentResult


class MobileMoneyProvider(PaymentProvider):
    def _provider_for_country(self, country_code: str):
        cfg = get_config(country_code)
        provider_name = cfg.payment_providers[0] if cfg.payment_providers else "fedapay"
        if provider_name == "flutterwave":
            return FlutterwaveProvider(), "flutterwave"
        return FedaPayProvider(), "fedapay"

    async def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        user_id: str,
        user_email: str,
        metadata: dict[str, Any],
        idempotency_key: str,
    ) -> PaymentResult:
        for key in ("escrow_id", "user_id", "country_code"):
            if not str(metadata.get(key, "")).strip():
                raise ValueError(f"Missing mandatory metadata '{key}'")
        country_code = str(metadata.get("country_code", "")).upper()
        provider, provider_name = self._provider_for_country(country_code)
        result = await provider.create_payment_intent(
            amount=amount,
            currency=currency,
            user_id=user_id,
            user_email=user_email,
            escrow_id=str(metadata.get("escrow_id", "")),
            task_id=str(metadata.get("task_id", "")),
            task_description=str(metadata.get("task_description", "ZASKA payment")),
            country_code=country_code,
            idempotency_key=idempotency_key,
        )
        return PaymentResult(
            provider=provider_name,
            payment_id=result.provider_intent_id,
            status="created",
            amount=result.amount,
            currency=result.currency,
            raw={"payment_url": result.payment_url},
        )

    async def confirm_payment(self, payment_id: str) -> PaymentResult:
        return PaymentResult(
            provider="mobile_money",
            payment_id=payment_id,
            status="webhook_confirmed",
            amount=Decimal("0"),
            currency="",
        )

    async def refund(self, payment_id: str, *, amount: Decimal | None = None) -> PaymentResult:
        return PaymentResult(
            provider="mobile_money",
            payment_id=payment_id,
            status="refund_requested",
            amount=amount or Decimal("0"),
            currency="",
        )
