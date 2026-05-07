"""fix task.price from FLOAT to NUMERIC(20,6)

Revision ID: 20260503_0004
Revises: 20260503_0003
Create Date: 2026-05-03

IEEE 754 float is unsuitable for monetary amounts.
This migration converts tasks.price to NUMERIC(20,6) to match
the precision used by wallets, transactions, and escrows.
"""

from alembic import op

revision = "20260503_0004"
down_revision = "20260503_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tasks ALTER COLUMN price TYPE NUMERIC(20, 6) USING price::NUMERIC(20, 6)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tasks ALTER COLUMN price TYPE DOUBLE PRECISION USING price::DOUBLE PRECISION"
    )
