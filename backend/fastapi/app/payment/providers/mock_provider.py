from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from .base import PaymentProvider, PaymentResult


class MockPaymentProvider(PaymentProvider):
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
        payment_id = f"mock_{uuid.uuid4().hex[:14]}"
        return PaymentResult(
            provider="mock",
            payment_id=payment_id,
            status="created",
            amount=amount,
            currency=currency,
            raw={"metadata": metadata, "idempotency_key": idempotency_key},
        )

    async def confirm_payment(self, payment_id: str) -> PaymentResult:
        return PaymentResult(
            provider="mock",
            payment_id=payment_id,
            status="confirmed",
            amount=Decimal("0"),
            currency="",
        )

    async def refund(self, payment_id: str, *, amount: Decimal | None = None) -> PaymentResult:
        return PaymentResult(
            provider="mock",
            payment_id=payment_id,
            status="refunded",
            amount=amount or Decimal("0"),
            currency="",
        )
