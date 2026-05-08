"""
PaystackProvider — canonical adapter for Paystack (Nigeria-first, Africa-ready).

Paystack is the primary Mobile Money / card rail for Nigeria.
Also supports Ghana (card + MoMo), Kenya, South Africa.

Payment flow:
  1. create_payment_intent() → Paystack hosted checkout URL (authorization_url)
  2. User completes payment on Paystack
  3. Paystack fires webhook → verify_webhook() → WebhookEvent
  4. handle_success() / handle_failure() via base class (WalletService)
  5. Payouts via Transfers API (payout())

Mobile Money priority for Africa:
  - NG: USSD, bank_transfer, mobile_money first; card secondary
  - GH/KE: mobile_money first; card secondary
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings

from .base_provider import (
    InvalidWebhookSignature,
    PaymentIntentResult,
    PaymentProvider,
    PaymentProviderError,
    PayoutResult,
    WebhookEvent,
)

_BASE_URL = "https://api.paystack.co"

# Smallest-unit multiplier — Paystack amounts in kobo/pesewas/cents (* 100)
_SUBUNIT_FACTOR = Decimal("100")

# Channel order encodes Mobile Money preference for Africa
_CHANNELS_BY_COUNTRY: dict[str, list[str]] = {
    "NG": ["ussd", "mobile_money", "bank_transfer", "card", "bank", "qr"],
    "GH": ["mobile_money", "card", "bank"],
    "KE": ["mobile_money", "card", "bank"],
    "ZA": ["card", "bank_transfer"],
}
_CHANNELS_DEFAULT = ["card", "bank_transfer"]

_CURRENCY_BY_COUNTRY: dict[str, str] = {
    "NG": "NGN",
    "GH": "GHS",
    "KE": "KES",
    "ZA": "ZAR",
}

# Paystack Transfer — mobile money bank codes per country
_MM_BANK_CODE: dict[str, str] = {
    "NG": "MTN",
    "GH": "MTN",
    "KE": "SAFARICOM",
}


class PaystackProvider(PaymentProvider):
    """
    Paystack adapter — implements the canonical PaymentProvider interface.

    All business logic is provider-agnostic; this class maps the canonical
    interface to Paystack-specific HTTP calls.
    """

    PROVIDER_NAME = "paystack"

    def __init__(self) -> None:
        sk = (settings.paystack_secret_key or "").strip()
        if not sk:
            raise PaymentProviderError("PAYSTACK_SECRET_KEY not configured")
        self._secret_key = sk
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={
                "Authorization": f"Bearer {self._secret_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ── create_payment_intent ─────────────────────────────────────────────────

    async def create_payment_intent(
        self,
        *,
        amount: Decimal,
        currency: str,
        user_id: str,
        user_email: str,
        escrow_id: str,
        task_id: str,
        task_description: str,
        country_code: str,
        idempotency_key: str,
    ) -> PaymentIntentResult:
        cc = country_code.upper()
        resolved_currency = currency.upper() or _CURRENCY_BY_COUNTRY.get(cc, "NGN")
        amount_subunit = int((amount * _SUBUNIT_FACTOR).to_integral_value())

        payload: dict[str, Any] = {
            "email": user_email or f"user_{user_id}@zaska.app",
            "amount": amount_subunit,
            "currency": resolved_currency,
            "reference": idempotency_key[:100],
            "callback_url": (
                f"{settings.payment_webhook_base_url.rstrip('/')}"
                f"/api/payments/webhook/paystack"
            ),
            "metadata": {
                "escrow_id": escrow_id,
                "task_id": task_id,
                "task_description": task_description[:100],
                "user_id": user_id,
                "country_code": cc,
                "zaska_idempotency_key": idempotency_key,
            },
            "channels": _CHANNELS_BY_COUNTRY.get(cc, _CHANNELS_DEFAULT),
        }

        try:
            resp = await self._client.post("/transaction/initialize", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PaymentProviderError(
                f"Paystack init failed [{exc.response.status_code}]: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise PaymentProviderError(f"Paystack network error: {exc}") from exc

        data = resp.json().get("data", {})
        return PaymentIntentResult(
            provider_intent_id=data.get("reference", idempotency_key),
            provider=self.PROVIDER_NAME,
            amount=amount,
            currency=resolved_currency,
            client_secret=None,
            payment_url=data.get("authorization_url"),
            escrow_id=escrow_id,
            idempotency_key=idempotency_key,
        )

    # ── verify_webhook ────────────────────────────────────────────────────────

    async def verify_webhook(
        self,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookEvent:
        signature = headers.get("x-paystack-signature", "")
        secret = (settings.paystack_webhook_secret or "").encode()
        mac = hmac.new(secret, raw_body, hashlib.sha512)
        expected = mac.hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise InvalidWebhookSignature("Paystack HMAC-SHA512 signature mismatch")

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise InvalidWebhookSignature("Invalid JSON body") from exc

        event_name: str = body.get("event", "")
        data: dict = body.get("data", {})
        meta: dict = (data.get("metadata") or {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}

        escrow_id: str = meta.get("escrow_id", "")
        reference: str = data.get("reference", "")
        amount_raw = data.get("amount", 0)
        currency: str = data.get("currency", "")
        amount = Decimal(str(amount_raw)) / _SUBUNIT_FACTOR

        if event_name == "charge.success":
            event_type = "payment.success"
        elif event_name in {"charge.failed", "transfer.failed", "charge.dispute.create"}:
            event_type = "payment.failed"
        else:
            event_type = "unhandled"

        return WebhookEvent(
            event_type=event_type,
            provider_tx_id=reference,
            escrow_id=escrow_id,
            amount=amount,
            currency=currency,
            raw_data=body,
        )

    # ── payout ────────────────────────────────────────────────────────────────

    async def payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        recipient_phone: str,
        country_code: str,
        reference: str,
        idempotency_key: str,
    ) -> PayoutResult:
        """
        Paystack Transfer API — payout to mobile money account.

        Step 1: create a transfer recipient for the phone number.
        Step 2: initiate the transfer.
        """
        cc = country_code.upper()
        resolved_currency = currency.upper() or _CURRENCY_BY_COUNTRY.get(cc, "NGN")
        amount_subunit = int((amount * _SUBUNIT_FACTOR).to_integral_value())

        recipient_payload: dict[str, Any] = {
            "type": "mobile_money",
            "currency": resolved_currency,
            "account_number": recipient_phone,
            "bank_code": _MM_BANK_CODE.get(cc, "MTN"),
        }

        try:
            r = await self._client.post("/transferrecipient", json=recipient_payload)
            r.raise_for_status()
            recipient_code: str = r.json()["data"]["recipient_code"]

            transfer_payload: dict[str, Any] = {
                "source": "balance",
                "amount": amount_subunit,
                "recipient": recipient_code,
                "reason": reference[:100],
                "reference": idempotency_key[:100],
            }
            tr = await self._client.post("/transfer", json=transfer_payload)
            tr.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PaymentProviderError(
                f"Paystack payout failed [{exc.response.status_code}]: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise PaymentProviderError(f"Paystack payout network error: {exc}") from exc

        tr_data = tr.json().get("data", {})
        return PayoutResult(
            provider=self.PROVIDER_NAME,
            payout_id=tr_data.get("transfer_code", idempotency_key),
            status=tr_data.get("status", "processing"),
            amount=amount,
            currency=resolved_currency,
            raw=tr_data,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
