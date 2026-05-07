from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "zaska",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.imports = (
    "app.worker.tasks",
    "app.workers.payment_webhook_worker",
    "app.workers.payout_worker",
    "app.services.payment.recovery_engine",
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-otp-every-5m": {
        "task": "app.worker.tasks.cleanup_otp_keys",
        "schedule": 300.0,
    },
    "payment-recovery-every-5m": {
        "task": "app.services.payment.recovery_engine.run_recovery",
        "schedule": 300.0,
    },
    # Safety net: drain any unprocessed webhook queue items every 30s.
    "drain-webhook-queue-every-30s": {
        "task": "app.workers.payment_webhook_worker.process_webhook",
        "schedule": 30.0,
    },
    # Poll providers for stale processing/pending payouts every minute.
    "check-pending-payouts-every-60s": {
        "task": "app.workers.payout_worker.check_pending_payouts",
        "schedule": 60.0,
    },
}
