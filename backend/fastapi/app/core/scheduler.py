"""
Lightweight asyncio scheduler — replaces Celery beat for free-tier deployments.
Runs periodic background tasks inside the FastAPI process.
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
from app.models.wallet import Escrow
from app.payment.audit_logger import FinancialAuditLogger
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []


async def _run_every(interval: float, name: str, fn) -> None:
    """Run fn() in a thread every `interval` seconds. Errors are logged, not raised."""
    await asyncio.sleep(30)  # let the app finish startup before first run
    loop = asyncio.get_event_loop()
    while True:
        try:
            await loop.run_in_executor(None, fn)
            logger.info("scheduler[%s]: ok", name)
        except Exception as exc:
            logger.error("scheduler[%s]: failed — %s", name, exc)
        await asyncio.sleep(interval)


# ── Job implementations ───────────────────────────────────────────────────────

def _cleanup_otp() -> None:
    from app.core.redis_client import redis_sync
    keys = redis_sync.keys("otp:*")
    logger.info("otp_cleanup: active_keys=%s", len(keys))


def _release_held_escrows() -> None:
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
            try:
                wallet_svc.release_escrow(escrow.id)
                FinancialAuditLogger.log(
                    action="escrow_auto_released",
                    user_id=escrow.payee_id or "",
                    payment_id=escrow.id,
                    amount=escrow.amount,
                    currency=escrow.currency,
                    provider="internal",
                    status="released",
                )
                released += 1
            except Exception as exc:
                logger.error("escrow_auto_release: failed escrow=%s — %s", escrow.id, exc)
                errors += 1

        logger.info(
            "release_held_escrows: checked=%s released=%s errors=%s",
            len(expired), released, errors,
        )
    finally:
        db.close()


def _check_pending_payouts() -> None:
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


def _backup_postgres() -> None:
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


# ── Public API ────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Create asyncio background tasks for all periodic jobs."""
    jobs = [
        (300,   "otp_cleanup",           _cleanup_otp),
        (300,   "release_held_escrows",  _release_held_escrows),
        (60,    "check_pending_payouts", _check_pending_payouts),
        (86400, "backup_postgres",       _backup_postgres),
    ]
    for interval, name, fn in jobs:
        task = asyncio.create_task(_run_every(interval, name, fn))
        _tasks.append(task)
    logger.info("scheduler: started %s periodic jobs", len(jobs))


def stop_scheduler() -> None:
    """Cancel all scheduler tasks (called on shutdown)."""
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    logger.info("scheduler: stopped")
