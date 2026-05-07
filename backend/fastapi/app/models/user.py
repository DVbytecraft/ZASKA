import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="client")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
