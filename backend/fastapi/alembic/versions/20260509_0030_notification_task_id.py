"""notification_task_id

Revision ID: 20260509_0030
Revises: 20260508_0029
Create Date: 2026-05-09
"""
from alembic import op

revision = "20260509_0030"
down_revision = "20260508_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS task_id VARCHAR(36) "
        "REFERENCES tasks(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_task_id ON notifications (task_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notifications_task_id")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS task_id")
