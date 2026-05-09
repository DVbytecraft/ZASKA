"""tasks: add stops JSON column for multi-stop task locations

Revision ID: 20260508_0019
Revises: 20260508_0018
Create Date: 2026-05-08
"""

from alembic import op

revision = "20260508_0019"
down_revision = "20260508_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stops JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS stops")
