"""task: scheduled_at, any_schedule, original_price

Revision ID: 20260508_0023
Revises: 20260508_0022
Create Date: 2026-05-08
"""

from alembic import op

revision = "20260508_0023"
down_revision = "20260508_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS any_schedule BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS original_price NUMERIC(20, 6)")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS scheduled_at")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS any_schedule")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS original_price")
