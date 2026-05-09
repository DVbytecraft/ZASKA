"""users: rating_sum/rating_count — tasks: creator_rated

Revision ID: 20260509_0029
Revises: 20260509_0028
Create Date: 2026-05-09
"""
from alembic import op

revision = "20260509_0029"
down_revision = "20260509_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS rating_sum FLOAT NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS rating_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS creator_rated BOOLEAN NOT NULL DEFAULT FALSE")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS rating_sum")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS rating_count")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS creator_rated")
