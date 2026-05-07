"""
Wallet Engine — tables financières internes de ZASKA PAY.

- wallets      : solde par utilisateur/devise
- transactions : grand-livre ACID (tous les mouvements)
- escrows      : réserves de fonds liées aux tâches
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("user_id", "currency", name="uq_wallet_user_currency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    # NUMERIC(20,6) → supporte XOF (entier) et EUR/USD (2 décimales)
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Transaction(Base):
    """Grand-livre immuable — aucune ligne ne doit jamais être supprimée."""

    __tablename__ = "transactions"
    __table_args__ = (Index("ix_tx_wallet_created", "wallet_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    wallet_id: Mapped[str] = mapped_column(String(36), ForeignKey("wallets.id"), nullable=False, index=True)
    # credit | debit
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    # pending | completed | failed | reversed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # stripe | fedapay | flutterwave | internal
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    # JSON libre pour métadonnées (task_id, escrow_id, etc.)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Escrow(Base):
    """
    Réserve de fonds garantissant le paiement d'une tâche.

    Cycle :  PENDING → FUNDED → RELEASED | REFUNDED
    """

    __tablename__ = "escrows"
    __table_args__ = (Index("ix_escrow_task", "task_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    payer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    payee_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    # pending | funded | hold | released | refunded | contested | partial_released
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    # référence du paiement externe (provider → escrow)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_tx_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # référence de la transaction de financement (wallet ledger)
    funding_tx_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True)
    # référence de la transaction de libération/remboursement
    settlement_tx_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True)
    # 24h hold: funds available only after this timestamp (no contest = auto-release)
    payout_available_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # timestamp when client contested the work
    contested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
