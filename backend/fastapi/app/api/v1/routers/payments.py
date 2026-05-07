from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_country_code,
    get_current_user_id,
    get_db,
    get_payment_service,
    get_wallet_service,
)
from app.core.config import settings
from app.core.country_engine import PaymentRouterService
from app.core.country_engine.definitions import get_config
from app.core.redis_client import redis_sync
from app.core.observability import logger
from app.core.responses import success_response
from app.models.task import Task
from app.models.user import User
from app.payment.audit_logger import FinancialAuditLogger
from app.payment.idempotency import IdempotencyError, IdempotencyService
from app.payment.limits import TransactionLimits
from app.payment.providers import get_payment_provider
from app.payment.safety_layer import PaymentSafetyError, PaymentSafetyLayer
from app.services.payment import (
    InvalidWebhookSignature,
    MockProvider,
    PaymentProviderError,
    UnsupportedCountryError,
    WebhookEvent,
    list_supported_countries,
)
from app.services.payment.fedapay_provider import FedaPayProvider
from app.services.payment.flutterwave_provider import FlutterwaveProvider
from app.services.payment.stripe_provider import StripeProvider
from app.services.payment_service import PaymentService
from app.services.payment.webhook_queue import QueuedWebhookEvent, WebhookQueue
from app.services.wallet_service import EscrowError, WalletService
from app.core.country_engine.feature_engine import FeatureFlagEngine
from app.worker.celery_app import celery_app as _celery_app


_SENSITIVE_KEYS = frozenset({
    "card_number", "cvv", "expiry", "pan", "pin", "password",
    "secret", "authorization", "token", "key",
})


def _safe_log_payload(data: dict) -> dict:
    """Return a copy of webhook payload with sensitive fields masked."""
    out: dict = {}
    for k, v in data.items():
        k_low = k.lower()
        if any(s in k_low for s in _SENSITIVE_KEYS):
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _safe_log_payload(v)
        elif isinstance(v, str) and len(v) > 200:
            out[k] = v[:200] + "...[truncated]"
        else:
            out[k] = v
    return out

router = APIRouter(prefix="/payments", tags=["payments"])


class CreateIntentPayload(BaseModel):
    task_id: str = Field(min_length=1)


class MockTriggerPayload(BaseModel):
    escrow_id: str = Field(min_length=1)


def _require_mock_mode() -> None:
    mode = PaymentSafetyLayer.resolve_mode().value
    if mode != "mock":
        raise HTTPException(status_code=403, detail=f"mock endpoints disabled in mode '{mode}'")


def _assert_payments_enabled() -> None:
    if settings.payments_disabled:
        raise HTTPException(status_code=503, detail="Payments are globally disabled")


def _payments_rate_limit(bucket: str, limit: int = 60, window_seconds: int = 60) -> None:
    key = f"rl:payments:{bucket}"
    n = redis_sync.incr(key)
    if n == 1:
        redis_sync.expire(key, window_seconds + 5)
    if n > limit:
        raise HTTPException(status_code=429, detail="Too many payment requests")


def _is_real_money_enabled(db: Session, country_code: str) -> bool:
    # Global env switch + feature flag per country.
    if not settings.real_money_enabled:
        return False
    return FeatureFlagEngine(redis_sync, db).get_flag(country_code, "real_money_enabled")


def _assert_webhook_secret_configured(provider_name: str) -> None:
    if PaymentSafetyLayer.resolve_mode().value == "mock":
        return
    if provider_name == "stripe" and not settings.stripe_webhook_secret.strip():
        raise HTTPException(status_code=500, detail="Stripe webhook secret missing")
    if provider_name == "fedapay" and not settings.fedapay_webhook_secret.strip():
        raise HTTPException(status_code=500, detail="FedaPay webhook secret missing")
    if provider_name == "flutterwave" and not settings.flutterwave_hash.strip():
        raise HTTPException(status_code=500, detail="Flutterwave webhook hash missing")


def _require_dev_mode() -> None:
    """Backward-compatible alias expected by legacy tests."""
    mode = str(settings.payment_mode).strip().lower()
    if mode not in {"dev", "mock"}:
        raise HTTPException(status_code=403, detail=f"mock endpoints disabled in mode '{mode}'")


@router.post("/create-intent")
async def create_intent(
    payload: CreateIntentPayload,
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    country_code: str = Depends(get_country_code),
    wallet_svc: WalletService = Depends(get_wallet_service),
):
    _assert_payments_enabled()
    _payments_rate_limit(f"intent:{user_id}", limit=20)

    if not x_idempotency_key and settings.payment_mode in {"production", "sandbox"}:
        raise HTTPException(status_code=400, detail="X-Idempotency-Key header is required in sandbox/production")
    if not x_idempotency_key:
        x_idempotency_key = f"dev-{uuid.uuid4().hex}"

    task = db.get(Task, payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tache introuvable")

    amount = Decimal(str(task.price))
    currency = (task.currency or "EUR").upper()

    safety = PaymentSafetyLayer(db)
    try:
        safety.assert_create_payment_safe(
            user_id=user_id,
            country_code=country_code,
            amount=amount,
            currency=currency,
            idempotency_key=x_idempotency_key,
        )
    except PaymentSafetyError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    user = db.get(User, user_id)
    user_email = (user.email if user else "") or ""
    real_money_enabled = _is_real_money_enabled(db, country_code.upper())

    idempotency = IdempotencyService(ttl_seconds=180)
    payload_fingerprint = f"{user_id}|{amount}|{currency}|{country_code}|{get_config(country_code).payment_providers[0]}"
    try:
        with idempotency.lock(x_idempotency_key, payload_fingerprint):
            escrow = wallet_svc.create_pending_escrow(
                task_id=payload.task_id,
                payer_id=user_id,
                payee_id=task.assigned_to,
                amount=amount,
                currency=currency,
            )
            wallet_svc.lock_funds(escrow.id)

            provider = get_payment_provider(
                payment_mode=("mock" if not real_money_enabled else settings.payment_mode),
                country_code=country_code,
            )
            result = await provider.create_payment(
                amount=amount,
                currency=currency,
                user_id=user_id,
                user_email=user_email,
                metadata={
                    "escrow_id": escrow.id,
                    "task_id": payload.task_id,
                    "task_description": str(getattr(task, "description", None) or getattr(task, "title", "Tache ZASKA")),
                    "country_code": country_code,
                },
                idempotency_key=x_idempotency_key,
            )
            cfg_provider = get_config(country_code).payment_providers[0]
            safety.assert_provider_mode_keys(cfg_provider)

            FinancialAuditLogger.log(
                action="intent_created",
                user_id=user_id,
                payment_id=result.payment_id,
                amount=amount,
                currency=currency,
                provider=result.provider,
                status=result.status,
            )
    except IdempotencyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur provider: {exc}")
    except UnsupportedCountryError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    commission = PaymentRouterService.compute_commission(amount, country_code)
    return success_response(
        {
            "mode": PaymentSafetyLayer.resolve_mode().value,
            "real_money_enabled": real_money_enabled,
            "provider": result.provider,
            "provider_intent_id": result.payment_id,
            "client_secret": result.raw.get("client_secret"),
            "payment_url": result.raw.get("payment_url"),
            "escrow_id": escrow.id,
            "amount": str(result.amount),
            "currency": result.currency,
            "commission": commission["commission"],
            "escrow_amount": commission["escrow_amount"],
            "idempotency_key": x_idempotency_key,
        }
    )


@router.post("/mock/success")
async def mock_success(
    payload: MockTriggerPayload,
    user_id: str = Depends(get_current_user_id),
    wallet_svc: WalletService = Depends(get_wallet_service),
):
    _require_mock_mode()
    provider = MockProvider()
    event = WebhookEvent(
        event_type="payment.success",
        provider_tx_id=f"mock_{uuid.uuid4().hex[:12]}",
        escrow_id=payload.escrow_id,
        amount=Decimal("0"),
        currency="",
        raw_data={"simulated": True, "triggered_by": user_id},
    )
    await provider.handle_success(event, wallet_svc)
    wallet_svc.finalize_transaction(payload.escrow_id)
    return success_response({"escrow_id": payload.escrow_id, "status": "funded", "mode": "mock"})


@router.post("/mock/failure")
async def mock_failure(
    payload: MockTriggerPayload,
    user_id: str = Depends(get_current_user_id),
    wallet_svc: WalletService = Depends(get_wallet_service),
):
    _require_mock_mode()
    provider = MockProvider()
    event = WebhookEvent(
        event_type="payment.failed",
        provider_tx_id=f"mock_fail_{uuid.uuid4().hex[:12]}",
        escrow_id=payload.escrow_id,
        amount=Decimal("0"),
        currency="",
        raw_data={"simulated": True, "triggered_by": user_id},
    )
    await provider.handle_failure(event, wallet_svc)
    wallet_svc.finalize_transaction(payload.escrow_id)
    return success_response({"escrow_id": payload.escrow_id, "status": "cancelled", "mode": "mock"})


async def _handle_webhook(provider, raw_body: bytes, headers: dict[str, str], wallet_svc: WalletService):
    event = await provider.verify_webhook(raw_body, headers)
    return event


def _credit_wallet_from_topup_event(
    event: WebhookEvent,
    wallet_svc: WalletService,
    provider_name: str,
    db: "Session | None" = None,
) -> tuple[bool, str]:
    """
    Crédite le wallet suite à un événement wallet_topup vérifié.
    Idempotent — marks BEFORE crediting to prevent double-credit on retry.

    Returns (processed: bool, idem_key: str).
    """
    stripe_event_id: str = event.raw_data.get("stripe_event_id") or event.provider_tx_id
    idem_key = f"{provider_name}:topup:{stripe_event_id}"

    if WebhookQueue.is_processed(idem_key, db=db):
        return False, idem_key

    user_id_meta: str = event.raw_data.get("user_id", "")
    currency_meta: str = event.raw_data.get("currency", "")
    reference: str = event.raw_data.get("reference", event.provider_tx_id)

    if not user_id_meta or not currency_meta or event.amount <= Decimal("0"):
        logger.warning(
            "webhook:topup_missing_metadata provider={} idem_key={} payload={}",
            provider_name, idem_key, _safe_log_payload(event.raw_data),
        )
        return True, idem_key

    # Credit FIRST: if the credit fails the webhook is not marked processed and
    # the provider can retry safely. The reverse order (mark before credit) would
    # permanently lose the user's funds on any DB error between the two calls.
    # Double-credit on crash is detectable via audit log and correctable; lost
    # funds are not.
    wallet_svc.credit_wallet(
        user_id=user_id_meta,
        currency=currency_meta,
        amount=event.amount,
        reference=reference,
        provider=provider_name,
        metadata={"type": "wallet_topup", "provider_tx_id": event.provider_tx_id},
    )
    WebhookQueue.mark_processed(idem_key, db=db, provider=provider_name, event_type="wallet_topup")

    # Record deposit timestamp so rapid deposit→withdraw detection works
    _limits = TransactionLimits(
        fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof))
    )
    _limits.record_deposit_timestamp(user_id=user_id_meta)

    FinancialAuditLogger.log(
        action="wallet_topup",
        user_id=user_id_meta,
        payment_id=event.provider_tx_id,
        amount=event.amount,
        currency=currency_meta,
        provider=provider_name,
        status="completed",
    )
    logger.info(
        "deposit:confirmed provider={} user={} amount={} {} ref={}",
        provider_name, user_id_meta, event.amount, currency_meta, reference,
    )
    return True, idem_key


@router.post("/webhook/stripe", include_in_schema=False)
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:stripe", limit=180)
    _assert_webhook_secret_configured("stripe")
    raw_body = await request.body()
    headers = dict(request.headers)
    wallet_svc = WalletService(db)
    try:
        provider = StripeProvider()
        event = await _handle_webhook(provider, raw_body, headers, wallet_svc)

        # ── Reject unknown / unhandled events ─────────────────────────────────
        if event.event_type == "unhandled":
            logger.warning(
                "webhook:stripe_unknown_event provider_tx={} payload={}",
                event.provider_tx_id, _safe_log_payload(event.raw_data),
            )
            return {"received": True, "ignored": True}

        # ── Wallet top-up (checkout.session.completed) ────────────────────────
        if event.event_type == "wallet_topup":
            processed, _ = _credit_wallet_from_topup_event(event, wallet_svc, "stripe", db=db)
            return {"received": True, "duplicate": not processed}

        # ── Escrow-based payment (PaymentIntent) ──────────────────────────────
        idem_key = f"stripe:{event.provider_tx_id}"
        if event.provider_tx_id and WebhookQueue.is_processed(idem_key):
            return {"received": True, "duplicate": True}
        WebhookQueue.enqueue(
            QueuedWebhookEvent(
                provider="stripe",
                raw_body=raw_body.decode("utf-8", errors="ignore"),
                headers=headers,
                idempotency_key=idem_key,
                request_id=request.headers.get("x-request-id", ""),
            )
        )
        try:
            _celery_app.send_task("app.workers.payment_webhook_worker.process_webhook")
        except Exception as _celery_err:
            logger.warning(
                "webhook:celery_unavailable provider=stripe — queued for drain: {}",
                _celery_err,
            )
    except InvalidWebhookSignature as exc:
        logger.warning("webhook:stripe_invalid_signature error={}", exc)
        FinancialAuditLogger.log(
            action="webhook_invalid",
            user_id="system",
            payment_id="",
            amount=Decimal("0"),
            currency="",
            provider="stripe",
            status="invalid_signature",
        )
        raise HTTPException(status_code=400, detail="Signature invalide")
    except PaymentProviderError as exc:
        logger.error("webhook:stripe_provider_error error={}", exc)
        raise HTTPException(status_code=500, detail="Configuration provider")

    FinancialAuditLogger.log(
        action="payment_success" if event.event_type == "payment.success" else "payment_failed",
        user_id="system",
        payment_id=event.provider_tx_id,
        amount=event.amount,
        currency=event.currency,
        provider="stripe",
        status=event.event_type,
    )
    return {"received": True}


@router.post("/webhook/fedapay", include_in_schema=False)
async def webhook_fedapay(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:fedapay", limit=180)
    _assert_webhook_secret_configured("fedapay")
    raw_body = await request.body()
    headers = dict(request.headers)
    wallet_svc = WalletService(db)
    try:
        provider = FedaPayProvider()
        event = await _handle_webhook(provider, raw_body, headers, wallet_svc)

        # ── Reject unknown / unhandled events ─────────────────────────────
        if event.event_type == "unhandled":
            logger.warning(
                "webhook:fedapay_unknown_event provider_tx={} payload={}",
                event.provider_tx_id, _safe_log_payload(event.raw_data),
            )
            return {"received": True, "ignored": True}

        # ── Wallet top-up ──────────────────────────────────────────────────
        if event.event_type == "wallet_topup":
            processed, _ = _credit_wallet_from_topup_event(event, wallet_svc, "fedapay", db=db)
            return {"received": True, "duplicate": not processed}

        # ── Escrow-based payment ───────────────────────────────────────────
        idem_key = f"fedapay:{event.provider_tx_id}"
        if event.provider_tx_id and WebhookQueue.is_processed(idem_key, db=db):
            return {"received": True, "duplicate": True}
        WebhookQueue.enqueue(
            QueuedWebhookEvent(
                provider="fedapay",
                raw_body=raw_body.decode("utf-8", errors="ignore"),
                headers=headers,
                idempotency_key=idem_key,
                request_id=request.headers.get("x-request-id", ""),
            )
        )
        try:
            _celery_app.send_task("app.workers.payment_webhook_worker.process_webhook")
        except Exception as _celery_err:
            logger.warning(
                "webhook:celery_unavailable provider=fedapay — queued for drain: {}",
                _celery_err,
            )
    except InvalidWebhookSignature as exc:
        logger.warning("webhook:fedapay_invalid_signature error={}", exc)
        FinancialAuditLogger.log(
            action="webhook_invalid",
            user_id="system",
            payment_id="",
            amount=Decimal("0"),
            currency="",
            provider="fedapay",
            status="invalid_signature",
        )
        raise HTTPException(status_code=400, detail="Signature invalide")
    except PaymentProviderError as exc:
        logger.error("webhook:fedapay_provider_error error={}", exc)
        raise HTTPException(status_code=500, detail="Configuration provider")

    FinancialAuditLogger.log(
        action="payment_success" if event.event_type == "payment.success" else "payment_failed",
        user_id="system",
        payment_id=event.provider_tx_id,
        amount=event.amount,
        currency=event.currency,
        provider="fedapay",
        status=event.event_type,
    )
    return {"received": True}


@router.post("/webhook/flutterwave", include_in_schema=False)
async def webhook_flutterwave(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:flutterwave", limit=180)
    _assert_webhook_secret_configured("flutterwave")
    raw_body = await request.body()
    headers = dict(request.headers)
    wallet_svc = WalletService(db)
    try:
        provider = FlutterwaveProvider()
        event = await _handle_webhook(provider, raw_body, headers, wallet_svc)

        # ── Reject unknown / unhandled events ─────────────────────────────
        if event.event_type == "unhandled":
            logger.warning(
                "webhook:flutterwave_unknown_event provider_tx={} payload={}",
                event.provider_tx_id, _safe_log_payload(event.raw_data),
            )
            return {"received": True, "ignored": True}

        # ── Wallet top-up ──────────────────────────────────────────────────
        if event.event_type == "wallet_topup":
            processed, _ = _credit_wallet_from_topup_event(event, wallet_svc, "flutterwave", db=db)
            return {"received": True, "duplicate": not processed}

        # ── Escrow-based payment ───────────────────────────────────────────
        idem_key = f"flutterwave:{event.provider_tx_id}"
        if event.provider_tx_id and WebhookQueue.is_processed(idem_key, db=db):
            return {"received": True, "duplicate": True}
        WebhookQueue.enqueue(
            QueuedWebhookEvent(
                provider="flutterwave",
                raw_body=raw_body.decode("utf-8", errors="ignore"),
                headers=headers,
                idempotency_key=idem_key,
                request_id=request.headers.get("x-request-id", ""),
            )
        )
        try:
            _celery_app.send_task("app.workers.payment_webhook_worker.process_webhook")
        except Exception as _celery_err:
            logger.warning(
                "webhook:celery_unavailable provider=flutterwave — queued for drain: {}",
                _celery_err,
            )
    except InvalidWebhookSignature as exc:
        logger.warning("webhook:flutterwave_invalid_signature error={}", exc)
        FinancialAuditLogger.log(
            action="webhook_invalid",
            user_id="system",
            payment_id="",
            amount=Decimal("0"),
            currency="",
            provider="flutterwave",
            status="invalid_signature",
        )
        raise HTTPException(status_code=400, detail="Signature invalide")
    except PaymentProviderError as exc:
        logger.error("webhook:flutterwave_provider_error error={}", exc)
        raise HTTPException(status_code=500, detail="Configuration provider")

    FinancialAuditLogger.log(
        action="payment_success" if event.event_type == "payment.success" else "payment_failed",
        user_id="system",
        payment_id=event.provider_tx_id,
        amount=event.amount,
        currency=event.currency,
        provider="flutterwave",
        status=event.event_type,
    )
    return {"received": True}


@router.get("/mode")
def payment_mode(user_id: str = Depends(get_current_user_id)):
    _ = user_id
    mode = PaymentSafetyLayer.resolve_mode().value
    return success_response({"mode": mode, "mock_available": mode == "mock"})


@router.get("/methods")
def payment_methods(
    service: PaymentService = Depends(get_payment_service),
    user_id: str = Depends(get_current_user_id),
):
    methods = service.list_methods(user_id=user_id)
    return success_response(
        [{"id": m.id, "type": m.method_type, "details": m.details, "isDefault": m.is_default} for m in methods]
    )


@router.get("/route")
def payment_route(
    country_code: str = Depends(get_country_code),
    user_id: str = Depends(get_current_user_id),
):
    _ = user_id
    route = PaymentRouterService.route_payment(country_code, 0, "")
    return success_response(route.model_dump())


@router.get("/supported")
def supported_countries(user_id: str = Depends(get_current_user_id)):
    _ = user_id
    return success_response(list_supported_countries())

