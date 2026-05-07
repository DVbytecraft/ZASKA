"""Relevés de compte — historique des tâches et des paiements."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.responses import success_response
from app.models.task import Task
from app.models.wallet import Escrow, Transaction, Wallet

router = APIRouter(prefix="/statement", tags=["statement"])


@router.get("")
def get_statement(
    currency: str = "USD",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Relevé complet : tâches créées, tâches exécutées, transactions wallet."""
    currency_upper = currency.upper()

    # Tasks created by this user
    tasks_created = (
        db.execute(
            select(Task).where(Task.created_by == user_id).order_by(Task.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Tasks executed by this user
    tasks_executed = (
        db.execute(
            select(Task).where(Task.assigned_to == user_id).order_by(Task.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Wallet transactions
    wallet = db.execute(
        select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency_upper)
    ).scalars().one_or_none()

    transactions = []
    balance = "0"
    if wallet:
        balance = str(wallet.balance)
        tx_rows = db.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
            .limit(200)
        ).scalars().all()
        transactions = [
            {
                "id": tx.id,
                "type": tx.type,
                "amount": str(tx.amount),
                "status": tx.status,
                "reference": tx.reference,
                "provider": tx.provider,
                "createdAt": tx.created_at.isoformat(),
            }
            for tx in tx_rows
        ]

    # Escrows as payer (client paid)
    escrows_paid = db.execute(
        select(Escrow).where(Escrow.payer_id == user_id).order_by(Escrow.created_at.desc())
    ).scalars().all()

    # Escrows as payee (executor received)
    escrows_received = db.execute(
        select(Escrow).where(Escrow.payee_id == user_id).order_by(Escrow.created_at.desc())
    ).scalars().all()

    def _task_summary(t: Task) -> dict:
        return {
            "id": t.id,
            "title": t.title,
            "price": float(t.price),
            "currency": t.currency,
            "status": t.status,
            "completionPercent": t.completion_percent,
            "createdAt": t.created_at.isoformat(),
        }

    def _escrow_summary(e: Escrow) -> dict:
        return {
            "id": e.id,
            "taskId": e.task_id,
            "amount": str(e.amount),
            "currency": e.currency,
            "status": e.status,
            "createdAt": e.created_at.isoformat(),
        }

    # Totals
    total_paid = sum(float(e.amount) for e in escrows_paid if e.status in {"released", "partial_released"})
    total_received = sum(float(e.amount) for e in escrows_received if e.status in {"released", "partial_released"})
    total_tasks_created = len(tasks_created)
    total_tasks_executed = len(tasks_executed)

    return success_response({
        "summary": {
            "currency": currency_upper,
            "walletBalance": balance,
            "totalTasksCreated": total_tasks_created,
            "totalTasksExecuted": total_tasks_executed,
            "totalPaidAsClient": round(total_paid, 2),
            "totalReceivedAsExecutor": round(total_received, 2),
        },
        "tasksCreated": [_task_summary(t) for t in tasks_created],
        "tasksExecuted": [_task_summary(t) for t in tasks_executed],
        "escrowsAsPayer": [_escrow_summary(e) for e in escrows_paid],
        "escrowsAsPayee": [_escrow_summary(e) for e in escrows_received],
        "transactions": transactions,
    })
