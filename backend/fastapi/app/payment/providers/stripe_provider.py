from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.payment.stripe_provider import StripeProvider

from .base import PaymentProvider, PaymentResult


class StripePaymentProvider(PaymentProvider):
    def __init__(self) -> None:
        self._provider = StripeProvider()

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
        result = await self._provider.create_payment_intent(
            amount=amount,
            currency=currency,
            user_id=user_id,
            user_email=user_email,
            escrow_id=str(metadata.get("escrow_id", "")),
            task_id=str(metadata.get("task_id", "")),
            task_description=str(metadata.get("task_description", "ZASKA payment")),
            country_code=str(metadata.get("country_code", "")),
            idempotency_key=idempotency_key,
        )
        return PaymentResult(
            provider="stripe",
            payment_id=result.provider_intent_id,
            status="created",
            amount=result.amount,
            currency=result.currency,
            raw={"client_secret": result.client_secret},
        )

    async def confirm_payment(self, payment_id: str) -> PaymentResult:
        return PaymentResult(
            provider="stripe",
            payment_id=payment_id,
            status="webhook_confirmed",
            amount=Decimal("0"),
            currency="",
        )

    async def refund(self, payment_id: str, *, amount: Decimal | None = None) -> PaymentResult:
        return PaymentResult(
            provider="stripe",
            payment_id=payment_id,
            status="refund_requested",
            amount=amount or Decimal("0"),
            currency="",
        )
