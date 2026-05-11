"""Add index on escrows.task_id for get_escrow_by_task performance.

Revision ID: 20260511_0038
Revises: 20260510_0037
Create Date: 2026-05-11

Without this index, get_escrow_by_task (and the FOR UPDATE variant) does a
sequential scan on the escrows table on every task lifecycle call (complete,
confirm, cancel, abandon).  At scale with millions of escrows this becomes a
full-table lock-scan which blocks concurrent transactions.
"""

revision = "20260511_0038"
down_revision = "20260510_0037"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # Non-concurrent index creation (alembic runs in a transaction).
    # On a live large table, use CREATE INDEX CONCURRENTLY in a manual migration.
    op.create_index(
        "idx_escrows_task_id",
        "escrows",
        ["task_id"],
        unique=False,
        if_not_exists=True,
    )
    # Partial index for active escrows — the hot path queries only funded/hold/pending
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_escrows_task_id_active
        ON escrows (task_id)
        WHERE status IN ('funded', 'hold', 'pending')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_escrows_task_id_active")
    op.drop_index("idx_escrows_task_id", table_name="escrows")
