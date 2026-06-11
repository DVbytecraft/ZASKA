from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SocialProtectionEvent(Base):
    __tablename__ = "social_protection_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "event_type",
            "period_key",
            "currency",
            name="uq_social_protection_event_scope",
        ),
        Index("ix_social_protection_event_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    period_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="completed")
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
