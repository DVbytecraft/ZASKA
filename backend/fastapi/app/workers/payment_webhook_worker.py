from __future__ import annotations

from decimal import Decimal

from app.core.observability import logger
from app.db.session import SessionLocal
from app.payment.audit_logger import FinancialAuditLogger
from app.services.payment.fedapay_provider import FedaPayProvider
from app.services.payment.flutterwave_provider import FlutterwaveProvider
from app.services.payment.stripe_provider import StripeProvider
from app.services.payment.webhook_queue import WebhookQueue
from app.services.wallet_service import WalletService
from app.worker.celery_app import celery_app


PROVIDERS = {
    "stripe": StripeProvider,
    "fedapay": FedaPayProvider,
    "flutterwave": FlutterwaveProvider,
}


@celery_app.task(name="app.workers.payment_webhook_worker.process_webhook", bind=True, max_retries=5)
def process_webhook(self, payload: dict | None = None):
    item = payload or WebhookQueue.pop()
    if not item:
        return {"processed": False, "reason": "empty"}

    idem = item.get("idempotency_key", "")
    if idem and WebhookQueue.is_processed(idem):
        return {"processed": False, "reason": "duplicate"}

    provider_name = item.get("provider")
    provider_cls = PROVIDERS.get(provider_name)
    if not provider_cls:
        WebhookQueue.requeue_or_dlq(item)
        return {"processed": False, "reason": "provider_not_supported"}

    db = SessionLocal()
    try:
        import asyncio

        provider = provider_cls()
        raw_body = (item.get("raw_body") or "").encode("utf-8")
        headers = item.get("headers") or {}
        event = asyncio.run(provider.verify_webhook(raw_body, headers))
        wallet_svc = WalletService(db)

        if event.event_type == "payment.success":
            asyncio.run(provider.handle_success(event, wallet_svc))
        elif event.event_type == "payment.failed":
            asyncio.run(provider.handle_failure(event, wallet_svc))

        if event.escrow_id:
            wallet_svc.finalize_transaction(event.escrow_id)

        if idem:
            WebhookQueue.mark_processed(idem)

        FinancialAuditLogger.log(
            action="webhook_worker_processed",
            user_id="system",
            payment_id=event.escrow_id or event.provider_tx_id,
            transaction_id=event.escrow_id or event.provider_tx_id,
            amount=event.amount if isinstance(event.amount, Decimal) else Decimal("0"),
            currency=event.currency or "",
            provider=provider_name,
            status=event.event_type,
            request_id=item.get("request_id", ""),
            idempotency_key=idem,
        )
        return {"processed": True, "provider": provider_name, "event": event.event_type}
    except Exception as exc:
        logger.error("Webhook worker failed: {}", exc)
        WebhookQueue.requeue_or_dlq(item)
        return {"processed": False, "error": str(exc)}
    finally:
        db.close()
