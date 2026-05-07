"""
Stripe provider — Europe / US / zones carte.

Fonctionnalités :
  - PaymentIntent avec automatic_payment_methods (Apple Pay, Google Pay inclus)
  - Vérification signature webhook via STRIPE_WEBHOOK_SECRET
  - Gestion payment_intent.succeeded + payment_intent.payment_failed

Currencies zero-decimal (pas de conversion ×100) :
  XOF, JPY, KRW, CLP, GNF, ISK, MGA, PYG, RWF, UGX, VND, XAF
"""

from __future__ import annotations

from decimal import Decimal

import stripe
import stripe.error

from app.core import config
from app.core.observability import logger

from .base_provider import (
    InvalidWebhookSignature,
    PaymentIntentResult,
    PaymentProvider,
    PaymentProviderError,
    WebhookEvent,
)

# Devises sans décimales — envoyées à Stripe tel quel (pas de ×100)
_ZERO_DECIMAL_CURRENCIES = frozenset(
    {"XOF", "JPY", "KRW", "CLP", "GNF", "ISK", "MGA", "PYG", "RWF", "UGX", "VND", "XAF"}
)


def _to_stripe_amount(amount: Decimal, currency: str) -> int:
    if currency.upper() in _ZERO_DECIMAL_CURRENCIES:
        return int(amount)
    return int(amount * 100)


def _from_stripe_amount(stripe_amount: int, currency: str) -> Decimal:
    if currency.upper() in _ZERO_DECIMAL_CURRENCIES:
        return Decimal(stripe_amount)
    return Decimal(stripe_amount) / Decimal(100)


class StripeProvider(PaymentProvider):
    PROVIDER_NAME = "stripe"

    def __init__(self) -> None:
        if not config.settings.stripe_secret_key:
            raise PaymentProviderError(
                "STRIPE_SECRET_KEY non configurée — vérifier les variables d'environnement"
            )
        stripe.api_key = config.settings.stripe_secret_key

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
        try:
            stripe_amount = _to_stripe_amount(amount, currency)

            intent = await stripe.PaymentIntent.create_async(
                amount=stripe_amount,
                currency=currency.lower(),
                payment_method_types=["card"],
                automatic_payment_methods={"enabled": True},
                description=task_description[:255],
                receipt_email=user_email or None,
                metadata={
                    "user_id": user_id,
                    "escrow_id": escrow_id,
                    "task_id": task_id,
                    "country_code": country_code,
                },
                idempotency_key=idempotency_key,
            )
            logger.info(
                "Stripe PaymentIntent créé — pi={} escrow={} amount={} {}",
                intent.id, escrow_id, amount, currency,
            )
            return PaymentIntentResult(
                provider_intent_id=intent.id,
                provider="stripe",
                amount=amount,
                currency=currency,
                client_secret=intent.client_secret,
                payment_url=None,
                escrow_id=escrow_id,
                idempotency_key=idempotency_key,
            )
        except stripe.error.StripeError as exc:
            logger.error("Stripe API error: {}", exc.user_message)
            raise PaymentProviderError(str(exc.user_message)) from exc

    async def verify_webhook(
        self,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookEvent:
        sig_header = headers.get("stripe-signature", "")
        if not sig_header:
            raise InvalidWebhookSignature("Header stripe-signature absent")

        if not config.settings.stripe_webhook_secret:
            raise PaymentProviderError("STRIPE_WEBHOOK_SECRET non configurée")

        try:
            event = stripe.Webhook.construct_event(
                raw_body, sig_header, config.settings.stripe_webhook_secret
            )
        except stripe.error.SignatureVerificationError as exc:
            raise InvalidWebhookSignature("Signature Stripe invalide") from exc
        except Exception as exc:
            raise InvalidWebhookSignature(f"Webhook Stripe mal formé: {exc}") from exc

        stripe_event_id: str = event.id or ""
        event_type = event.type
        data_obj = event.data.object

        # StripeObject v5+ is NOT a dict subclass — use .get() or getattr defensively
        def _get(key: str, default=None):
            try:
                v = data_obj.get(key, default)
                return v if v is not None else default
            except (AttributeError, TypeError):
                return getattr(data_obj, key, default)

        def _meta() -> dict:
            raw = _get("metadata") or {}
            if hasattr(raw, "items"):
                return dict(raw)
            return {}

        meta = _meta()

        if event_type == "payment_intent.succeeded":
            pi_id: str = _get("id") or ""
            raw_amount: int = _get("amount") or 0
            raw_currency: str = (_get("currency") or "").upper()
            logger.info("Stripe webhook succeeded — pi={} escrow={} evt={}", pi_id, meta.get("escrow_id"), stripe_event_id)
            return WebhookEvent(
                event_type="payment.success",
                provider_tx_id=pi_id,
                escrow_id=meta.get("escrow_id", ""),
                amount=_from_stripe_amount(raw_amount, raw_currency),
                currency=raw_currency,
                raw_data={"stripe_event_id": stripe_event_id, **meta},
            )

        if event_type == "payment_intent.payment_failed":
            pi_id = _get("id") or ""
            raw_amount = _get("amount") or 0
            raw_currency = (_get("currency") or "").upper()
            logger.warning("Stripe webhook payment_failed — pi={} escrow={} evt={}", pi_id, meta.get("escrow_id"), stripe_event_id)
            return WebhookEvent(
                event_type="payment.failed",
                provider_tx_id=pi_id,
                escrow_id=meta.get("escrow_id", ""),
                amount=_from_stripe_amount(raw_amount, raw_currency),
                currency=raw_currency,
                raw_data={"stripe_event_id": stripe_event_id, **meta},
            )

        if event_type == "checkout.session.completed":
            session_id: str = _get("id") or ""
            raw_amount_total: int = _get("amount_total") or 0
            raw_currency = (_get("currency") or "").upper()
            topup_type = meta.get("type", "")
            logger.info(
                "Stripe checkout.session.completed — session={} type={} user={} evt={}",
                session_id, topup_type, meta.get("user_id"), stripe_event_id,
            )
            if topup_type == "wallet_topup":
                return WebhookEvent(
                    event_type="wallet_topup",
                    provider_tx_id=session_id,
                    escrow_id="",
                    amount=_from_stripe_amount(raw_amount_total, raw_currency),
                    currency=raw_currency,
                    raw_data={
                        "stripe_event_id": stripe_event_id,
                        "session_id": session_id,
                        "stripe_event_type": event_type,
                        **meta,
                    },
                )

        return WebhookEvent(
            event_type="unhandled",
            provider_tx_id="",
            escrow_id="",
            amount=Decimal("0"),
            currency="",
            raw_data={"stripe_event_id": stripe_event_id, "stripe_event_type": event_type},
        )

