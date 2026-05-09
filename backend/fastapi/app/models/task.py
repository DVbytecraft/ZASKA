import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_task_assigned_to", "assigned_to"),
        Index("ix_task_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8))
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Completion tracking
    completion_percent: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # Price negotiation
    negotiation_status: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    negotiated_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    negotiated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    any_schedule: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Task mode: "fast" (instant accept) | "choose" (applications)
    mode: Mapped[str] = mapped_column(String(8), default="fast", nullable=False, server_default="fast")

    # Creation idempotency — prevents double-submit
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)

    # Multi-stop: [{address, latitude, longitude}, ...]
    stops: Mapped[list | None] = mapped_column(JSON, nullable=True)
