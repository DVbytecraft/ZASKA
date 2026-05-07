import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskApplication(Base):
    __tablename__ = "task_applications"

    __table_args__ = (
        UniqueConstraint("task_id", "tasker_id", name="uq_application_task_tasker"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    tasker_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    proposed_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
