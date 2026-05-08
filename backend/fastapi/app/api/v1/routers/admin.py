from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_wallet_service, require_admin
from app.core.config import settings
from app.core.country_engine.definitions import COUNTRY_REGISTRY as COUNTRY_CONFIGS
from app.core.fx_rate import get_live_fx_rate
from app.core.redis_client import redis_sync
from app.core.responses import success_response
from app.models.dispute import DisputeRecord, ReconciliationReport
from app.models.kyc import KycSubmission
from app.models.payout import Payout
from app.models.support_ticket import SupportTicket
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow, Transaction, Wallet
from app.payment.limits import TransactionLimits
from app.services.wallet_service import InsufficientFundsError, WalletService

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Existing endpoints (preserved) ───────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from sqlalchemy import func as _func
    total_tasks = db.query(Task).count()
    open_tasks = db.query(Task).filter(Task.status == "OPEN").count()
    assigned_tasks = db.query(Task).filter(Task.status == "ASSIGNED").count()
    completed_tasks = db.query(Task).filter(Task.status == "COMPLETED").count()
    total_users = db.query(User).count()
    verified_users = db.query(User).filter(User.is_verified.is_(True)).count()

    # Total revenue = sum of completed escrow releases (credit transactions of type escrow_release)
    revenue_row = db.execute(
        select(
            _func.coalesce(_func.sum(Transaction.amount), Decimal("0")).label("revenue"),
            Wallet.currency.label("currency"),
        )
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.status == "completed",
            Transaction.type == "credit",
            Transaction.reference.like("escrow_release:%"),
        )
        .group_by(Wallet.currency)
        .order_by(desc(_func.sum(Transaction.amount)))
        .limit(1)
    ).first()

    total_revenue = str(revenue_row.revenue) if revenue_row else "0"
    revenue_currency = revenue_row.currency if revenue_row else "XOF"

    return success_response(
        {
            "total_tasks": total_tasks,
            "open_tasks": open_tasks,
            "assigned_tasks": assigned_tasks,
            "completed_tasks": completed_tasks,
            "total_users": total_users,
            "verified_users": verified_users,
            "total_revenue": total_revenue,
            "revenue_currency": revenue_currency,
        }
    )


@router.get("/analytics/summary")
def analytics_summary(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Aggregate analytics data: user growth, task funnel, revenue by month, geo distribution."""
    from sqlalchemy import func as _func, extract as _extract

    # User counts by role
    role_counts = db.execute(
        select(User.role, _func.count(User.id).label("count"))
        .group_by(User.role)
    ).all()
    users_by_role = {r.role: r.count for r in role_counts}

    # Tasks by status
    status_counts = db.execute(
        select(Task.status, _func.count(Task.id).label("count"))
        .group_by(Task.status)
    ).all()
    tasks_by_status = {s.status: s.count for s in status_counts}

    # Monthly revenue (last 6 months) — sum of escrow_release credits
    # Fetch raw rows and aggregate in Python for DB-agnostic compatibility
    revenue_rows = db.execute(
        select(
            Transaction.created_at,
            Transaction.amount,
            Wallet.currency,
        )
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.status == "completed",
            Transaction.type == "credit",
            Transaction.reference.like("escrow_release:%"),
        )
        .order_by(Transaction.created_at)
    ).all()

    # Aggregate by YYYY-MM
    _rev_by_month: dict[str, dict] = {}
    for row in revenue_rows:
        dt = row.created_at
        key = f"{dt.year}-{str(dt.month).zfill(2)}"
        if key not in _rev_by_month:
            _rev_by_month[key] = {"revenue": Decimal("0"), "count": 0, "currency": row.currency}
        _rev_by_month[key]["revenue"] += row.amount
        _rev_by_month[key]["count"] += 1

    monthly_revenue_list = [
        {
            "month": k,
            "revenue": str(v["revenue"]),
            "transactions": v["count"],
            "currency": v["currency"],
        }
        for k, v in sorted(_rev_by_month.items())[-6:]
    ]

    # Top countries by user count
    country_counts = db.execute(
        select(
            User.country_code.label("country"),
            _func.count(User.id).label("users"),
        )
        .where(User.country_code.isnot(None))
        .group_by(User.country_code)
        .order_by(desc(_func.count(User.id)))
        .limit(10)
    ).all()

    # KYC stats
    kyc_counts = db.execute(
        select(KycSubmission.status, _func.count(KycSubmission.id).label("count"))
        .group_by(KycSubmission.status)
    ).all()

    # Dispute stats
    dispute_counts = db.execute(
        select(DisputeRecord.status, _func.count(DisputeRecord.id).label("count"))
        .group_by(DisputeRecord.status)
    ).all()

    return success_response({
        "users_by_role": users_by_role,
        "tasks_by_status": tasks_by_status,
        "monthly_revenue": monthly_revenue_list,
        "top_countries": [
            {"country": r.country, "users": r.users}
            for r in country_counts
        ],
        "kyc_by_status": {r.status: r.count for r in kyc_counts},
        "disputes_by_status": {r.status: r.count for r in dispute_counts},
    })


@router.get("/tasks")
def list_all_tasks(
    status: str | None = Query(default=None, description="Filter by task status"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = select(Task).order_by(desc(Task.created_at)).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Task.status == status.upper())
    tasks = db.execute(stmt).scalars().all()
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
                "latitude": t.latitude,
                "longitude": t.longitude,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    )


class AdminTaskAssignPayload(BaseModel):
    tasker_id: str


class AdminTaskCancelPayload(BaseModel):
    reason: str = ""


@router.post("/tasks/{task_id}/assign")
def admin_force_assign_task(
    task_id: str,
    payload: AdminTaskAssignPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    """Force-assign a task to a specific tasker (admin override)."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    tasker = db.get(User, payload.tasker_id)
    if tasker is None:
        raise HTTPException(status_code=404, detail="Tasker introuvable")
    if task.status not in {"OPEN", "ASSIGNED"}:
        raise HTTPException(status_code=409, detail=f"Tâche ne peut pas être assignée (statut: {task.status})")
    task.assigned_to = payload.tasker_id
    task.status = "ASSIGNED"
    db.commit()
    db.refresh(task)
    return success_response({
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "assigned_by_admin": admin_id,
    })


@router.post("/tasks/{task_id}/cancel")
def admin_cancel_task(
    task_id: str,
    payload: AdminTaskCancelPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    """Cancel a task and refund escrow if funded (admin action)."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    if task.status == "COMPLETED":
        raise HTTPException(status_code=409, detail="Impossible d'annuler une tâche déjà complétée")

    # Refund any active escrow
    escrow = svc.get_escrow_by_task(task_id)
    escrow_refunded = False
    if escrow and escrow.status in {"pending", "funded", "hold"}:
        try:
            if escrow.status == "pending":
                svc.cancel_pending_escrow(escrow.id)
            else:
                svc.refund_escrow(escrow.id)
            escrow_refunded = True
        except Exception as e:
            raise HTTPException(status_code=409, detail=f"Impossible de rembourser l'escrow: {e}")

    task.status = "CANCELLED"
    db.commit()
    return success_response({
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "escrow_refunded": escrow_refunded,
        "cancelled_by_admin": admin_id,
        "reason": payload.reason,
    })


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


@router.post("/ledger/reconcile")
def ledger_reconcile(
    user_id: str | None = None,
    currency: str | None = None,
    dry_run: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """
    Ledger reconciliation — compare wallet.balance vs ledger-computed balance.

    The ledger (Transaction table) is the single source of truth.
    wallet.balance is a denormalized cache; any drift is corrected here.

    Query params:
      user_id + currency  → reconcile one specific wallet
      (none)              → reconcile all wallets
      dry_run=true        → report only, do not write corrections (default)
      dry_run=false       → apply corrections to wallet.balance
    """
    from app.services.wallet_service import LedgerDriftError

    wallet_svc = WalletService(db)
    drift_report = []

    if user_id and currency:
        wallets = (
            db.execute(
                select(Wallet).where(
                    Wallet.user_id == user_id,
                    Wallet.currency == currency.upper(),
                )
            )
            .scalars()
            .all()
        )
    else:
        wallets = db.execute(select(Wallet)).scalars().all()

    for wallet in wallets:
        computed = wallet_svc.recompute_balance_from_ledger(wallet.user_id, wallet.currency)
        diff = wallet.balance - computed
        if abs(diff) > Decimal("0.000001"):
            drift_report.append({
                "user_id": wallet.user_id,
                "currency": wallet.currency,
                "wallet_balance": str(wallet.balance),
                "ledger_computed": str(computed),
                "drift": str(diff),
                "corrected": not dry_run,
            })
            if not dry_run:
                wallet.balance = computed

    if not dry_run and drift_report:
        db.commit()

    return success_response({
        "wallets_checked": len(wallets),
        "drifts_found": len(drift_report),
        "drifts_corrected": len(drift_report) if not dry_run else 0,
        "dry_run": dry_run,
        "drift_report": drift_report,
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


# ── Admin user detail & management ───────────────────────────────────────────

def _user_display_name(u: User) -> str:
    if u.full_name:
        return u.full_name
    parts = " ".join(filter(None, [u.first_name, u.last_name])).strip()
    return parts or u.email or u.phone or u.id[:8]


def _serialize_user_full(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "phone": u.phone,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "full_name": u.full_name,
        "role": u.role,
        "is_verified": u.is_verified,
        "is_suspended": getattr(u, "is_suspended", False),
        "is_locked": getattr(u, "is_locked", False),
        "ban_reason": getattr(u, "ban_reason", None),
        "suspension_reason": getattr(u, "suspension_reason", None),
        "country_code": u.country_code,
        "created_at": u.created_at.isoformat(),
    }


@router.get("/users/lookup")
def lookup_user_by_phone(
    phone: str = Query(..., description="Phone number to look up"),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Find a user by phone number (exact match)."""
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable pour ce numéro")

    # Wallet info
    wallets = db.query(Wallet).filter(Wallet.user_id == user.id).all()
    wallet_info = [
        {"currency": w.currency, "balance": str(w.balance)}
        for w in wallets
    ]

    # Recent transactions (5 most recent)
    recent_txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(desc(Transaction.created_at))
        .limit(5)
        .all()
    ) if hasattr(Transaction, "user_id") else []

    # Active tasks
    active_tasks = (
        db.query(Task)
        .filter(
            (Task.created_by == user.id) | (Task.assigned_to == user.id),
            Task.status.in_(["OPEN", "ASSIGNED"]),
        )
        .limit(5)
        .all()
    )

    data = _serialize_user_full(user)
    data["wallets"] = wallet_info
    data["wallet"] = wallet_info[0] if wallet_info else None
    data["recent_transactions"] = [
        {
            "id": tx.id,
            "type": tx.type,
            "amount": str(tx.amount),
            "currency": getattr(tx, "currency", "XOF"),
            "status": tx.status,
            "provider": tx.provider,
            "created_at": tx.created_at.isoformat(),
        }
        for tx in recent_txs
    ]
    data["active_tasks"] = [
        {"id": t.id, "title": t.title, "status": t.status, "price": str(t.price), "currency": t.currency}
        for t in active_tasks
    ]
    return success_response(data)


@router.get("/users/{user_id}")
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    wallets = db.query(Wallet).filter(Wallet.user_id == user_id).all()
    wallet_info = [{"currency": w.currency, "balance": str(w.balance)} for w in wallets]

    # Build a single wallet summary (first wallet with locked escrow sum)
    wallet_summary = None
    if wallet_info:
        locked = (
            db.query(Escrow)
            .filter(Escrow.payer_id == user_id, Escrow.status == "funded")
            .all()
        )
        locked_balance = sum(e.amount for e in locked)
        wallet_summary = {
            **wallet_info[0],
            "locked_balance": str(locked_balance),
        }

    recent_txs = []
    if wallets:
        wallet_ids = [w.id for w in wallets]
        recent_txs = (
            db.query(Transaction)
            .filter(Transaction.wallet_id.in_(wallet_ids))
            .order_by(desc(Transaction.created_at))
            .limit(5)
            .all()
        )

    active_tasks = (
        db.query(Task)
        .filter(
            (Task.created_by == user_id) | (Task.assigned_to == user_id),
            Task.status.in_(["OPEN", "ASSIGNED"]),
        )
        .limit(5)
        .all()
    )

    # KYC status
    kyc = (
        db.query(KycSubmission)
        .filter(KycSubmission.user_id == user_id)
        .order_by(desc(KycSubmission.created_at))
        .first()
    )

    data = _serialize_user_full(user)
    data["kyc_status"] = kyc.status if kyc else "not_submitted"
    data["wallet"] = wallet_summary
    data["recent_transactions"] = [
        {
            "id": tx.id,
            "type": tx.type,
            "amount": str(tx.amount),
            "currency": getattr(tx, "currency", "XOF"),
            "status": tx.status,
            "provider": tx.provider,
            "created_at": tx.created_at.isoformat(),
        }
        for tx in recent_txs
    ]
    data["active_tasks"] = [
        {"id": t.id, "title": t.title, "status": t.status, "price": str(t.price), "currency": t.currency}
        for t in active_tasks
    ]
    return success_response(data)


class UserActionPayload(BaseModel):
    reason: str = ""


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_suspended = True
    user.suspension_reason = payload.reason or f"Suspendu par admin {admin_id}"
    db.commit()
    return success_response({"user_id": user_id, "is_suspended": True})


@router.post("/users/{user_id}/unsuspend")
def unsuspend_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_suspended = False
    user.suspension_reason = None
    db.commit()
    return success_response({"user_id": user_id, "is_suspended": False})


@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_suspended = True
    user.ban_reason = payload.reason or f"Banni par admin {admin_id}"
    db.commit()
    return success_response({"user_id": user_id, "banned": True})


@router.post("/users/{user_id}/verify")
def verify_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_verified = True
    db.commit()
    return success_response({"user_id": user_id, "is_verified": True})


@router.post("/users/{user_id}/lock")
def lock_user(
    user_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_locked = True
    user.suspension_reason = payload.reason or f"Verrouillé par admin {admin_id}"
    db.commit()
    return success_response({"user_id": user_id, "is_locked": True})


@router.post("/users/{user_id}/unlock")
def unlock_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_locked = False
    db.commit()
    return success_response({"user_id": user_id, "is_locked": False})


# ── Admin transactions ────────────────────────────────────────────────────────

@router.get("/transactions")
def list_transactions(
    user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    import json as _json

    stmt = (
        select(Transaction, Wallet, User)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .join(User, Wallet.user_id == User.id)
        .order_by(desc(Transaction.created_at))
        .limit(limit)
    )
    if user_id:
        stmt = stmt.where(Wallet.user_id == user_id)
    if status:
        stmt = stmt.where(Transaction.status == status)
    rows = db.execute(stmt).all()

    def _business_type(tx: Transaction) -> str:
        """Extract business type from metadata_json, fallback to raw type."""
        if tx.metadata_json:
            try:
                meta = _json.loads(tx.metadata_json)
                if isinstance(meta, dict) and "type" in meta:
                    return meta["type"]
            except Exception:
                pass
        # Map raw types: credit → deposit (incoming), debit → withdrawal
        return "deposit" if tx.type == "credit" else "withdrawal"

    result = [
        {
            "id": tx.id,
            "user_id": wallet.user_id,
            "user_name": _user_display_name(user),
            "user_phone": user.phone,
            "type": _business_type(tx),
            "amount": str(tx.amount),
            "currency": wallet.currency,
            "status": tx.status,
            "provider": tx.provider,
            "reference": tx.reference,
            "created_at": tx.created_at.isoformat(),
        }
        for tx, wallet, user in rows
    ]
    # Optional: filter by business type after extraction
    if type:
        result = [r for r in result if r["type"] == type]
    return success_response(result)


@router.post("/transactions/{tx_id}/retry")
def retry_transaction(
    tx_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Alias: find the payout linked to this transaction and queue a retry."""
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    payout = db.query(Payout).filter(Payout.transaction_id == tx_id).one_or_none()
    if payout is None:
        raise HTTPException(status_code=404, detail="Aucun payout lié à cette transaction")
    if payout.status == "completed":
        raise HTTPException(status_code=409, detail="Payout déjà complété")
    payout.retry_count = 0
    payout.status = "failed"
    db.commit()
    from app.workers.payout_worker import retry_payout
    job = retry_payout.delay(payout.id)
    return success_response({"tx_id": tx_id, "payout_id": payout.id, "job_id": job.id})


# ── Admin escrows ─────────────────────────────────────────────────────────────

@router.get("/escrows")
def list_escrows(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(Escrow, Task)
        .join(Task, Escrow.task_id == Task.id, isouter=True)
        .order_by(desc(Escrow.created_at))
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Escrow.status == status)
    rows = db.execute(stmt).all()

    def _get_user_name(uid: str | None) -> str | None:
        if not uid:
            return None
        u = db.get(User, uid)
        return _user_display_name(u) if u else None

    return success_response([
        {
            "escrow_id": esc.id,
            "task_id": esc.task_id,
            "task_title": task.title if task else None,
            "client_id": esc.payer_id,
            "client_name": _get_user_name(esc.payer_id),
            "tasker_id": esc.payee_id,
            "tasker_name": _get_user_name(esc.payee_id),
            "amount": str(esc.amount),
            "currency": esc.currency,
            "status": esc.status,
            "created_at": esc.created_at.isoformat(),
        }
        for esc, task in rows
    ])


@router.post("/escrows/{escrow_id}/release")
def admin_release_escrow(
    escrow_id: str,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        escrow = svc.release_escrow(escrow_id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return success_response({"escrow_id": escrow.id, "status": escrow.status, "released_by_admin": admin_id})


@router.post("/escrows/{escrow_id}/refund")
def admin_refund_escrow(
    escrow_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        escrow = svc.refund_escrow(escrow_id)
        svc.finalize_transaction(escrow.id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return success_response({"escrow_id": escrow.id, "status": escrow.status, "refunded_by_admin": admin_id})


# ── Admin wallet adjust ───────────────────────────────────────────────────────

class WalletAdjustPayload(BaseModel):
    user_id: str
    amount: str
    currency: str
    reason: str


@router.post("/wallet/adjust")
def admin_wallet_adjust(
    payload: WalletAdjustPayload,
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        amount = Decimal(payload.amount)
        if amount == 0:
            raise HTTPException(status_code=400, detail="Le montant ne peut pas être zéro")
        reference = f"admin_adjust:{payload.user_id}:{payload.currency}:{int(amount*100)}"
        if amount > 0:
            tx = svc.credit_wallet(
                user_id=payload.user_id,
                currency=payload.currency.upper(),
                amount=amount,
                reference=reference,
                provider="admin",
                metadata={"type": "adjustment", "reason": payload.reason, "admin_id": admin_id},
            )
        else:
            tx = svc.debit_wallet(
                user_id=payload.user_id,
                currency=payload.currency.upper(),
                amount=abs(amount),
                reference=reference,
                provider="admin",
                metadata={"type": "adjustment", "reason": payload.reason, "admin_id": admin_id},
            )
        return success_response({"tx_id": tx.id, "amount": str(amount), "currency": payload.currency})
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Payment providers status ──────────────────────────────────────────────────

@router.get("/providers")
def list_payment_providers(
    _: str = Depends(require_admin),
):
    """Return static provider status derived from country configs."""
    providers = []
    seen: set[str] = set()
    for cfg in COUNTRY_CONFIGS.values():
        for provider_name in (cfg.payment_providers or []):
            if provider_name in seen:
                continue
            seen.add(provider_name)
            providers.append({
                "id": provider_name,
                "name": provider_name.replace("_", " ").title(),
                "type": "mobile_money" if provider_name not in {"stripe"} else "card",
                "countries": [
                    c.country_code
                    for c in COUNTRY_CONFIGS.values()
                    if provider_name in (c.payment_providers or [])
                ],
                "status": "operational",
                "success_rate": 98.5,
            })
    return success_response(providers)


# ── Support tickets ───────────────────────────────────────────────────────────

class SupportTicketCreatePayload(BaseModel):
    user_id: str
    category: str = "other"
    priority: str = "medium"
    subject: str
    description: str


class SupportTicketUpdatePayload(BaseModel):
    notes: str | None = None
    status: str | None = None
    priority: str | None = None


class SupportTicketResolvePayload(BaseModel):
    notes: str = ""


class SupportRefundPayload(BaseModel):
    user_id: str
    amount: str
    currency: str
    reason: str
    ticket_id: str | None = None


def _serialize_ticket(t: SupportTicket, db: Session) -> dict:
    user = db.get(User, t.user_id)
    now = datetime.now(timezone.utc)
    wait_minutes = int((now - t.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60) if t.status == "open" else 0
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_name": _user_display_name(user) if user else t.user_id,
        "user_phone": user.phone if user else None,
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "subject": t.subject,
        "description": t.description,
        "notes": t.notes,
        "agent_id": t.agent_id,
        "wait_minutes": wait_minutes,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


@router.get("/support")
def list_support_tickets(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.is_deleted.is_(False))
        .order_by(desc(SupportTicket.created_at))
        .limit(limit)
    )
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    tickets = db.execute(stmt).scalars().all()
    return success_response([_serialize_ticket(t, db) for t in tickets])


@router.post("/support")
def create_support_ticket(
    payload: SupportTicketCreatePayload,
    db: Session = Depends(get_db),
    agent_id: str = Depends(require_admin),
):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    ticket = SupportTicket(
        user_id=payload.user_id,
        agent_id=agent_id,
        category=payload.category,
        priority=payload.priority,
        subject=payload.subject,
        description=payload.description,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.patch("/support/{ticket_id}")
def update_support_ticket(
    ticket_id: str,
    payload: SupportTicketUpdatePayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if payload.notes is not None:
        ticket.notes = payload.notes
    if payload.status is not None:
        ticket.status = payload.status
    if payload.priority is not None:
        ticket.priority = payload.priority
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.post("/support/{ticket_id}/resolve")
def resolve_support_ticket(
    ticket_id: str,
    payload: SupportTicketResolvePayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    ticket.status = "resolved"
    if payload.notes:
        ticket.notes = payload.notes
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.post("/support/{ticket_id}/escalate")
def escalate_support_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    ticket.status = "escalated"
    ticket.priority = "urgent"
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.post("/support/refund")
def support_refund(
    payload: SupportRefundPayload,
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
):
    """Trigger a manual refund from the support desk."""
    try:
        amount = Decimal(payload.amount)
        reference = f"support_refund:{payload.user_id}:{payload.ticket_id or 'manual'}"
        tx = svc.credit_wallet(
            user_id=payload.user_id,
            currency=payload.currency.upper(),
            amount=amount,
            reference=reference,
            provider="admin",
            metadata={
                "type": "refund",
                "reason": payload.reason,
                "admin_id": admin_id,
                "ticket_id": payload.ticket_id,
            },
        )
        # Link ticket to resolved if ticket_id given
        if payload.ticket_id:
            ticket = db.get(SupportTicket, payload.ticket_id)
            if ticket:
                ticket.notes = (ticket.notes or "") + f"\nRemboursement {amount} {payload.currency} effectué."
                ticket.updated_at = datetime.now(timezone.utc)
                db.commit()
        return success_response({"tx_id": tx.id, "reference": reference, "amount": str(amount)})
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationPayload(BaseModel):
    user_id: str
    message: str
    channel: str  # "sms" | "push"


@router.post("/notifications/send")
def send_notification(
    payload: NotificationPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    """Send an SMS or push notification to a user."""
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    sent = False
    if payload.channel == "sms" and user.phone:
        try:
            from app.core.sms import send_sms
            send_sms(phone=user.phone, message=payload.message)
            sent = True
        except Exception:
            pass
    elif payload.channel == "push":
        from app.services.push_service import get_push_service
        push_svc = get_push_service()
        if user.fcm_token:
            sent = push_svc.send(
                fcm_token=user.fcm_token,
                title="Message de l'équipe ZASKA",
                body=payload.message,
                data={"admin_id": admin_id},
            )
        else:
            from app.core.observability import logger
            logger.info(
                "admin:push_notification_no_token user=%s admin=%s message=%s",
                payload.user_id, admin_id, payload.message[:100],
            )
            sent = False

    return success_response({
        "user_id": payload.user_id,
        "channel": payload.channel,
        "sent": sent,
        "note": "SMS envoyé" if (sent and payload.channel == "sms")
        else ("Push envoyé" if sent else "Token FCM manquant ou FCM non configuré"),
    })
