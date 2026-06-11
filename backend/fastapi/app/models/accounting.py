from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (UniqueConstraint("code", "currency", name="uq_financial_account_code_currency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="global", server_default="global")
    scope_value: Mapped[str] = mapped_column(String(64), nullable=False, default="*", server_default="*")
    module_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FinancialAccountScope(Base):
    __tablename__ = "financial_account_scopes"
    __table_args__ = (UniqueConstraint("account_id", "scope_type", "scope_value", name="uq_financial_account_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("reference", "account_id", "direction", name="uq_ledger_entry_ref_account_direction"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    journal_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_table: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    module_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(64), nullable=False, default="wallet_mirror", server_default="wallet_mirror")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class FundTransfer(Base):
    __tablename__ = "fund_transfers"
    __table_args__ = (UniqueConstraint("reference", name="uq_fund_transfer_reference"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    from_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    to_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="completed", server_default="completed")
    transfer_type: Mapped[str] = mapped_column(String(64), nullable=False, default="internal_fund_transfer", server_default="internal_fund_transfer")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ReconciliationSnapshot(Base):
    __tablename__ = "reconciliation_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", "account_id", "currency", name="uq_reconciliation_snapshot_account_day"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    ledger_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_wallet_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    drift_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ok", server_default="ok")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class CountryRevenueSnapshot(Base):
    __tablename__ = "country_revenue_snapshots"
    __table_args__ = (UniqueConstraint("period_key", "country_code", "currency", name="uq_country_revenue_snapshot_period_country_currency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    period_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    gross_task_volume: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    tasker_net_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    zaska_revenue_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    pension_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    health_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    smoothing_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
