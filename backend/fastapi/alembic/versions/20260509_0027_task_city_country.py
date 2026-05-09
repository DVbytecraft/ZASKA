"""tasks: add city and country columns for structured location display

Revision ID: 20260509_0027
Revises: 20260509_0026
Create Date: 2026-05-09
"""
from alembic import op

revision = "20260509_0027"
down_revision = "20260509_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS city VARCHAR(128)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS country VARCHAR(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS city")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS country")
