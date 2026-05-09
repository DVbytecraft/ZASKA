"""negotiation_events table

Revision ID: 20260508_0022
Revises: 20260508_0021
Create Date: 2026-05-08
"""

from alembic import op

revision = "20260508_0022"
down_revision = "20260508_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS negotiation_events (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            task_id VARCHAR(36) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            actor_id VARCHAR(36) NOT NULL REFERENCES users(id),
            event_type VARCHAR(16) NOT NULL,
            price NUMERIC(20, 6),
            currency VARCHAR(8) NOT NULL DEFAULT 'USD',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_events_task_id ON negotiation_events(task_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_negotiation_events_task_id")
    op.execute("DROP TABLE IF EXISTS negotiation_events")
