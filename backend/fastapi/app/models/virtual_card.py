"""VirtualCard — carte de crédit virtuelle Visa/Mastercard générée pour chaque utilisateur."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class VirtualCard(Base):
    __tablename__ = "virtual_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # "visa" | "mastercard"
    card_type: Mapped[str] = mapped_column(String(12), nullable=False)
    # "4532 **** **** 1234" — masqué, pour affichage frontend
    card_number_masked: Mapped[str] = mapped_column(String(24), nullable=False)
    # HMAC-SHA256 du numéro complet — pour vérification sans stocker en clair
    card_number_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expiry_month: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # HMAC-SHA256 du CVV
    cvv_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # "active" | "frozen" | "cancelled"
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")
    # Portefeuille lié à la carte
    wallet_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
