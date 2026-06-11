from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ReferralProgram(Base):
    __tablename__ = "referral_programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    referral_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    reward_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    reward_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    qualification_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ReferralEvent(Base):
    __tablename__ = "referral_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    referral_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    referral_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    referrer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    referred_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("referral_programs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    qualification_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    progress_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    trigger_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    reward_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    reward_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    referral_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("referral_events.id"), nullable=False, index=True)
    beneficiary_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    reward_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    amount_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    amount_remaining: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="AVAILABLE", index=True)
    wallet_transaction_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    applied_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
