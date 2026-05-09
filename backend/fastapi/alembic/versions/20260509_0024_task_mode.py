"""tasks: add mode column (fast|choose)

Revision ID: 20260509_0024
Revises: 20260508_0023
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "20260509_0024"
down_revision = "20260508_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("mode", sa.String(8), nullable=False, server_default="fast"),
    )


def downgrade() -> None:
    op.drop_column("tasks", "mode")
