"""wallet transactions: UNIQUE(wallet_id, reference) + CHECK balance constraints

FIN-04: Prevents double-credit / double-debit for the same reference on the same wallet.
        A unique constraint at DB level is the last line of defence after application-level
        idempotency checks.
FIN-balance: Adds CHECK(balance >= 0) on wallets to prevent negative balances at DB level.

Revision ID: 0035
Revises: 0034
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0035"
down_revision = "20260510_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate (wallet_id, reference) pairs that may already exist before
    # adding the constraint — keep only the oldest record per pair.
    op.execute(
        """
        DELETE FROM transactions t1
        USING transactions t2
        WHERE t1.wallet_id = t2.wallet_id
          AND t1.reference = t2.reference
          AND t1.created_at > t2.created_at
        """
    )

    # UNIQUE constraint on (wallet_id, reference) — prevents double processing
    # of the same payment reference for the same wallet.
    op.create_unique_constraint(
        "uq_transactions_wallet_reference",
        "transactions",
        ["wallet_id", "reference"],
    )

    # Index to make the uniqueness check fast (also helps WHERE wallet_id = ? AND reference = ?)
    op.create_index(
        "ix_transactions_wallet_reference",
        "transactions",
        ["wallet_id", "reference"],
        unique=True,
    )

    # CHECK(balance >= 0) on wallets — DB-level safety net against negative balances.
    # Application code already prevents this, but the constraint is the authoritative guard.
    op.execute(
        "ALTER TABLE wallets ADD CONSTRAINT ck_wallets_balance_non_negative CHECK (balance >= 0)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE wallets DROP CONSTRAINT IF EXISTS ck_wallets_balance_non_negative"
    )
    op.drop_index("ix_transactions_wallet_reference", table_name="transactions")
    op.drop_constraint(
        "uq_transactions_wallet_reference", "transactions", type_="unique"
    )
