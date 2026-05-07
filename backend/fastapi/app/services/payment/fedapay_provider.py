"""
FedaPay provider — Togo / Afrique francophone (zone CFA).

Méthodes supportées : TMoney, Flooz (Orange Money), Wave
Currency : XOF

API REST FedaPay v1 :
  Sandbox : https://sandbox-api.fedapay.com/v1
  Live    : https://api.fedapay.com/v1

Authentification : Bearer {FEDAPAY_API_KEY}

Flux paiement :
  1. POST /transactions        → crée la transaction, retourne payment_url
  2. Utilisateur paie sur l'interface FedaPay
  3. FedaPay POST webhook      → verify_webhook() → WebhookEvent

Vérification webhook FedaPay :
  Header : FedaPay-Signature: t={timestamp},v1={hmac_sha256}
  Signature = HMAC_SHA256(secret, "{timestamp}.{raw_body}")
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import httpx

from app.core import config
from app.core.observability import logger

from .base_provider import (
    InvalidWebhookSignature,
    PaymentIntentResult,
    PaymentProvider,
    PaymentProviderError,
    WebhookEvent,
)

_SANDBOX_URL = "https://sandbox-api.fedapay.com/v1"
_LIVE_URL = "https://api.fedapay.com/v1"


def _base_url() -> str:
    return _LIVE_URL if config.settings.fedapay_env == "live" else _SANDBOX_URL


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.settings.fedapay_api_key}",
        "Content-Type": "application/json",
    }


def _verify_fedapay_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """
    FedaPay envoie : FedaPay-Signature: t=<ts>,v1=<hex>
    Signature = HMAC_SHA256(secret, f"{timestamp}.{body}")
    """
    parts: dict[str, str] = {}
    for part in signature_header.split(","):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            parts[k] = v

    timestamp = parts.get("t", "")
    v1 = parts.get("v1", "")
    if not timestamp or not v1:
        return False

    signed_payload = f"{timestamp}.{raw_body.decode('utf-8', errors='replace')}"
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, v1)


class FedaPayProvider(PaymentProvider):
    PROVIDER_NAME = "fedapay"

    def __init__(self) -> None:
        if not config.settings.fedapay_api_key:
            raise PaymentProviderError(
                "FEDAPAY_API_KEY non configurée — vérifier les variables d'environnement"
            )
        mode = config.settings.payment_mode
        if mode == "sandbox" and config.settings.fedapay_env != "sandbox":
            raise PaymentProviderError("FEDAPAY_ENV must be sandbox in sandbox mode")
        if mode == "production" and config.settings.fedapay_env != "live":
            raise PaymentProviderError("FEDAPAY_ENV must be live in production mode")

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
        # FedaPay n'accepte que des montants entiers en XOF
        xof_amount = int(amount)

        webhook_url = (
            f"{config.settings.payment_webhook_base_url}/api/payments/webhook/fedapay"
        )

        payload = {
            "description": task_description[:255],
            "amount": xof_amount,
            "currency": {"iso": currency or "XOF"},
            "callback_url": config.settings.payment_redirect_url,
            "customer": {"email": user_email} if user_email else {},
            "meta": {
                "user_id": user_id,
                "escrow_id": escrow_id,
                "task_id": task_id,
                "country_code": country_code,
                "idempotency_key": idempotency_key,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{_base_url()}/transactions",
                    headers=_headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("FedaPay API HTTP error: {} — {}", exc.response.status_code, exc.response.text)
            raise PaymentProviderError(f"FedaPay erreur {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("FedaPay connexion échouée: {}", exc)
            raise PaymentProviderError("FedaPay inaccessible") from exc

        try:
            tx_data = data.get("v_transaction", data)
            tx_id = str(tx_data.get("id", ""))
            token = tx_data.get("token", "")
            # URL de paiement FedaPay : https://[env]-app.fedapay.com/payment/token/{token}
            if config.settings.fedapay_env == "live":
                payment_url = f"https://app.fedapay.com/payment/token/{token}"
            else:
                payment_url = f"https://sandbox-app.fedapay.com/payment/token/{token}"
        except (KeyError, TypeError) as exc:
            logger.error("FedaPay réponse inattendue: {}", data)
            raise PaymentProviderError("FedaPay réponse mal formée") from exc

        logger.info(
            "FedaPay transaction créée — tx={} escrow={} amount={} XOF",
            tx_id, escrow_id, xof_amount,
        )
        return PaymentIntentResult(
            provider_intent_id=tx_id,
            provider="fedapay",
            amount=amount,
            currency=currency or "XOF",
            client_secret=None,
            payment_url=payment_url,
            escrow_id=escrow_id,
            idempotency_key=idempotency_key,
        )

    async def verify_webhook(
        self,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookEvent:
        sig_header = (
            headers.get("fedapay-signature")
            or headers.get("FedaPay-Signature")
            or ""
        )

        if config.settings.payment_mode != "mock" and not config.settings.fedapay_webhook_secret:
            raise PaymentProviderError("FEDAPAY_WEBHOOK_SECRET non configurée")
        if config.settings.fedapay_webhook_secret:
            if not sig_header:
                raise InvalidWebhookSignature("Header FedaPay-Signature absent")
            if not _verify_fedapay_signature(raw_body, sig_header, config.settings.fedapay_webhook_secret):
                raise InvalidWebhookSignature("Signature FedaPay invalide")

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise InvalidWebhookSignature("Webhook FedaPay : JSON invalide") from exc

        # FedaPay webhook payload :
        # { "name": "transaction.approved", "data": { "object": { ... } } }
        event_name: str = body.get("name", "")
        tx_data: dict = body.get("data", {}).get("object", body.get("data", {}))

        tx_id = str(tx_data.get("id", ""))
        status: str = tx_data.get("status", "")
        meta: dict = tx_data.get("meta", {})
        raw_amount: int = tx_data.get("amount", 0)
        currency_data = tx_data.get("currency", {})
        currency: str = (
            currency_data.get("iso", "XOF") if isinstance(currency_data, dict) else "XOF"
        )
        escrow_id: str = meta.get("escrow_id", "")

        if event_name in ("transaction.approved",) or status == "approved":
            # Wallet top-up (pas d'escrow)
            if meta.get("type") == "wallet_topup":
                logger.info("FedaPay topup approved — tx={} user={}", tx_id, meta.get("user_id"))
                return WebhookEvent(
                    event_type="wallet_topup",
                    provider_tx_id=tx_id,
                    escrow_id="",
                    amount=Decimal(raw_amount),
                    currency=currency,
                    raw_data={
                        "stripe_event_id": f"fedapay:{tx_id}",
                        **meta,
                        "provider_tx_id": tx_id,
                    },
                )
            logger.info("FedaPay webhook approved — tx={} escrow={}", tx_id, escrow_id)
            return WebhookEvent(
                event_type="payment.success",
                provider_tx_id=tx_id,
                escrow_id=escrow_id,
                amount=Decimal(raw_amount),
                currency=currency,
                raw_data=body,
            )

        if event_name in ("transaction.declined", "transaction.canceled") or status in (
            "declined", "canceled", "failed"
        ):
            logger.warning("FedaPay webhook failed — tx={} escrow={} status={}", tx_id, escrow_id, status)
            return WebhookEvent(
                event_type="payment.failed",
                provider_tx_id=tx_id,
                escrow_id=escrow_id,
                amount=Decimal(raw_amount),
                currency=currency,
                raw_data=body,
            )

        return WebhookEvent(
            event_type="unhandled",
            provider_tx_id=tx_id,
            escrow_id=escrow_id,
            amount=Decimal("0"),
            currency=currency,
            raw_data=body,
        )

