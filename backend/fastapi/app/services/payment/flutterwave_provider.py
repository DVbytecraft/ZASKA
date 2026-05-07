"""
Flutterwave provider — Ghana / Nigeria / Kenya / Afrique anglophone.

Méthodes supportées :
  - Mobile Money Ghana   (GHS, MTN MoMo)
  - Mobile Money (NGN, KES, TZS…)
  - Card  (fallback)

API REST Flutterwave v3 :
  Base URL : https://api.flutterwave.com/v3
  Auth     : Authorization: Bearer {FLW_SECRET_KEY}

Flux paiement :
  1. POST /payments             → retourne hosted payment URL
  2. Utilisateur paie sur l'interface Flutterwave
  3. Flutterwave POST webhook   → verify_webhook() → WebhookEvent

Vérification webhook Flutterwave :
  Header : verif-hash: {FLW_HASH}
  Comparaison directe avec FLUTTERWAVE_HASH env var.
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

_BASE_URL = "https://api.flutterwave.com/v3"

# Devises par défaut selon le pays
_COUNTRY_CURRENCY: dict[str, str] = {
    "GH": "GHS",
    "NG": "NGN",
    "KE": "KES",
    "ZA": "ZAR",
    "TZ": "TZS",
    "UG": "UGX",
    "RW": "RWF",
}

# Type de charge selon le pays
_CHARGE_TYPE: dict[str, str] = {
    "GH": "mobile_money_ghana",
    "NG": "ussd",
    "KE": "mobile_money_kenya",
    "TZ": "mobile_money_tanzania",
    "UG": "mobile_money_uganda",
    "RW": "mobile_money_rwanda",
    "ZA": "card",
}


def _flw_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.settings.flutterwave_secret_key}",
        "Content-Type": "application/json",
    }


class FlutterwaveProvider(PaymentProvider):
    PROVIDER_NAME = "flutterwave"

    def __init__(self) -> None:
        if not config.settings.flutterwave_secret_key:
            raise PaymentProviderError(
                "FLUTTERWAVE_SECRET_KEY non configurée — vérifier les variables d'environnement"
            )

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
        effective_currency = currency or _COUNTRY_CURRENCY.get(cc, "USD")

        # Hosted Payment Link — méthode universelle Flutterwave (supporte MoMo + carte)
        payload = {
            "tx_ref": idempotency_key,
            "amount": float(amount),
            "currency": effective_currency,
            "redirect_url": config.settings.payment_redirect_url,
            "payment_plan": None,
            "meta": {
                "user_id": user_id,
                "escrow_id": escrow_id,
                "task_id": task_id,
                "country_code": cc,
            },
            "customer": {
                "email": user_email or f"{user_id}@zaska.app",
                "name": user_id,
            },
            "customizations": {
                "title": "ZASKA Pay",
                "description": task_description[:100],
                "logo": "",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{_BASE_URL}/payments",
                    headers=_flw_headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Flutterwave HTTP error: {} — {}", exc.response.status_code, exc.response.text
            )
            raise PaymentProviderError(f"Flutterwave erreur {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Flutterwave connexion échouée: {}", exc)
            raise PaymentProviderError("Flutterwave inaccessible") from exc

        if data.get("status") != "success":
            msg = data.get("message", "Flutterwave erreur inconnue")
            logger.error("Flutterwave création échouée: {}", msg)
            raise PaymentProviderError(msg)

        link_data = data.get("data", {})
        payment_url: str = link_data.get("link", "")
        flw_ref: str = str(link_data.get("id", idempotency_key))

        logger.info(
            "Flutterwave payment link créé — ref={} escrow={} amount={} {}",
            flw_ref, escrow_id, amount, effective_currency,
        )
        return PaymentIntentResult(
            provider_intent_id=flw_ref,
            provider="flutterwave",
            amount=amount,
            currency=effective_currency,
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
        # Flutterwave utilise un hash statique dans le header verif-hash
        verif_hash = headers.get("verif-hash", "")

        if config.settings.payment_mode != "mock" and not config.settings.flutterwave_hash:
            raise PaymentProviderError("FLUTTERWAVE_HASH non configurée")
        if config.settings.flutterwave_hash:
            if not verif_hash:
                raise InvalidWebhookSignature("Header verif-hash absent")
            if not hmac.compare_digest(verif_hash, config.settings.flutterwave_hash):
                raise InvalidWebhookSignature("Signature Flutterwave invalide")

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise InvalidWebhookSignature("Webhook Flutterwave : JSON invalide") from exc

        # Flutterwave webhook payload :
        # { "event": "charge.completed", "data": { ... } }
        event: str = body.get("event", "")
        data: dict = body.get("data", {})

        flw_ref = str(data.get("id", ""))
        status: str = (data.get("status") or "").lower()
        meta: dict = data.get("meta", {}) or {}

        # Récupération escrow_id depuis meta
        if isinstance(meta, list):
            # Flutterwave peut retourner meta comme liste de dicts [{metaname, metavalue}]
            meta_dict: dict[str, str] = {
                m.get("metaname", ""): m.get("metavalue", "")
                for m in meta if isinstance(m, dict)
            }
        else:
            meta_dict = meta

        escrow_id: str = meta_dict.get("escrow_id", "")
        raw_amount: float = float(data.get("amount", 0))
        currency: str = (data.get("currency") or "USD").upper()

        if event == "charge.completed" and status == "successful":
            # Wallet top-up (pas d'escrow)
            topup_type = meta_dict.get("type", "")
            if topup_type == "wallet_topup":
                logger.info(
                    "Flutterwave topup completed — ref={} user={}",
                    flw_ref, meta_dict.get("user_id"),
                )
                return WebhookEvent(
                    event_type="wallet_topup",
                    provider_tx_id=flw_ref,
                    escrow_id="",
                    amount=Decimal(str(raw_amount)),
                    currency=currency,
                    raw_data={
                        "stripe_event_id": f"flutterwave:{flw_ref}",
                        **meta_dict,
                        "provider_tx_id": flw_ref,
                    },
                )
            logger.info("Flutterwave webhook completed — ref={} escrow={}", flw_ref, escrow_id)
            return WebhookEvent(
                event_type="payment.success",
                provider_tx_id=flw_ref,
                escrow_id=escrow_id,
                amount=Decimal(str(raw_amount)),
                currency=currency,
                raw_data=body,
            )

        if status in ("failed", "cancelled", "error"):
            logger.warning(
                "Flutterwave webhook failed — ref={} escrow={} status={}", flw_ref, escrow_id, status
            )
            return WebhookEvent(
                event_type="payment.failed",
                provider_tx_id=flw_ref,
                escrow_id=escrow_id,
                amount=Decimal(str(raw_amount)),
                currency=currency,
                raw_data=body,
            )

        return WebhookEvent(
            event_type="unhandled",
            provider_tx_id=flw_ref,
            escrow_id=escrow_id,
            amount=Decimal("0"),
            currency=currency,
            raw_data=body,
        )

