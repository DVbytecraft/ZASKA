"""task: composite index (status, created_by) + negotiation_status index

Revision ID: 20260509_0026
Revises: 20260509_0025
Create Date: 2026-05-09
"""
from alembic import op

revision = "20260509_0026"
down_revision = "20260509_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_task_status_created_by
        ON tasks (status, created_by)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_task_negotiation_status
        ON tasks (negotiation_status)
        WHERE negotiation_status != 'none'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_task_status_created_by")
    op.execute("DROP INDEX IF EXISTS ix_task_negotiation_status")
