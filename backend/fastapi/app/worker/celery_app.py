from celery import Celery
from celery.signals import beat_init, worker_ready

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
    "app.workers.backup_worker",
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
    # Auto-release held escrows once the 24h contestation window expires.
    "release-held-escrows-every-5m": {
        "task": "app.workers.payout_worker.release_held_escrows",
        "schedule": 300.0,
    },
    # social_protection_cycle, kyc_lifecycle_cycle and operations_resilience_cycle
    # run from the in-process asyncio scheduler (app/core/scheduler.py), which holds
    # a Redis lock per job — they must not also be scheduled here, or they would run
    # twice per interval (once via Celery beat, once via the asyncio scheduler).
    # Daily PostgreSQL backup (86400s = 24h).
    "postgres-backup-daily": {
        "task": "app.workers.backup_worker.backup_postgres",
        "schedule": 86400.0,
    },
}


def _ensure_internal_wallet_runtime() -> None:
    from app.db.session import SessionLocal
    from app.services.internal_wallet_seed_service import InternalWalletSeedService

    db = SessionLocal()
    try:
        InternalWalletSeedService(db).ensure_all()
    finally:
        db.close()


@worker_ready.connect
def _seed_internal_wallets_for_worker(**_kwargs) -> None:
    _ensure_internal_wallet_runtime()


@beat_init.connect
def _seed_internal_wallets_for_beat(**_kwargs) -> None:
    _ensure_internal_wallet_runtime()
