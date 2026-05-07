from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.wallet import Escrow
from app.services.payment.reconciliation_engine import ReconciliationEngine
from app.services.payment.webhook_queue import WebhookQueue
from app.worker.celery_app import celery_app
from app.workers.payment_webhook_worker import process_webhook


class RecoveryEngine:
    def __init__(self, db: Session):
        self.db = db

    def recover_stuck_payments(self, country_code: str) -> dict:
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        stuck = (
            self.db.execute(select(Escrow).where(Escrow.status == "pending", Escrow.created_at < cutoff))
            .scalars()
            .all()
        )
        for _ in range(10):
            payload = WebhookQueue.pop()
            if not payload:
                break
            process_webhook.delay(payload)

        report = ReconciliationEngine(self.db).reconcile_all(country_code)
        return {"stuck_count": len(stuck), "reconciliation": report}


@celery_app.task(name="app.services.payment.recovery_engine.run_recovery")
def run_recovery(country_code: str = "DEFAULT"):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return RecoveryEngine(db).recover_stuck_payments(country_code)
    finally:
        db.close()
