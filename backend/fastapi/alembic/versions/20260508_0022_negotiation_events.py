"""negotiation_events table

Revision ID: 20260508_0022
Revises: 20260508_0021
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0022"
down_revision = "20260508_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "negotiation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_negotiation_events_task_id", "negotiation_events", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_negotiation_events_task_id", "negotiation_events")
    op.drop_table("negotiation_events")
