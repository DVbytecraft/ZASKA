"""tasks: add service_category, is_urgent, escrow_auto_release_minutes columns

These columns exist on the Task ORM model (app/models/task.py) but were
never given a migration, causing UndefinedColumn errors on any query
selecting the tasks table.

Revision ID: 20260614_0066
Revises: 20260613_0065
Create Date: 2026-06-14
"""

from alembic import op


revision = "20260614_0066"
down_revision = "20260613_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS service_category VARCHAR(32) NOT NULL DEFAULT 'TASK'")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_urgent BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS escrow_auto_release_minutes INTEGER NOT NULL DEFAULT 180")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS escrow_auto_release_minutes")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS is_urgent")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS service_category")
