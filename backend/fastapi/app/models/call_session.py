import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), index=True)
    caller_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    callee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    media_type: Mapped[str] = mapped_column(String(8))   # 'audio' | 'video'
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending → active → ended | rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
