"""
Payout model — tracks lifecycle of Mobile Money withdrawals.

States:
  pending    → record created, wallet debited, API call not yet attempted
  processing → API call submitted to provider
  completed  → provider confirmed the transfer
  failed     → provider rejected; wallet was re-credited automatically

provider_tx_id is persisted here independently of Transaction.metadata_json
so it can be indexed and queried efficiently.
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


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id"), nullable=True, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Stored as last-4 digits in plain, full number only in metadata_json
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    country_code: Mapped[str] = mapped_column(String(4), nullable=False)
    reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    # pending | processing | completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    provider_tx_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Set by admin for manual resolution
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
