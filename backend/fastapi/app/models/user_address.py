"""UserAddress — adresses enregistrées par l'utilisateur (maison, bureau, etc.)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)           # "Maison", "Bureau", …
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
