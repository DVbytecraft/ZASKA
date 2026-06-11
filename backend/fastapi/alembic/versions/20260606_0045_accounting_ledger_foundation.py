"""accounting ledger foundation

Revision ID: 20260606_0045
Revises: 20260606_0044
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0045"
down_revision = "20260606_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="global"),
        sa.Column("scope_value", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "currency", name="uq_financial_account_code_currency"),
    )
    op.create_index(op.f("ix_financial_accounts_account_type"), "financial_accounts", ["account_type"], unique=False)
    op.create_index(op.f("ix_financial_accounts_code"), "financial_accounts", ["code"], unique=False)
    op.create_index(op.f("ix_financial_accounts_currency"), "financial_accounts", ["currency"], unique=False)
    op.create_index(op.f("ix_financial_accounts_module_code"), "financial_accounts", ["module_code"], unique=False)
    op.create_index(op.f("ix_financial_accounts_owner_user_id"), "financial_accounts", ["owner_user_id"], unique=False)

    op.create_table(
        "financial_account_scopes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_value", sa.String(length=64), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["financial_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "scope_type", "scope_value", name="uq_financial_account_scope"),
    )
    op.create_index(op.f("ix_financial_account_scopes_account_id"), "financial_account_scopes", ["account_id"], unique=False)
    op.create_index(op.f("ix_financial_account_scopes_module_code"), "financial_account_scopes", ["module_code"], unique=False)
    op.create_index(op.f("ix_financial_account_scopes_scope_type"), "financial_account_scopes", ["scope_type"], unique=False)
    op.create_index(op.f("ix_financial_account_scopes_scope_value"), "financial_account_scopes", ["scope_value"], unique=False)

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("journal_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("entry_type", sa.String(length=64), nullable=False, server_default="wallet_mirror"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["financial_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", "account_id", "direction", name="uq_ledger_entry_ref_account_direction"),
    )
    op.create_index(op.f("ix_ledger_entries_account_id"), "ledger_entries", ["account_id"], unique=False)
    op.create_index(op.f("ix_ledger_entries_country_code"), "ledger_entries", ["country_code"], unique=False)
    op.create_index(op.f("ix_ledger_entries_currency"), "ledger_entries", ["currency"], unique=False)
    op.create_index(op.f("ix_ledger_entries_direction"), "ledger_entries", ["direction"], unique=False)
    op.create_index(op.f("ix_ledger_entries_entry_type"), "ledger_entries", ["entry_type"], unique=False)
    op.create_index(op.f("ix_ledger_entries_journal_id"), "ledger_entries", ["journal_id"], unique=False)
    op.create_index(op.f("ix_ledger_entries_module_code"), "ledger_entries", ["module_code"], unique=False)
    op.create_index(op.f("ix_ledger_entries_reference"), "ledger_entries", ["reference"], unique=False)
    op.create_index(op.f("ix_ledger_entries_source_id"), "ledger_entries", ["source_id"], unique=False)
    op.create_index(op.f("ix_ledger_entries_source_table"), "ledger_entries", ["source_table"], unique=False)

    op.create_table(
        "fund_transfers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("from_account_id", sa.String(length=36), nullable=False),
        sa.Column("to_account_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("transfer_type", sa.String(length=64), nullable=False, server_default="internal_fund_transfer"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_account_id"], ["financial_accounts.id"]),
        sa.ForeignKeyConstraint(["to_account_id"], ["financial_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", name="uq_fund_transfer_reference"),
    )
    op.create_index(op.f("ix_fund_transfers_currency"), "fund_transfers", ["currency"], unique=False)
    op.create_index(op.f("ix_fund_transfers_from_account_id"), "fund_transfers", ["from_account_id"], unique=False)
    op.create_index(op.f("ix_fund_transfers_reference"), "fund_transfers", ["reference"], unique=False)
    op.create_index(op.f("ix_fund_transfers_to_account_id"), "fund_transfers", ["to_account_id"], unique=False)

    op.create_table(
        "reconciliation_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("ledger_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_wallet_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("drift_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ok"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["financial_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_date", "account_id", "currency", name="uq_reconciliation_snapshot_account_day"),
    )
    op.create_index(op.f("ix_reconciliation_snapshots_account_id"), "reconciliation_snapshots", ["account_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_snapshots_currency"), "reconciliation_snapshots", ["currency"], unique=False)
    op.create_index(op.f("ix_reconciliation_snapshots_snapshot_date"), "reconciliation_snapshots", ["snapshot_date"], unique=False)

    op.create_table(
        "country_revenue_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("gross_task_volume", sa.Numeric(20, 6), nullable=False),
        sa.Column("tasker_net_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("zaska_revenue_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("pension_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("health_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("smoothing_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("completed_tasks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_key", "country_code", "currency", name="uq_country_revenue_snapshot_period_country_currency"),
    )
    op.create_index(op.f("ix_country_revenue_snapshots_country_code"), "country_revenue_snapshots", ["country_code"], unique=False)
    op.create_index(op.f("ix_country_revenue_snapshots_currency"), "country_revenue_snapshots", ["currency"], unique=False)
    op.create_index(op.f("ix_country_revenue_snapshots_period_key"), "country_revenue_snapshots", ["period_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_country_revenue_snapshots_period_key"), table_name="country_revenue_snapshots")
    op.drop_index(op.f("ix_country_revenue_snapshots_currency"), table_name="country_revenue_snapshots")
    op.drop_index(op.f("ix_country_revenue_snapshots_country_code"), table_name="country_revenue_snapshots")
    op.drop_table("country_revenue_snapshots")
    op.drop_index(op.f("ix_reconciliation_snapshots_snapshot_date"), table_name="reconciliation_snapshots")
    op.drop_index(op.f("ix_reconciliation_snapshots_currency"), table_name="reconciliation_snapshots")
    op.drop_index(op.f("ix_reconciliation_snapshots_account_id"), table_name="reconciliation_snapshots")
    op.drop_table("reconciliation_snapshots")
    op.drop_index(op.f("ix_fund_transfers_to_account_id"), table_name="fund_transfers")
    op.drop_index(op.f("ix_fund_transfers_reference"), table_name="fund_transfers")
    op.drop_index(op.f("ix_fund_transfers_from_account_id"), table_name="fund_transfers")
    op.drop_index(op.f("ix_fund_transfers_currency"), table_name="fund_transfers")
    op.drop_table("fund_transfers")
    op.drop_index(op.f("ix_ledger_entries_source_table"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_source_id"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_reference"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_module_code"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_journal_id"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_entry_type"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_direction"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_currency"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_country_code"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_account_id"), table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index(op.f("ix_financial_account_scopes_scope_value"), table_name="financial_account_scopes")
    op.drop_index(op.f("ix_financial_account_scopes_scope_type"), table_name="financial_account_scopes")
    op.drop_index(op.f("ix_financial_account_scopes_module_code"), table_name="financial_account_scopes")
    op.drop_index(op.f("ix_financial_account_scopes_account_id"), table_name="financial_account_scopes")
    op.drop_table("financial_account_scopes")
    op.drop_index(op.f("ix_financial_accounts_owner_user_id"), table_name="financial_accounts")
    op.drop_index(op.f("ix_financial_accounts_module_code"), table_name="financial_accounts")
    op.drop_index(op.f("ix_financial_accounts_currency"), table_name="financial_accounts")
    op.drop_index(op.f("ix_financial_accounts_code"), table_name="financial_accounts")
    op.drop_index(op.f("ix_financial_accounts_account_type"), table_name="financial_accounts")
    op.drop_table("financial_accounts")
