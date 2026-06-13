"""
Payout retry — manual retry of a specific failed payout.

release_held_escrows and check_pending_payouts now run exclusively from the
native asyncio scheduler (app/core/scheduler.py), each guarded by a Redis
distributed lock to prevent multi-instance duplication.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.payout import Payout
from app.payment.audit_logger import FinancialAuditLogger
from app.payment.limits import TransactionLimits
from app.services.payment.mobile_money_topup import execute_mobile_money_payout

logger = logging.getLogger(__name__)


def _make_limits() -> TransactionLimits:
    return TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))


def retry_payout(payout_id: str) -> dict:
    """
    Retry a failed payout.
    Enforces payout_max_retries from config.
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
        logger.error("retry_payout: attempt failed for payout %s — %s", payout_id, exc)
        try:
            payout = db.execute(
                select(Payout).where(Payout.id == payout_id)
            ).scalars().one_or_none()
            if payout:
                payout.status = "failed"
                payout.failure_reason = f"retry_{payout.retry_count}: {exc}"
                db.commit()

                limits = _make_limits()
                limits.record_payout_failure(
                    user_id=payout.user_id,
                    threshold=settings.payout_fail_block_threshold,
                )
        except Exception:
            pass

        return {"error": str(exc)}
    finally:
        db.close()
