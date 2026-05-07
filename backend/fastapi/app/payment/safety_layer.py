from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.country_engine.definitions import get_config
from app.models.kyc import KycSubmission
from app.models.user import User


class PaymentMode(str, Enum):
    MOCK = "mock"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class PaymentSafetyError(Exception):
    pass


@dataclass(frozen=True)
class SafetyContext:
    payment_mode: PaymentMode
    country_code: str
    currency: str
    user_id: str


class PaymentSafetyLayer:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def resolve_mode() -> PaymentMode:
        raw = settings.payment_mode.strip().lower()
        if raw == "dev":
            raw = "mock"
        if raw not in {"mock", "sandbox", "production"}:
            raise PaymentSafetyError(f"Invalid PAYMENT_MODE '{settings.payment_mode}'")
        return PaymentMode(raw)

    def assert_create_payment_safe(
        self,
        *,
        user_id: str,
        country_code: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> SafetyContext:
        if not idempotency_key.strip():
            raise PaymentSafetyError("idempotency_key is required")
        if amount <= Decimal("0"):
            raise PaymentSafetyError("amount must be > 0")

        user = self.db.get(User, user_id)
        if not user or not user.is_verified:
            raise PaymentSafetyError("email verification is required before payment")

        cfg = get_config(country_code)
        if currency.upper() != cfg.currency.upper():
            raise PaymentSafetyError(
                f"currency '{currency}' not allowed for country '{country_code.upper()}'"
            )
        return SafetyContext(
            payment_mode=self.resolve_mode(),
            country_code=country_code.upper(),
            currency=currency.upper(),
            user_id=user_id,
        )

    def assert_payout_safe(self, *, user_id: str) -> None:
        user = self.db.get(User, user_id)
        if not user or not user.is_verified:
            raise PaymentSafetyError("email verification is required")

        stmt = (
            select(KycSubmission)
            .where(KycSubmission.user_id == user_id)
            .order_by(KycSubmission.created_at.desc())
        )
        latest = self.db.execute(stmt).scalars().first()
        if not latest or latest.status != "approved":
            raise PaymentSafetyError("KYC approved status is required for payout")

    @staticmethod
    def assert_provider_mode_keys(provider_name: str) -> None:
        mode = PaymentSafetyLayer.resolve_mode()
        if mode == PaymentMode.MOCK:
            return

        if provider_name == "stripe":
            key = settings.stripe_secret_key.strip()
            if mode == PaymentMode.SANDBOX and not key.startswith("sk_test_"):
                raise PaymentSafetyError("sandbox requires Stripe test key")
            if mode == PaymentMode.PRODUCTION and not key.startswith("sk_live_"):
                raise PaymentSafetyError("production requires Stripe live key")
            return

        if provider_name == "fedapay":
            if mode == PaymentMode.SANDBOX and settings.fedapay_env != "sandbox":
                raise PaymentSafetyError("sandbox requires FEDAPAY_ENV=sandbox")
            if mode == PaymentMode.PRODUCTION and settings.fedapay_env != "live":
                raise PaymentSafetyError("production requires FEDAPAY_ENV=live")
            return

        if provider_name == "flutterwave":
            key = settings.flutterwave_secret_key.strip()
            if mode == PaymentMode.SANDBOX and "TEST" not in key.upper():
                raise PaymentSafetyError("sandbox requires Flutterwave test key")
            if mode == PaymentMode.PRODUCTION and "LIVE" not in key.upper():
                raise PaymentSafetyError("production requires Flutterwave live key")
