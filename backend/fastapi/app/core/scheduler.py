"""
Lightweight asyncio scheduler — replaces Celery beat for free-tier deployments.
Runs periodic background tasks inside the FastAPI process.

MULTI-INSTANCE SAFETY:
Each FastAPI replica (pod) runs its own in-process scheduler.  Without distributed
locks, every job would run N times (once per replica) on every tick.  To prevent
this, every job acquires a Redis lock with TTL = (interval - safety_margin) via
SET NX.  Only the first instance to call SET NX wins; the others skip gracefully.

The lock is NOT explicitly released after the job completes.  It expires via TTL
slightly before the next scheduled run, allowing any surviving instance to win the
next cycle.  This prevents two instances from running the same job within a single
interval window — even if one finishes early.
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.wallet import Escrow, Transaction, Wallet
from app.payment.audit_logger import FinancialAuditLogger
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []

_job_heartbeats: dict[str, datetime] = {}

_JOB_MAX_SILENCE: dict[str, float] = {
    "release_held_escrows": 900,
    "process_outbox": 120,
    "check_pending_payouts": 300,
    "kyc_lifecycle_cycle": 90000,
    "reconciliation": 900,
    "otp_cleanup": 1800,
    "backup_postgres": 172800,
    "social_protection_cycle": 43200,
    "trust_score_recompute": 90000,   # daily job — alert after 25h silence
    "moderation_auto_escalate": 7200, # hourly job — alert after 2h silence
    "operations_resilience_cycle": 900,
    "sandbox_data_cleanup": 90000,  # daily job — alert after 25h silence
    "drain_webhook_queue": 120,
    "payment_recovery": 900,
    "demo_cleanup": 90000,  # every 6h — alert after 25h silence
}


# ── Distributed lock helper ───────────────────────────────────────────────────

def _acquire_job_lock(name: str, ttl_seconds: int) -> bool:
    """Try to acquire a distributed Redis lock for a scheduler job.

    Returns True if the lock was acquired (this instance should run the job).
    Returns False if another instance already holds the lock (skip this run).

    TTL should be slightly less than the job interval (interval - 10s).  The
    lock is intentionally NOT released after the job — it expires naturally so
    only ONE instance runs the job within each interval window, even if the job
    finishes early on the winning instance.
    """
    from app.core.redis_client import redis_sync
    lock_key = f"scheduler:{name}:lock"
    acquired = redis_sync.set(lock_key, "1", ex=ttl_seconds, nx=True)
    if not acquired:
        logger.info("scheduler[%s]: distributed lock held — skipping this cycle", name)
        return False
    return True


async def _run_every(interval: float, name: str, fn) -> None:
    """Run fn() in a thread every `interval` seconds.

    Errors are caught, logged, and the job continues (no silent death).
    Heartbeats are updated after each run so the watchdog can detect stuck jobs.
    """
    await asyncio.sleep(30)
    loop = asyncio.get_event_loop()
    while True:
        start = datetime.utcnow()
        try:
            await loop.run_in_executor(None, fn)
            _job_heartbeats[name] = datetime.utcnow()
            elapsed = (datetime.utcnow() - start).total_seconds()
            logger.info("scheduler[%s]: ok elapsed=%.1fs", name, elapsed)
        except Exception as exc:
            elapsed = (datetime.utcnow() - start).total_seconds()
            logger.error("scheduler[%s]: failed elapsed=%.1fs — %s", name, elapsed, exc)
            _job_heartbeats[name] = datetime.utcnow()
        await asyncio.sleep(interval)


async def _watchdog() -> None:
    """Watchdog task — checks that all scheduled jobs are still running."""
    while True:
        await asyncio.sleep(60)
        now = datetime.utcnow()
        for name, max_silence in _JOB_MAX_SILENCE.items():
            last = _job_heartbeats.get(name)
            if last is None:
                continue
            silence = (now - last).total_seconds()
            if silence > max_silence:
                logger.error(
                    "SCHEDULER_WATCHDOG_ALERT: job '%s' silent for %.0fs (max %.0fs) — "
                    "potential dead task or crash",
                    name, silence, max_silence,
                )


def get_scheduler_health() -> dict:
    now = datetime.utcnow()
    status = {}
    for name, max_silence in _JOB_MAX_SILENCE.items():
        last = _job_heartbeats.get(name)
        if last is None:
            status[name] = {"status": "not_started", "last_run": None, "silence_s": None}
        else:
            silence = (now - last).total_seconds()
            status[name] = {
                "status": "dead" if silence > max_silence else "ok",
                "last_run": last.isoformat(),
                "silence_s": round(silence, 1),
                "max_silence_s": max_silence,
            }
    return status


# ── Job implementations ───────────────────────────────────────────────────────

def _cleanup_otp() -> None:
    # Lock TTL = 290s (interval 300s - 10s).  Only one replica runs this per cycle.
    if not _acquire_job_lock("otp_cleanup", 290):
        return
    # P1-010 FIX: SCAN-based iteration instead of redis.keys("otp:*")
    from app.core.redis_client import redis_sync
    count = 0
    cursor = 0
    while True:
        cursor, keys = redis_sync.scan(cursor, match="otp:*", count=100)
        count += len(keys)
        if cursor == 0:
            break
    logger.info("otp_cleanup: active_keys=%s", count)


def _release_held_escrows() -> None:
    from app.core.redis_client import redis_sync
    # Existing lock pattern kept — TTL 290s for 300s interval
    lock_key = "scheduler:release_held_escrows:lock"
    acquired = redis_sync.set(lock_key, "1", ex=290, nx=True)
    if not acquired:
        logger.info("release_held_escrows: lock held by another instance — skipping")
        return

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        wallet_svc = WalletService(db)
        expired = db.execute(
            select(Escrow).where(
                Escrow.status == "hold",
                Escrow.payout_available_at <= now,
            )
        ).scalars().all()

        released = 0
        errors = 0
        for escrow in expired:
            # P1-011 FIX: capture fields before release_escrow commits
            esc_id = escrow.id
            esc_payee_id = escrow.payee_id
            esc_amount = escrow.amount
            esc_currency = escrow.currency
            try:
                wallet_svc.release_escrow(esc_id)
                FinancialAuditLogger.log(
                    action="escrow_auto_released",
                    user_id=esc_payee_id or "",
                    payment_id=esc_id,
                    amount=esc_amount,
                    currency=esc_currency,
                    provider="internal",
                    status="released",
                )
                released += 1
            except Exception as exc:
                logger.error("escrow_auto_release: failed escrow=%s — %s", esc_id, exc)
                errors += 1

        logger.info(
            "release_held_escrows: checked=%s released=%s errors=%s",
            len(expired), released, errors,
        )
    finally:
        db.close()


def _process_outbox() -> None:
    """Deliver pending outbox events (transactional outbox pattern).

    Lock TTL = 25s (interval 30s - 5s).  At high replica count, only one instance
    processes the outbox per 30s window.  The outbox service uses SELECT FOR UPDATE
    SKIP LOCKED internally, so concurrent executions are also safe — the lock here
    is purely to reduce unnecessary DB load from redundant runs.
    """
    if not _acquire_job_lock("process_outbox", 25):
        return
    from app.services.outbox_service import OutboxService
    db = SessionLocal()
    try:
        result = OutboxService.process_pending(db)
        if result["delivered"] or result["failed"] or result["dead_letter"]:
            logger.info(
                "outbox: delivered=%s failed=%s dead_letter=%s",
                result["delivered"], result["failed"], result["dead_letter"],
            )
    except Exception as exc:
        logger.error("outbox_processor: failed — %s", exc)
    finally:
        db.close()


def _drain_webhook_queue() -> None:
    """Drain pending payment webhook events queued in Redis.

    Lock TTL = 25s (interval 30s - 5s).  Replaces the former Celery
    "drain-webhook-queue-every-30s" beat schedule.
    """
    if not _acquire_job_lock("drain_webhook_queue", 25):
        return
    from app.workers.payment_webhook_worker import process_webhook
    drained = 0
    for _ in range(10):
        result = process_webhook()
        if not result.get("processed") and result.get("reason") == "empty":
            break
        drained += 1
    if drained:
        logger.info("drain_webhook_queue: drained=%s", drained)


def _run_payment_recovery() -> None:
    """Recover stuck escrow payments and reconcile providers.

    Lock TTL = 290s (interval 300s - 10s).  Replaces the former Celery
    "payment-recovery-every-5m" beat schedule.
    """
    if not _acquire_job_lock("payment_recovery", 290):
        return
    from app.services.payment.recovery_engine import RecoveryEngine
    db = SessionLocal()
    try:
        result = RecoveryEngine(db).recover_stuck_payments("ALL")
        logger.info("payment_recovery: stuck_count=%s", result["stuck_count"])
    except Exception as exc:
        logger.error("payment_recovery: failed — %s", exc)
    finally:
        db.close()


def _run_reconciliation() -> None:
    """Run full financial reconciliation.

    Lock TTL = 290s (interval 300s - 10s).  Reconciliation reads the ledger and
    may log drift — running it concurrently on multiple replicas would produce
    duplicate alerts and unnecessary DB load.
    """
    if not _acquire_job_lock("reconciliation", 290):
        return
    from app.services.reconciliation_service import run_reconciliation
    report = run_reconciliation()
    issues = report.get("summary", {}).get("issues_total", 0)
    logger.info("reconciliation: issues=%s", issues)


def _check_pending_payouts() -> None:
    # Lock TTL = 55s (interval 60s - 5s)
    if not _acquire_job_lock("check_pending_payouts", 55):
        return
    from app.services.payment.reconciliation_engine import ReconciliationEngine
    db = SessionLocal()
    try:
        engine = ReconciliationEngine(db)
        report: dict = {
            "country_code": "ALL",
            "run_at": datetime.utcnow().isoformat(),
            "mismatches": [],
            "repaired": 0,
            "payout_updates": [],
        }
        engine._reconcile_payouts(report)
        logger.info("payout_monitor: updated=%s", len(report["payout_updates"]))
    except Exception as exc:
        logger.error("payout_monitor: failed — %s", exc)
    finally:
        db.close()


def _recompute_trust_scores() -> None:
    # Lock TTL = 86390s (daily job)
    if not _acquire_job_lock("trust_score_recompute", 86390):
        return
    from app.services.trust_service import TrustService
    db = SessionLocal()
    try:
        count = TrustService(db).recompute_all()
        logger.info("trust_score_recompute: processed=%s", count)
    except Exception as exc:
        logger.error("trust_score_recompute: failed — %s", exc)
    finally:
        db.close()


def _run_social_protection_cycle() -> None:
    # Lock TTL = 21590s (6h interval - 10s)
    if not _acquire_job_lock("social_protection_cycle", 21590):
        return
    from app.services.social_protection_service import SocialProtectionService

    db = SessionLocal()
    try:
        results = SocialProtectionService(db).run_periodic_cycle()
        logger.info(
            "social_protection_cycle: taskers=%s health_alerts=%s pension_alerts=%s interventions=%s reimbursements=%s",
            results["taskers_scanned"],
            results["health_alerts_sent"],
            results["pension_alerts_sent"],
            results["smoothing_interventions"],
            results["smoothing_reimbursements"],
        )
    except Exception as exc:
        logger.error("social_protection_cycle: failed — %s", exc)
    finally:
        db.close()


def _run_kyc_lifecycle_cycle() -> None:
    if not _acquire_job_lock("kyc_lifecycle_cycle", 86390):
        return
    from app.services.kyc_service import KycService

    db = SessionLocal()
    try:
        results = KycService(db).process_lifecycle()
        logger.info(
            "kyc_lifecycle_cycle: reminders_30d=%s reminders_7d=%s expired=%s reactivated=%s",
            results["reminders_30d"],
            results["reminders_7d"],
            results["expired"],
            results["reactivated"],
        )
    except Exception as exc:
        logger.error("kyc_lifecycle_cycle: failed — %s", exc)
    finally:
        db.close()


def _moderation_auto_escalate() -> None:
    # Lock TTL = 3590s (hourly job)
    if not _acquire_job_lock("moderation_auto_escalate", 3590):
        return
    from app.services.moderation_service import ModerationService
    db = SessionLocal()
    try:
        count = ModerationService(db).auto_escalate_stale()
        logger.info("moderation_auto_escalate: escalated=%s", count)
    except Exception as exc:
        logger.error("moderation_auto_escalate: failed — %s", exc)
    finally:
        db.close()


def _run_operations_resilience_cycle() -> None:
    if not _acquire_job_lock("operations_resilience_cycle", 290):
        return
    from app.services.operations_resilience_service import OperationsResilienceService
    db = SessionLocal()
    try:
        results = OperationsResilienceService(db).run_cycle()
        logger.info(
            "operations_resilience_cycle: expired_vtc_offers=%s redispatched_vtc_rides=%s stale_shop_orders=%s stale_food_orders=%s",
            results["expired_vtc_offers"],
            results["redispatched_vtc_rides"],
            results["stale_shop_orders"],
            results["stale_food_orders"],
        )
    except Exception as exc:
        logger.error("operations_resilience_cycle: failed — %s", exc)
    finally:
        db.close()


def _backup_postgres() -> None:
    # Lock TTL = 86390s (interval 86400s - 10s).  Only one replica runs the daily backup.
    if not _acquire_job_lock("backup_postgres", 86390):
        return

    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    parsed = urlparse(settings.database_url)
    db_info = {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/zaska").lstrip("/"),
    }

    pg_dump_cmd = shutil.which("pg_dump")
    if pg_dump_cmd is None:
        logger.warning("backup_postgres: pg_dump not found — skipping")
        return

    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dump_path = backup_dir / f"zaska_{timestamp}.sql.gz"

    proc = subprocess.run(
        [pg_dump_cmd, "-h", db_info["host"], "-p", db_info["port"],
         "-U", db_info["user"], "-d", db_info["dbname"], "--no-password", "-Fp"],
        env=env, capture_output=True, timeout=300,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace")[:300]
        logger.error("backup_postgres: pg_dump failed (rc=%s): %s", proc.returncode, err)
        return

    with gzip.open(dump_path, "wb") as gz:
        gz.write(proc.stdout)

    size_mb = dump_path.stat().st_size / (1024 * 1024)
    logger.info("backup_postgres: created %s (%.1f MB)", dump_path.name, size_mb)

    cutoff = datetime.utcnow() - timedelta(days=settings.backup_keep_days)
    for f in backup_dir.glob("zaska_*.sql.gz"):
        if datetime.utcfromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            logger.info("backup_postgres: rotated %s", f.name)


def _cleanup_demo_users() -> None:
    """Delete demo users whose JWTs have long expired (> 24h old).

    Lock TTL = 21590s (6h interval - 10s). Only one replica runs this per cycle.
    """
    if not _acquire_job_lock("demo_cleanup", 21590):
        return
    from app.services.demo_service import cleanup_stale_demo_users
    db = SessionLocal()
    try:
        result = cleanup_stale_demo_users(db)
        logger.info(
            "demo_cleanup: scanned=%s deleted=%s suspended=%s",
            result["scanned"], result["deleted"], result["suspended"],
        )
    except Exception as exc:
        logger.error("demo_cleanup: failed — %s", exc)
    finally:
        db.close()


def _cleanup_sandbox_data() -> None:
    """Purge sandbox wallets/transactions/escrows older than the retention window.

    Sandbox data (created via a sandbox API key, is_sandbox=True) never touches
    real money or the accounting ledger — it only exists to let B2B integrators
    test against the API. We delete in FK-safe order: escrows -> transactions ->
    wallets, each older than settings.sandbox_data_retention_days.
    """
    if not _acquire_job_lock("sandbox_data_cleanup", 86390):
        return

    cutoff = datetime.utcnow() - timedelta(days=settings.sandbox_data_retention_days)
    db = SessionLocal()
    try:
        escrows = db.execute(
            select(Escrow).where(Escrow.is_sandbox.is_(True), Escrow.created_at < cutoff)
        ).scalars().all()
        escrow_count = len(escrows)
        for escrow in escrows:
            escrow.funding_tx_id = None
            escrow.settlement_tx_id = None
            db.delete(escrow)
        db.flush()

        transactions = db.execute(
            select(Transaction).where(Transaction.is_sandbox.is_(True), Transaction.created_at < cutoff)
        ).scalars().all()
        tx_count = len(transactions)
        for tx in transactions:
            db.delete(tx)
        db.flush()

        wallets = db.execute(
            select(Wallet).where(Wallet.is_sandbox.is_(True), Wallet.created_at < cutoff)
        ).scalars().all()
        wallet_count = len(wallets)
        for wallet in wallets:
            db.delete(wallet)

        db.commit()
        logger.info(
            "sandbox_data_cleanup: escrows=%s transactions=%s wallets=%s cutoff=%s",
            escrow_count, tx_count, wallet_count, cutoff.isoformat(),
        )
    except Exception as exc:
        db.rollback()
        logger.error("sandbox_data_cleanup: failed — %s", exc)
    finally:
        db.close()


# ── Public API ────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Create asyncio background tasks for all periodic jobs + watchdog."""
    jobs = [
        (300,   "otp_cleanup",              _cleanup_otp),
        (300,   "release_held_escrows",     _release_held_escrows),
        (30,    "process_outbox",           _process_outbox),
        (60,    "check_pending_payouts",    _check_pending_payouts),
        (300,   "reconciliation",           _run_reconciliation),
        (21600, "social_protection_cycle",  _run_social_protection_cycle),
        (86400, "kyc_lifecycle_cycle",      _run_kyc_lifecycle_cycle),
        (86400, "backup_postgres",          _backup_postgres),
        (86400, "trust_score_recompute",    _recompute_trust_scores),
        (3600,  "moderation_auto_escalate", _moderation_auto_escalate),
        (300,   "operations_resilience_cycle", _run_operations_resilience_cycle),
        (86400, "sandbox_data_cleanup",     _cleanup_sandbox_data),
        (30,    "drain_webhook_queue",      _drain_webhook_queue),
        (300,   "payment_recovery",         _run_payment_recovery),
        (21600, "demo_cleanup",             _cleanup_demo_users),
    ]
    for interval, name, fn in jobs:
        task = asyncio.create_task(_run_every(interval, name, fn))
        _tasks.append(task)
    watchdog_task = asyncio.create_task(_watchdog())
    _tasks.append(watchdog_task)
    logger.info("scheduler: started %s periodic jobs + watchdog", len(jobs))


def stop_scheduler() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    logger.info("scheduler: stopped")
