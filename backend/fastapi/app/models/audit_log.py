from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class FinancialAuditLog(Base):
    """Append-only financial audit trail persisted to DB.

    Records are immutable by convention — never update or delete rows.
    Complements the structured log stream for long-term traceability.
    """

    __tablename__ = "financial_audit_logs"
    __table_args__ = (
        Index("ix_audit_user_id",  "user_id"),
        Index("ix_audit_action",   "action"),
        Index("ix_audit_created",  "created_at"),
    )

    id: Mapped[str]       = mapped_column(String(36), primary_key=True, default=_uuid)
    action: Mapped[str]   = mapped_column(String(64), nullable=False)
    user_id: Mapped[str]  = mapped_column(String(36), nullable=False)
    payment_id: Mapped[str]     = mapped_column(String(255), nullable=False, default="")
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    amount: Mapped[Decimal]     = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str]       = mapped_column(String(10), nullable=False)
    provider: Mapped[str]       = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str]         = mapped_column(String(32), nullable=False)
    state_before: Mapped[str]   = mapped_column(String(255), nullable=False, default="")
    state_after: Mapped[str]    = mapped_column(String(255), nullable=False, default="")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    country_code: Mapped[str]   = mapped_column(String(10), nullable=False, default="")
    request_id: Mapped[str]     = mapped_column(String(64), nullable=False, default="")
    extra: Mapped[str | None]   = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
