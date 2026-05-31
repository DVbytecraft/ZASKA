from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

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
from app.core.country_engine.feature_engine import FeatureFlagEngine
from app.core.redis_client import redis_sync
from app.core.observability import logger
from app.core.responses import success_response
from app.payment.audit_logger import FinancialAuditLogger
from app.payment.limits import TransactionLimits
from app.payment.orchestrator import OrchestratorError, PaymentOrchestrator
from app.payment.safety_layer import PaymentSafetyLayer
from app.services.payment import (
    InvalidWebhookSignature,
    MockProvider,
    PaymentProviderError,
    WebhookEvent,
    list_supported_countries,
)
from app.services.payment.fedapay_provider import FedaPayProvider
from app.services.payment.flutterwave_provider import FlutterwaveProvider
from app.services.payment.paystack_provider import PaystackProvider
from app.services.payment.stripe_provider import StripeProvider
from app.services.payment_service import PaymentService
from app.services.payment.webhook_queue import QueuedWebhookEvent, WebhookQueue
from app.services.wallet_service import WalletService
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
    if provider_name == "paystack" and not settings.paystack_webhook_secret.strip():
        raise HTTPException(status_code=500, detail="Paystack webhook secret missing")


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

    orchestrator = PaymentOrchestrator(db=db, wallet_svc=wallet_svc)
    try:
        result = await orchestrator.execute(
            task_id=payload.task_id,
            user_id=user_id,
            country_code=country_code,
            idempotency_key=x_idempotency_key,
        )
    except OrchestratorError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))

    return success_response(
        {
            "mode": result.mode,
            "real_money_enabled": result.real_money_enabled,
            "provider": result.provider,
            "provider_intent_id": result.provider_intent_id,
            "client_secret": result.client_secret,
            "payment_url": result.payment_url,
            "escrow_id": result.escrow_id,
            "amount": str(result.amount),
            "currency": result.currency,
            "commission": result.commission,
            "escrow_amount": result.escrow_amount,
            "idempotency_key": result.idempotency_key,
            "region": result.region,
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
    Idempotent — uses atomic Redis SETNX claim to prevent double-credit under concurrency.

    Returns (processed: bool, idem_key: str).
    """
    stripe_event_id: str = event.raw_data.get("stripe_event_id") or event.provider_tx_id
    idem_key = f"{provider_name}:topup:{stripe_event_id}"

    # Fast path: obvious duplicate already in Redis or DB
    if WebhookQueue.is_processed(idem_key, db=db):
        return False, idem_key

    # Atomic SETNX claim — only one concurrent caller wins; others return duplicate
    if not WebhookQueue.claim(idem_key):
        return False, idem_key

    user_id_meta: str = event.raw_data.get("user_id", "")
    currency_meta: str = event.raw_data.get("currency", "")
    reference: str = event.raw_data.get("reference", event.provider_tx_id)

    if not user_id_meta or not currency_meta or event.amount <= Decimal("0"):
        logger.warning(
            "webhook:topup_missing_metadata provider={} idem_key={} payload={}",
            provider_name, idem_key, _safe_log_payload(event.raw_data),
        )
        # Keep claim — bad payload is permanently skipped, not retried
        return True, idem_key

    try:
        wallet_svc.credit_wallet(
            user_id=user_id_meta,
            currency=currency_meta,
            amount=event.amount,
            reference=reference,
            provider=provider_name,
            metadata={"type": "wallet_topup", "provider_tx_id": event.provider_tx_id},
        )
    except Exception:
        # Transient failure — release claim so the provider can retry
        WebhookQueue.unclaim(idem_key)
        raise

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


async def _dispatch_provider_webhook(
    *,
    provider_name: str,
    provider_instance: Any,
    request: Request,
    db: Session,
) -> dict:
    """
    Single webhook dispatcher — handles all three providers identically.

    Replaces three near-identical handlers (stripe/fedapay/flutterwave).
    All idempotency, queue, and audit logic lives here once.
    """
    raw_body = await request.body()
    headers = dict(request.headers)
    wallet_svc = WalletService(db)
    event: WebhookEvent | None = None

    try:
        event = await _handle_webhook(provider_instance, raw_body, headers, wallet_svc)

        if event.event_type == "unhandled":
            logger.warning(
                "webhook:{}_unknown_event provider_tx={} payload={}",
                provider_name, event.provider_tx_id, _safe_log_payload(event.raw_data),
            )
            return {"received": True, "ignored": True}

        if event.event_type == "wallet_topup":
            processed, _ = _credit_wallet_from_topup_event(event, wallet_svc, provider_name, db=db)
            return {"received": True, "duplicate": not processed}

        # Escrow-based payment → enqueue for async Celery processing
        idem_key = f"{provider_name}:{event.provider_tx_id}"
        if event.provider_tx_id and WebhookQueue.is_processed(idem_key, db=db):
            return {"received": True, "duplicate": True}

        WebhookQueue.enqueue(
            QueuedWebhookEvent(
                provider=provider_name,
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
                "webhook:celery_unavailable provider={} — queued for drain: {}",
                provider_name, _celery_err,
            )

    except InvalidWebhookSignature as exc:
        logger.warning("webhook:{}_invalid_signature error={}", provider_name, exc)
        FinancialAuditLogger.log(
            action="webhook_invalid",
            user_id="system",
            payment_id="",
            amount=Decimal("0"),
            currency="",
            provider=provider_name,
            status="invalid_signature",
        )
        raise HTTPException(status_code=400, detail="Signature invalide")
    except PaymentProviderError as exc:
        logger.error("webhook:{}_provider_error error={}", provider_name, exc)
        raise HTTPException(status_code=500, detail="Configuration provider")

    if event is not None:
        FinancialAuditLogger.log(
            action="payment_success" if event.event_type == "payment.success" else "payment_failed",
            user_id="system",
            payment_id=event.provider_tx_id,
            amount=event.amount,
            currency=event.currency,
            provider=provider_name,
            status=event.event_type,
        )
    return {"received": True}


@router.post("/webhook/stripe", include_in_schema=False)
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:stripe", limit=180)
    _assert_webhook_secret_configured("stripe")
    return await _dispatch_provider_webhook(
        provider_name="stripe",
        provider_instance=StripeProvider(),
        request=request,
        db=db,
    )


@router.post("/webhook/fedapay", include_in_schema=False)
async def webhook_fedapay(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:fedapay", limit=180)
    _assert_webhook_secret_configured("fedapay")
    return await _dispatch_provider_webhook(
        provider_name="fedapay",
        provider_instance=FedaPayProvider(),
        request=request,
        db=db,
    )


@router.post("/webhook/flutterwave", include_in_schema=False)
async def webhook_flutterwave(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:flutterwave", limit=180)
    _assert_webhook_secret_configured("flutterwave")
    return await _dispatch_provider_webhook(
        provider_name="flutterwave",
        provider_instance=FlutterwaveProvider(),
        request=request,
        db=db,
    )


@router.post("/webhook/paystack", include_in_schema=False)
async def webhook_paystack(request: Request, db: Session = Depends(get_db)):
    _assert_payments_enabled()
    _payments_rate_limit("webhook:paystack", limit=180)
    _assert_webhook_secret_configured("paystack")
    return await _dispatch_provider_webhook(
        provider_name="paystack",
        provider_instance=PaystackProvider(),
        request=request,
        db=db,
    )


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

