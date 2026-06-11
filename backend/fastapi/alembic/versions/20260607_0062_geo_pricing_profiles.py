"""geo pricing profiles

Revision ID: 20260607_0062
Revises: 20260607_0061
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_0062"
down_revision = "20260607_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("continents", sa.Column("pricing_profile_json", sa.Text(), nullable=True))
    op.add_column("countries", sa.Column("pricing_profile_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("countries", "pricing_profile_json")
    op.drop_column("continents", "pricing_profile_json")
