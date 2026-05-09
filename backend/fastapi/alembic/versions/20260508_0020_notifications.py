"""create notifications table

Revision ID: 20260508_0020
Revises: 20260508_0019
Create Date: 2026-05-08
"""

from alembic import op

revision = "20260508_0020"
down_revision = "20260508_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id),
            type VARCHAR(16) NOT NULL DEFAULT 'info',
            title VARCHAR(128) NOT NULL,
            body VARCHAR(512) NOT NULL,
            read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_id")
    op.execute("DROP TABLE IF EXISTS notifications")
