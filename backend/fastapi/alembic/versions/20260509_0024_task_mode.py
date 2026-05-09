"""tasks: add mode column (fast|choose)

Revision ID: 20260509_0024
Revises: 20260508_0023
Create Date: 2026-05-09
"""

from alembic import op

revision = "20260509_0024"
down_revision = "20260508_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS mode VARCHAR(8) NOT NULL DEFAULT 'fast'")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS mode")
