"""
Payout monitoring and retry Celery tasks.

check_pending_payouts — polls provider for stale processing/pending payouts
retry_payout          — exponential-backoff retry for a specific failed payout
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.payout import Payout
from app.payment.audit_logger import FinancialAuditLogger
from app.payment.limits import TransactionLimits
from app.services.payment.mobile_money_topup import execute_mobile_money_payout
from app.services.wallet_service import WalletService
from app.worker.celery_app import celery_app

from app.models.wallet import Escrow

logger = logging.getLogger(__name__)


def _make_limits() -> TransactionLimits:
    return TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))


@celery_app.task(name="app.workers.payout_worker.release_held_escrows", bind=True)
def release_held_escrows(self):
    """
    Scheduled task — runs every 5 minutes.
    Finds escrows in 'hold' state where payout_available_at has passed
    and no contest has been filed. Automatically releases payment to the tasker.
    This is the 24h automatic release after task completion.
    """
    # Distributed lock — coordinate with the asyncio scheduler running in each FastAPI
    # process.  TTL matches the scheduler interval (300s) minus a 10s grace window.
    from app.core.redis_client import redis_sync as _redis
    lock_key = "scheduler:release_held_escrows:lock"
    acquired = _redis.set(lock_key, "celery", ex=290, nx=True)
    if not acquired:
        logger.info("release_held_escrows: lock held — skipping this Celery run")
        return {"skipped": True, "reason": "distributed_lock"}

    db = SessionLocal()
    released = 0
    errors = 0
    try:
        now = datetime.utcnow()
        wallet_svc = WalletService(db)

        # Find all hold escrows whose window has passed
        expired_holds = db.execute(
            select(Escrow)
            .where(
                Escrow.status == "hold",
                Escrow.payout_available_at <= now,
            )
        ).scalars().all()

        for escrow in expired_holds:
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
                logger.info(
                    "escrow_auto_release: escrow=%s task=%s amount=%s %s",
                    escrow.id, escrow.task_id, escrow.amount, escrow.currency,
                )
                released += 1
            except Exception as exc:
                logger.error(
                    "escrow_auto_release: failed escrow=%s error=%s",
                    escrow.id, exc,
                )
                errors += 1

        logger.info(
            "release_held_escrows: checked=%s released=%s errors=%s",
            len(expired_holds), released, errors,
        )
        return {"checked": len(expired_holds), "released": released, "errors": errors}
    except Exception as exc:
        logger.error("release_held_escrows: task failed — %s", exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()


@celery_app.task(name="app.workers.payout_worker.check_pending_payouts", bind=True)
def check_pending_payouts(self):
    """
    Scheduled task — runs every minute.
    Finds payouts stuck in 'processing' or 'pending' for longer than
    PAYOUT_MONITOR_STALE_MINUTES, polls the provider, and syncs status.
    """
    db = SessionLocal()
    try:
        from app.services.payment.reconciliation_engine import ReconciliationEngine
        engine = ReconciliationEngine(db)
        report: dict = {
            "country_code": "ALL",
            "run_at": datetime.utcnow().isoformat(),
            "mismatches": [],
            "repaired": 0,
            "payout_updates": [],
        }
        engine._reconcile_payouts(report)
        updated = len(report["payout_updates"])
        logger.info("payout_monitor: checked stale payouts, updated=%s", updated)
        return {"updated_count": updated, "updates": report["payout_updates"]}
    except Exception as exc:
        logger.error("payout_monitor: failed — %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        db.close()


@celery_app.task(
    name="app.workers.payout_worker.retry_payout",
    bind=True,
    max_retries=3,
)
def retry_payout(self, payout_id: str):
    """
    Retry a failed payout.
    Enforces payout_max_retries from config.
    Uses exponential backoff: 60s, 300s, 900s.
    """
    db = SessionLocal()
    try:
        payout: Payout | None = db.execute(
            select(Payout).where(Payout.id == payout_id)
        ).scalars().one_or_none()

        if payout is None:
            logger.error("retry_payout: payout %s not found", payout_id)
            return {"error": "not_found"}

        if payout.status not in {"failed", "pending"}:
            logger.info(
                "retry_payout: payout %s status=%s — skip", payout_id, payout.status
            )
            return {"skipped": True, "status": payout.status}

        if payout.retry_count >= settings.payout_max_retries:
            logger.warning(
                "retry_payout: max retries (%s) reached for payout %s",
                settings.payout_max_retries, payout_id,
            )
            payout.failure_reason = (
                f"max_retries_reached ({settings.payout_max_retries})"
            )
            db.commit()
            FinancialAuditLogger.log(
                action="payout_max_retries_reached",
                user_id=payout.user_id,
                payment_id=payout.id,
                amount=payout.amount,
                currency=payout.currency,
                provider=payout.provider,
                status="failed",
            )
            return {"error": "max_retries_reached"}

        # Increment retry counter and set status to processing
        payout.retry_count += 1
        payout.status = "processing"
        payout.failure_reason = None
        db.commit()

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                execute_mobile_money_payout(
                    user_id=payout.user_id,
                    amount=payout.amount,
                    currency=payout.currency,
                    provider=payout.provider,
                    phone_number=payout.phone_number,
                    country_code=payout.country_code,
                    reference=f"{payout.reference}:retry{payout.retry_count}",
                )
            )
        finally:
            loop.close()

        payout.status = result["status"]
        payout.provider_tx_id = result["provider_tx_id"]
        db.commit()

        limits = _make_limits()
        limits.clear_payout_failures(user_id=payout.user_id)

        FinancialAuditLogger.log(
            action="payout_retry_success",
            user_id=payout.user_id,
            payment_id=result["provider_tx_id"],
            amount=payout.amount,
            currency=payout.currency,
            provider=result["provider"],
            status=result["status"],
        )
        logger.info(
            "retry_payout: success payout=%s retry=%s status=%s",
            payout_id, payout.retry_count, result["status"],
        )
        return {"status": result["status"], "retry_count": payout.retry_count}

    except Exception as exc:
        # Exponential backoff: 60s → 300s → 900s
        backoff_schedule = [60, 300, 900]
        attempt = self.request.retries
        countdown = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]

        logger.warning(
            "retry_payout: attempt %s failed for payout %s — retrying in %ss: %s",
            attempt + 1, payout_id, countdown, exc,
        )
        try:
            # Mark payout as failed between retries
            payout = db.execute(
                select(Payout).where(Payout.id == payout_id)
            ).scalars().one_or_none()
            if payout:
                payout.status = "failed"
                payout.failure_reason = f"retry_{attempt + 1}: {exc}"
                db.commit()

                limits = _make_limits()
                limits.record_payout_failure(
                    user_id=payout.user_id,
                    threshold=settings.payout_fail_block_threshold,
                )
        except Exception:
            pass

        raise self.retry(exc=exc, countdown=countdown) from exc
    finally:
        db.close()
