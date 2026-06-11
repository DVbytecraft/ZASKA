from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subscription_type: Mapped[str] = mapped_column(String(24), nullable=False, default="GENERAL")
    service_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False, default="MONTHLY")
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    tasks_included_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overage_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    priority_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    diaspora_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    support_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("subscription_plans.id"), nullable=False, index=True)
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subscription_type: Mapped[str] = mapped_column(String(24), nullable=False)
    service_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", index=True)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    tasks_included_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tasks_used_this_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    renewal_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="self_service")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SubscriptionUsage(Base):
    __tablename__ = "subscription_usages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subscription_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_subscriptions.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    service_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    benefit_type: Mapped[str] = mapped_column(String(24), nullable=False, default="SERVICE_QUOTA")
    units_used: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    amount_saved: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    period_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
