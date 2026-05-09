"""task: scheduled_at, any_schedule, original_price

Revision ID: 20260508_0023
Revises: 20260508_0022
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0023"
down_revision = "20260508_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("any_schedule", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tasks", sa.Column("original_price", sa.Numeric(20, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "scheduled_at")
    op.drop_column("tasks", "any_schedule")
    op.drop_column("tasks", "original_price")
