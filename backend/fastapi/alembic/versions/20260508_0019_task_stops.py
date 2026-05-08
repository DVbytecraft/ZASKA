"""tasks: add stops JSON column for multi-stop task locations

Revision ID: 20260508_0019
Revises: 20260508_0018
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260508_0019"
down_revision = "20260508_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("stops", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "stops")
