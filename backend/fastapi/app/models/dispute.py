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

    # "open" | "resolved" | "rejected"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")

    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when dispute is resolved via a reversal transaction
    resolution_tx_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
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
