"""TaskCompletionCode — codes email pour valider la fin d'une tâche.

Les deux parties (client + exécutant) reçoivent chacune un code unique par email.
Le paiement n'est libéré que lorsque les deux codes sont validés.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TaskCompletionCode(Base):
    __tablename__ = "task_completion_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    # "client" | "executor"
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    # HMAC-SHA256 du code à 6 chiffres
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # Code valable 48h
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
