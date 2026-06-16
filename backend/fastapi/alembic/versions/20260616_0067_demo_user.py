"""users: add is_demo flag for ephemeral demo sessions

Revision ID: 20260616_0067
Revises: 20260614_0066
Create Date: 2026-06-16
"""

from alembic import op


revision = "20260616_0067"
down_revision = "20260614_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_is_demo ON users (is_demo)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_is_demo")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_demo")
