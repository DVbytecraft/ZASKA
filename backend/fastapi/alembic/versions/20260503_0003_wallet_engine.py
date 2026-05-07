"""wallet engine — wallets, transactions, escrows, user.country_code

Revision ID: 20260503_0003
Revises: 20260502_0002
Create Date: 2026-05-03

Crée :
  - wallets             : soldes par utilisateur/devise
  - transactions        : grand-livre ACID
  - escrows             : réserves de fonds liées aux tâches
  - users.country_code  : pays détecté au premier login/register
"""

from alembic import op
import sqlalchemy as sa

revision = "20260503_0003"
down_revision = "20260502_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.country_code ────────────────────────────────────────────────
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS country_code VARCHAR(2)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_country_code ON users(country_code)"
    )

    # ── wallets ───────────────────────────────────────────────────────────
    op.create_table(
        "wallets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("balance", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "currency", name="uq_wallet_user_currency"),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"])

    # ── transactions ──────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wallet_id", sa.String(36), sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("reference", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="internal"),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_transactions_wallet_id", "transactions", ["wallet_id"])
    op.create_index("ix_transactions_reference", "transactions", ["reference"])
    op.create_index("ix_tx_wallet_created", "transactions", ["wallet_id", "created_at"])

    # ── escrows ───────────────────────────────────────────────────────────
    op.create_table(
        "escrows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("payer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("funding_tx_id", sa.String(36), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("settlement_tx_id", sa.String(36), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_escrow_task", "escrows", ["task_id"])
    op.create_index("ix_escrows_payer_id", "escrows", ["payer_id"])
    op.create_index("ix_escrows_payee_id", "escrows", ["payee_id"])


def downgrade() -> None:
    op.drop_table("escrows")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS country_code")
