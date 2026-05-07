from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class PaymentResult:
    provider: str
    payment_id: str
    status: str
    amount: Decimal
    currency: str
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        user_id: str,
        user_email: str,
        metadata: dict[str, Any],
        idempotency_key: str,
    ) -> PaymentResult: ...

    @abstractmethod
    async def confirm_payment(
        self,
        payment_id: str,
    ) -> PaymentResult: ...

    @abstractmethod
    async def refund(
        self,
        payment_id: str,
        *,
        amount: Decimal | None = None,
    ) -> PaymentResult: ...
