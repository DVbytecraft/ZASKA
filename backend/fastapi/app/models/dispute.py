"""
Dispute and reconciliation models.

DisputeRecord — tracks user-raised disputes and admin-initiated reversals.
ReconciliationReport — stores the output of each scheduled reconciliation run.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class DisputeRecord(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id"), nullable=True, index=True
    )
    escrow_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("escrows.id"), nullable=True, index=True
    )
    counterparty_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    opened_by_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    escalated_to_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    # At least one of these must be set
    transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id"), nullable=True, index=True
    )
    payout_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payouts.id"), nullable=True, index=True
    )

    # "reversal" | "dispute" | "fraud_report"
    dispute_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # "open" | "under_review" | "resolved" | "rejected" | "escalated"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolution_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)

    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when dispute is resolved via a reversal transaction
    resolution_tx_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id"), nullable=True
    )
    task_snapshot_json: Mapped[str | None] = mapped_column("task_snapshot", Text, nullable=True)
    chat_snapshot_json: Mapped[str | None] = mapped_column("chat_snapshot", Text, nullable=True)
    geo_snapshot_json: Mapped[str | None] = mapped_column("geo_snapshot", Text, nullable=True)
    photos_snapshot_json: Mapped[str | None] = mapped_column("photos_snapshot", Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class DisputeEvent(Base):
    __tablename__ = "dispute_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dispute_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("disputes.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column("payload", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    country_code: Mapped[str] = mapped_column(String(4), nullable=False, default="ALL")

    # Summary counts
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inconsistent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repaired_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Full JSON report for auditing
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
