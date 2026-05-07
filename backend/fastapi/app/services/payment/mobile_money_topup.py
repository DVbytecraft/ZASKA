"""
Mobile Money wallet top-up (NOT escrow).

Crée une demande de paiement FedaPay ou Flutterwave pour recharger
directement un wallet ZASKA.

Flow:
  1. POST /wallet/deposit {amount, currency, provider:"mobile_money"}
  2. Backend appelle create_mobile_money_topup() → retourne payment_url
  3. Client redirige vers payment_url
  4. Provider envoie webhook avec meta.type="wallet_topup"
  5. Webhook handler crédite le wallet

Routing par pays:
  - zone CFA (TG, SN, BJ, CI…) → FedaPay
  - Ghana, Nigeria, Kenya…       → Flutterwave
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import httpx

from app.core import config
from app.core.observability import logger

from .base_provider import PaymentProviderError


# ── FedaPay ───────────────────────────────────────────────────────────────────

_FEDAPAY_SANDBOX = "https://sandbox-api.fedapay.com/v1"
_FEDAPAY_LIVE = "https://api.fedapay.com/v1"

# Pays utilisant FedaPay (zone UEMOA/CFA)
_FEDAPAY_COUNTRIES = {"TG", "SN", "BJ", "CI", "ML", "BF", "NE", "GW"}

# Pays utilisant Flutterwave
_FLUTTERWAVE_COUNTRIES = {"GH", "NG", "KE", "ZA", "TZ", "UG", "RW"}


def _fedapay_base() -> str:
    return _FEDAPAY_LIVE if config.settings.fedapay_env == "live" else _FEDAPAY_SANDBOX


def _fedapay_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.settings.fedapay_api_key}",
        "Content-Type": "application/json",
    }


def _flutterwave_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.settings.flutterwave_secret_key}",
        "Content-Type": "application/json",
    }


# ── Public entry point ────────────────────────────────────────────────────────

async def create_mobile_money_topup(
    *,
    user_id: str,
    user_email: str,
    amount: Decimal,
    currency: str,
    country_code: str,
    reference: str,
) -> dict[str, Any]:
    """
    Crée un paiement Mobile Money pour wallet top-up.

    Returns:
        {
            "provider": "fedapay" | "flutterwave",
            "payment_url": str,
            "provider_tx_id": str,
            "reference": str,
            "amount": str,
            "currency": str,
        }
    """
    cc = country_code.upper()

    if cc in _FLUTTERWAVE_COUNTRIES:
        if not config.settings.flutterwave_secret_key:
            raise PaymentProviderError(
                "FLUTTERWAVE_SECRET_KEY non configurée pour les pays Flutterwave"
            )
        return await _flutterwave_topup(
            user_id=user_id, user_email=user_email,
            amount=amount, currency=currency,
            country_code=cc, reference=reference,
        )

    # Fallback : FedaPay (zone CFA + défaut)
    if not config.settings.fedapay_api_key:
        raise PaymentProviderError(
            "FEDAPAY_API_KEY non configurée pour le pays {}".format(cc)
        )
    return await _fedapay_topup(
        user_id=user_id, user_email=user_email,
        amount=amount, currency=currency,
        country_code=cc, reference=reference,
    )


# ── FedaPay ───────────────────────────────────────────────────────────────────

async def _fedapay_topup(
    *,
    user_id: str,
    user_email: str,
    amount: Decimal,
    currency: str,
    country_code: str,
    reference: str,
) -> dict[str, Any]:
    redirect_url = config.settings.payment_redirect_url.replace(
        "/success", "/wallet?status=success"
    )
    # Patch propre : si payment_redirect_url pointe vers /wallet déjà, on l'utilise tel quel
    if "/wallet" in config.settings.payment_redirect_url:
        redirect_url = config.settings.payment_redirect_url

    payload = {
        "description": f"ZASKA wallet top-up — {reference}",
        "amount": int(amount),  # FedaPay accepte uniquement entiers XOF
        "currency": {"iso": currency or "XOF"},
        "callback_url": redirect_url,
        "customer": ({"email": user_email} if user_email else {}),
        "meta": {
            "type": "wallet_topup",
            "user_id": user_id,
            "currency": currency or "XOF",
            "amount": str(amount),
            "reference": reference,
            "country_code": country_code,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_fedapay_base()}/transactions",
                headers=_fedapay_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("FedaPay topup HTTP {}: {}", exc.response.status_code, exc.response.text[:300])
        raise PaymentProviderError(f"FedaPay erreur {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.error("FedaPay topup connexion: {}", exc)
        raise PaymentProviderError("FedaPay inaccessible") from exc

    tx_data = data.get("v_transaction", data)
    tx_id = str(tx_data.get("id", ""))
    token = tx_data.get("token", "")
    if not token:
        logger.error("FedaPay topup: token manquant dans réponse {}", data)
        raise PaymentProviderError("FedaPay réponse incomplète (token manquant)")

    if config.settings.fedapay_env == "live":
        payment_url = f"https://app.fedapay.com/payment/token/{token}"
    else:
        payment_url = f"https://sandbox-app.fedapay.com/payment/token/{token}"

    logger.info(
        "FedaPay topup créé — tx={} user={} amount={} {}",
        tx_id, user_id, amount, currency,
    )
    return {
        "provider": "fedapay",
        "payment_url": payment_url,
        "provider_tx_id": tx_id,
        "reference": reference,
        "amount": str(amount),
        "currency": currency or "XOF",
    }


# ── Flutterwave ───────────────────────────────────────────────────────────────

_FLW_BASE = "https://api.flutterwave.com/v3"

# Devise par défaut selon le pays
_FLW_CURRENCY: dict[str, str] = {
    "GH": "GHS", "NG": "NGN", "KE": "KES",
    "ZA": "ZAR", "TZ": "TZS", "UG": "UGX", "RW": "RWF",
}


async def _flutterwave_topup(
    *,
    user_id: str,
    user_email: str,
    amount: Decimal,
    currency: str,
    country_code: str,
    reference: str,
) -> dict[str, Any]:
    effective_currency = currency or _FLW_CURRENCY.get(country_code, "USD")
    redirect_url = config.settings.payment_redirect_url

    payload = {
        "tx_ref": reference,
        "amount": float(str(amount)),
        "currency": effective_currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": user_email or f"{user_id}@zaska.app",
            "name": user_id,
        },
        "meta": {
            "type": "wallet_topup",
            "user_id": user_id,
            "currency": effective_currency,
            "amount": str(amount),
            "reference": reference,
            "country_code": country_code,
        },
        "customizations": {
            "title": "ZASKA Wallet",
            "description": f"Recharge {effective_currency} — {reference[:20]}",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_FLW_BASE}/payments",
                headers=_flutterwave_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Flutterwave topup HTTP {}: {}", exc.response.status_code, exc.response.text[:300])
        raise PaymentProviderError(f"Flutterwave erreur {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.error("Flutterwave topup connexion: {}", exc)
        raise PaymentProviderError("Flutterwave inaccessible") from exc

    if data.get("status") != "success":
        msg = data.get("message", "Flutterwave erreur inconnue")
        logger.error("Flutterwave topup création échouée: {}", msg)
        raise PaymentProviderError(msg)

    link_data = data.get("data", {})
    payment_url: str = link_data.get("link", "")
    flw_ref: str = str(link_data.get("id", reference))

    logger.info(
        "Flutterwave topup créé — ref={} user={} amount={} {}",
        flw_ref, user_id, amount, effective_currency,
    )
    return {
        "provider": "flutterwave",
        "payment_url": payment_url,
        "provider_tx_id": flw_ref,
        "reference": reference,
        "amount": str(amount),
        "currency": effective_currency,
    }


# ── Payout (Mobile Money withdrawal) ─────────────────────────────────────────

async def execute_mobile_money_payout(
    *,
    user_id: str,
    amount: Decimal,
    currency: str,
    provider: str,
    phone_number: str,
    country_code: str,
    reference: str,
) -> dict[str, Any]:
    """
    Exécute un virement Mobile Money (payout).
    Appelé APRÈS débit du wallet — si cette fonction échoue, le caller doit re-créditer.

    Returns:
        {"status": "completed" | "pending", "provider_tx_id": str, "provider": str}
    """
    cc = country_code.upper()
    prov = provider.lower()

    if prov in ("flutterwave",) or cc in _FLUTTERWAVE_COUNTRIES:
        return await _flutterwave_payout(
            user_id=user_id, amount=amount, currency=currency,
            phone_number=phone_number, country_code=cc, reference=reference,
        )

    # Default: FedaPay
    return await _fedapay_payout(
        user_id=user_id, amount=amount, currency=currency,
        phone_number=phone_number, country_code=cc, reference=reference,
    )


async def _fedapay_payout(
    *,
    user_id: str,
    amount: Decimal,
    currency: str,
    phone_number: str,
    country_code: str,
    reference: str,
) -> dict[str, Any]:
    """FedaPay Payout — POST /v1/payouts"""
    payload = {
        "amount": int(amount),
        "currency": {"iso": currency or "XOF"},
        "description": f"ZASKA payout — {reference}",
        "customer": {"phone_number": phone_number},
        "mode": "mtn",  # FedaPay auto-detect selon préfixe
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_fedapay_base()}/payouts",
                headers=_fedapay_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("FedaPay payout HTTP {}: {}", exc.response.status_code, exc.response.text[:300])
        raise PaymentProviderError(
            f"FedaPay payout erreur {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.RequestError as exc:
        logger.error("FedaPay payout connexion: {}", exc)
        raise PaymentProviderError("FedaPay inaccessible") from exc

    payout_data = data.get("v_payout", data)
    payout_id = str(payout_data.get("id", ""))
    status = str(payout_data.get("status", "pending"))

    logger.info(
        "FedaPay payout envoyé — payout_id={} user={} amount={} {} status={}",
        payout_id, user_id, amount, currency, status,
    )
    return {
        "status": "completed" if status in ("sent", "approved") else "pending",
        "provider_tx_id": payout_id,
        "provider": "fedapay",
    }


async def _flutterwave_payout(
    *,
    user_id: str,
    amount: Decimal,
    currency: str,
    phone_number: str,
    country_code: str,
    reference: str,
) -> dict[str, Any]:
    """Flutterwave Transfer — POST /v3/transfers"""
    # Flutterwave accepts decimal amounts; use str→float to avoid binary float drift
    amount_float = float(str(amount))
    webhook_url = (
        f"{config.settings.payment_webhook_base_url.rstrip('/')}"
        "/api/payments/webhook/flutterwave"
    )
    payload = {
        "account_bank": "MPS",  # Mobile Money (auto-detect by country)
        "account_number": phone_number,
        "amount": amount_float,
        "narration": f"ZASKA payout {reference}",
        "currency": currency,
        "reference": reference,
        "callback_url": webhook_url,
        "debit_currency": currency,
        "meta": [
            {"sender": "ZASKA"},
            {"user_id": user_id},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_FLW_BASE}/transfers",
                headers=_flutterwave_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Flutterwave transfer HTTP {}: {}",
            exc.response.status_code, exc.response.text[:300],
        )
        raise PaymentProviderError(
            f"Flutterwave transfer erreur {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Flutterwave transfer connexion: {}", exc)
        raise PaymentProviderError("Flutterwave inaccessible") from exc

    if data.get("status") != "success":
        msg = data.get("message", "Flutterwave transfer erreur inconnue")
        logger.error("Flutterwave transfer échoué: {}", msg)
        raise PaymentProviderError(msg)

    tx_data = data.get("data", {})
    flw_id = str(tx_data.get("id", ""))
    status_str = str(tx_data.get("status", "PENDING")).upper()

    logger.info(
        "Flutterwave transfer envoyé — id={} user={} amount={} {} status={}",
        flw_id, user_id, amount, currency, status_str,
    )
    return {
        "status": "completed" if status_str == "SUCCESSFUL" else "pending",
        "provider_tx_id": flw_id,
        "provider": "flutterwave",
    }
