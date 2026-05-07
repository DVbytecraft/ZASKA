from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_wallet_service, require_admin
from app.core.config import settings
from app.core.country_engine.definitions import COUNTRY_CONFIGS
from app.core.fx_rate import get_live_fx_rate
from app.core.redis_client import redis_sync
from app.core.responses import success_response
from app.models.dispute import DisputeRecord, ReconciliationReport
from app.models.kyc import KycSubmission
from app.models.payout import Payout
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Transaction
from app.payment.limits import TransactionLimits
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Existing endpoints (preserved) ───────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    total_tasks = db.query(Task).count()
    open_tasks = db.query(Task).filter(Task.status == "OPEN").count()
    assigned_tasks = db.query(Task).filter(Task.status == "ASSIGNED").count()
    completed_tasks = db.query(Task).filter(Task.status == "COMPLETED").count()
    total_users = db.query(User).count()
    verified_users = db.query(User).filter(User.is_verified.is_(True)).count()
    return success_response(
        {
            "total_tasks": total_tasks,
            "open_tasks": open_tasks,
            "assigned_tasks": assigned_tasks,
            "completed_tasks": completed_tasks,
            "total_users": total_users,
            "verified_users": verified_users,
        }
    )


@router.get("/tasks")
def list_all_tasks(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    tasks = db.query(Task).order_by(Task.created_at.desc()).limit(100).all()
    return success_response(
        [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "price": str(t.price),
                "currency": t.currency,
                "status": t.status,
                "created_by": t.created_by,
                "assigned_to": t.assigned_to,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    )


@router.get("/countries")
def list_countries(
    _: str = Depends(require_admin),
):
    return success_response(
        [
            {
                "code": cfg.country_code,
                "currency": cfg.currency,
                "mobile_money_enabled": cfg.mobile_money_enabled,
                "payment_providers": cfg.payment_providers,
            }
            for cfg in COUNTRY_CONFIGS.values()
        ]
    )


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    return success_response(
        [
            {
                "id": u.id,
                "email": u.email,
                "phone": u.phone,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "full_name": u.full_name,
                "role": u.role,
                "is_verified": u.is_verified,
                "country_code": u.country_code,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    )


# ── Payout management ─────────────────────────────────────────────────────────

@router.get("/payouts")
def list_payouts(
    status: str | None = None,
    user_id_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = select(Payout).order_by(desc(Payout.created_at)).limit(min(limit, 200))
    if status:
        stmt = stmt.where(Payout.status == status)
    if user_id_filter:
        stmt = stmt.where(Payout.user_id == user_id_filter)
    payouts = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": p.id,
            "user_id": p.user_id,
            "amount": str(p.amount),
            "currency": p.currency,
            "provider": p.provider,
            "phone_number": p.phone_number[-4:].rjust(len(p.phone_number), "*"),
            "country_code": p.country_code,
            "status": p.status,
            "provider_tx_id": p.provider_tx_id,
            "failure_reason": p.failure_reason,
            "retry_count": p.retry_count,
            "admin_notes": p.admin_notes,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in payouts
    ])


class ResolvePayoutPayload(BaseModel):
    status: str       # "completed" | "failed"
    admin_notes: str = ""


@router.post("/payouts/{payout_id}/resolve")
def resolve_payout(
    payout_id: str,
    payload: ResolvePayoutPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    if payload.status not in {"completed", "failed"}:
        raise HTTPException(status_code=400, detail="status must be 'completed' or 'failed'")
    payout = db.get(Payout, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout introuvable")
    if payout.status == "completed":
        raise HTTPException(status_code=409, detail="Payout already completed")

    reconciled = False
    if payload.status == "completed" and payout.status == "failed":
        # The payout actually succeeded after all — undo the automatic rollback credit
        # (rollback credit is issued with reference "rollback:{payout.reference}")
        from app.models.wallet import Transaction as WalletTransaction
        from app.services.wallet_service import InsufficientFundsError
        rollback_tx = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.reference == f"rollback:{payout.reference}",
                WalletTransaction.user_id == payout.user_id,
            )
            .one_or_none()
        )
        if rollback_tx is not None:
            try:
                svc.debit_wallet(
                    user_id=payout.user_id,
                    currency=payout.currency,
                    amount=payout.amount,
                    reference=f"admin_reconcile:{payout_id}",
                    provider="admin",
                    metadata={
                        "type": "payout_reconcile",
                        "payout_id": payout_id,
                        "admin_id": admin_user_id,
                        "rollback_tx_id": rollback_tx.id,
                    },
                )
                reconciled = True
            except InsufficientFundsError as exc:
                raise HTTPException(
                    status_code=402,
                    detail=f"Réconciliation impossible : solde insuffisant ({exc})",
                )

    payout.status = payload.status
    payout.admin_notes = payload.admin_notes or f"Manually resolved by admin {admin_user_id}"
    db.commit()
    return success_response({
        "payout_id": payout_id,
        "status": payout.status,
        "wallet_reconciled": reconciled,
    })


@router.post("/payouts/{payout_id}/retry")
def queue_payout_retry(
    payout_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    payout = db.get(Payout, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout introuvable")
    if payout.status == "completed":
        raise HTTPException(status_code=409, detail="Payout already completed")

    # Reset retry counter so admin override is not blocked by max_retries
    payout.retry_count = 0
    payout.status = "failed"
    db.commit()

    from app.workers.payout_worker import retry_payout
    task = retry_payout.delay(payout_id)
    return success_response({"payout_id": payout_id, "job_id": task.id, "queued": True})


# ── KYC management ────────────────────────────────────────────────────────────

@router.get("/kyc")
def list_kyc(
    status: str | None = "pending",
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(KycSubmission)
        .order_by(desc(KycSubmission.created_at))
        .limit(min(limit, 200))
    )
    if status:
        stmt = stmt.where(KycSubmission.status == status)
    submissions = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": s.id,
            "user_id": s.user_id,
            "status": s.status,
            "id_document_url": s.id_document_url,
            "selfie_url": s.selfie_url,
            "reviewed_by": s.reviewed_by,
            "reviewer_note": s.reviewer_note,
            "created_at": s.created_at.isoformat(),
        }
        for s in submissions
    ])


class KYCDecisionPayload(BaseModel):
    reason: str = ""


@router.post("/kyc/{submission_id}/approve")
def approve_kyc(
    submission_id: str,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
):
    from app.services.kyc_service import KycService
    try:
        KycService(db).approve(submission_id, reviewer_id=admin_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success_response({"submission_id": submission_id, "status": "approved"})


@router.post("/kyc/{submission_id}/reject")
def reject_kyc(
    submission_id: str,
    payload: KYCDecisionPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
):
    from app.services.kyc_service import KycService
    try:
        KycService(db).reject(
            submission_id,
            reviewer_id=admin_user_id,
            note=payload.reason or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success_response({"submission_id": submission_id, "status": "rejected"})


# ── Fraud flags ───────────────────────────────────────────────────────────────

def _scan_redis_keys(pattern: str, count: int = 100) -> list[str]:
    """Scan Redis keys matching pattern using SCAN (non-blocking, O(1) per call)."""
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = redis_sync.scan(cursor, match=pattern, count=count)
        for k in batch:
            keys.append(k if isinstance(k, str) else k.decode())
        if cursor == 0:
            break
    return keys


@router.get("/fraud/flags")
def list_fraud_flags(
    _: str = Depends(require_admin),
):
    """Return currently flagged users: payout-blocked and rapid-cycle candidates."""
    payout_fail_keys = _scan_redis_keys("fraud:payout_fails:*")
    rapid_cycle_keys = _scan_redis_keys("fraud:last_deposit:*")

    payout_blocked = []
    for key in payout_fail_keys:
        raw = redis_sync.get(key)
        count = int(raw) if raw else 0
        if count >= settings.payout_fail_block_threshold:
            uid = key.split(":")[-1]
            payout_blocked.append({"user_id": uid, "consecutive_failures": count})

    rapid_cycle_candidates = []
    for key in rapid_cycle_keys:
        uid = key.split(":")[-1]
        rapid_cycle_candidates.append({"user_id": uid})

    return success_response({
        "payout_blocked": payout_blocked,
        "rapid_cycle_candidates": rapid_cycle_candidates,
    })


@router.delete("/fraud/flags/{user_id}")
def clear_fraud_flags(
    user_id: str,
    _: str = Depends(require_admin),
):
    """Admin: clear all fraud flags for a user (unblock payout + rapid-cycle)."""
    limits = TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))
    limits.clear_payout_failures(user_id=user_id)
    redis_sync.delete(f"fraud:last_deposit:{user_id}")
    return success_response({"user_id": user_id, "flags_cleared": True})


# ── Transaction reversal ──────────────────────────────────────────────────────

class ReversalPayload(BaseModel):
    reason: str


@router.post("/transactions/{transaction_id}/reverse")
def reverse_transaction(
    transaction_id: str,
    payload: ReversalPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    from app.services.wallet_service import InsufficientFundsError
    try:
        rev_tx, dispute = svc.reverse_transaction(
            transaction_id=transaction_id,
            reason=payload.reason,
            admin_user_id=admin_user_id,
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return success_response({
        "reversal_tx_id": rev_tx.id,
        "dispute_id": dispute.id,
        "original_tx_id": transaction_id,
        "status": "reversed",
    })


# ── Disputes ─────────────────────────────────────────────────────────────────

@router.get("/disputes")
def list_disputes(
    status: str | None = "open",
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(DisputeRecord)
        .order_by(desc(DisputeRecord.created_at))
        .limit(min(limit, 200))
    )
    if status:
        stmt = stmt.where(DisputeRecord.status == status)
    disputes = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": d.id,
            "user_id": d.user_id,
            "transaction_id": d.transaction_id,
            "payout_id": d.payout_id,
            "dispute_type": d.dispute_type,
            "reason": d.reason,
            "status": d.status,
            "admin_notes": d.admin_notes,
            "resolution_tx_id": d.resolution_tx_id,
            "created_at": d.created_at.isoformat(),
        }
        for d in disputes
    ])


class DisputeResolutionPayload(BaseModel):
    resolution: str   # "resolved" | "rejected"
    admin_notes: str = ""


@router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: str,
    payload: DisputeResolutionPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        dispute = svc.resolve_dispute(
            dispute_id=dispute_id,
            admin_user_id=admin_user_id,
            resolution=payload.resolution,
            admin_notes=payload.admin_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return success_response({
        "dispute_id": dispute.id,
        "status": dispute.status,
        "admin_notes": dispute.admin_notes,
    })


# ── Reconciliation reports ────────────────────────────────────────────────────

@router.get("/reconciliation/reports")
def list_reconciliation_reports(
    limit: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    reports = (
        db.execute(
            select(ReconciliationReport)
            .order_by(desc(ReconciliationReport.run_at))
            .limit(min(limit, 100))
        )
        .scalars()
        .all()
    )
    return success_response([
        {
            "id": r.id,
            "run_at": r.run_at.isoformat(),
            "country_code": r.country_code,
            "matched_count": r.matched_count,
            "missing_count": r.missing_count,
            "inconsistent_count": r.inconsistent_count,
            "repaired_count": r.repaired_count,
        }
        for r in reports
    ])


@router.get("/reconciliation/reports/{report_id}")
def get_reconciliation_report(
    report_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    import json as _json
    report = db.get(ReconciliationReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report introuvable")
    return success_response({
        "id": report.id,
        "run_at": report.run_at.isoformat(),
        "country_code": report.country_code,
        "matched_count": report.matched_count,
        "missing_count": report.missing_count,
        "inconsistent_count": report.inconsistent_count,
        "repaired_count": report.repaired_count,
        "details": _json.loads(report.report_json) if report.report_json else {},
    })


_FX_RATE_REDIS_KEY = "config:fx_usd_to_xof"


@router.get("/fx/rate")
def get_fx_rate(_: str = Depends(require_admin)):
    """Return the currently active USD→XOF FX rate (Redis override or config default)."""
    raw = redis_sync.get(_FX_RATE_REDIS_KEY)
    source = "redis_override" if raw else "config_default"
    rate = get_live_fx_rate()
    return success_response({
        "fx_usd_to_xof": str(rate),
        "source": source,
        "config_default": str(settings.fx_usd_to_xof),
    })


class FxRatePayload(BaseModel):
    rate: str   # Decimal string, e.g. "655.957"


@router.put("/fx/rate")
def set_fx_rate(
    payload: FxRatePayload,
    _: str = Depends(require_admin),
):
    """Override the live USD→XOF rate in Redis. Takes effect immediately on all new operations."""
    try:
        rate = Decimal(payload.rate)
    except Exception:
        raise HTTPException(status_code=400, detail="rate must be a valid decimal number")
    if rate <= Decimal("0") or rate > Decimal("10000"):
        raise HTTPException(status_code=400, detail="rate must be between 0 and 10000")
    redis_sync.set(_FX_RATE_REDIS_KEY, str(rate))
    return success_response({"fx_usd_to_xof": str(rate), "source": "redis_override"})


@router.delete("/fx/rate")
def reset_fx_rate(_: str = Depends(require_admin)):
    """Remove the Redis FX rate override — reverts to config default."""
    redis_sync.delete(_FX_RATE_REDIS_KEY)
    return success_response({
        "fx_usd_to_xof": str(settings.fx_usd_to_xof),
        "source": "config_default",
    })


# ── FX exposure ───────────────────────────────────────────────────────────────

@router.get("/fx/exposure")
def get_fx_exposure(
    _: str = Depends(require_admin),
):
    limits = TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))
    return success_response({
        **limits.get_fx_exposure(),
        "limit_usd": str(settings.fx_exposure_limit_usd),
    })


@router.delete("/fx/exposure/{direction}")
def reset_fx_exposure(
    direction: str,
    _: str = Depends(require_admin),
):
    if direction not in {"to_xof", "from_xof"}:
        raise HTTPException(
            status_code=400, detail="direction must be 'to_xof' or 'from_xof'"
        )
    limits = TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))
    limits.reset_fx_exposure(direction=direction)
    return success_response({"direction": direction, "reset": True})


# ── Financial audit logs ──────────────────────────────────────────────────────

@router.get("/audit-logs")
def list_audit_logs(
    user_id_filter: str | None = None,
    action_filter: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Return immutable financial audit trail (most recent first)."""
    from app.models.audit_log import FinancialAuditLog
    stmt = (
        select(FinancialAuditLog)
        .order_by(desc(FinancialAuditLog.created_at))
        .limit(min(limit, 500))
        .offset(offset)
    )
    if user_id_filter:
        stmt = stmt.where(FinancialAuditLog.user_id == user_id_filter)
    if action_filter:
        stmt = stmt.where(FinancialAuditLog.action == action_filter)
    logs = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": lg.id,
            "action": lg.action,
            "user_id": lg.user_id,
            "payment_id": lg.payment_id,
            "transaction_id": lg.transaction_id,
            "amount": str(lg.amount),
            "currency": lg.currency,
            "provider": lg.provider,
            "status": lg.status,
            "country_code": lg.country_code,
            "created_at": lg.created_at.isoformat(),
        }
        for lg in logs
    ])
