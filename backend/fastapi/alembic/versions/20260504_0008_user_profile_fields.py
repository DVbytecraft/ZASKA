"""users — add full_name and avatar_url for profile setup

Revision ID: 20260504_0008
Revises: 20260503_0007
Create Date: 2026-05-04
"""

from alembic import op

revision = "20260504_0008"
down_revision = "20260503_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(128)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_url")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS full_name")
