"""call_sessions: table for audio/video call tracking

Revision ID: 20260510_0032
Revises: 20260509_0031
Create Date: 2026-05-10
"""

revision = "20260510_0032"
down_revision = "20260509_0031"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("caller_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("callee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("media_type", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_call_sessions_task_id", "call_sessions", ["task_id"])
    op.create_index("ix_call_sessions_caller_id", "call_sessions", ["caller_id"])
    op.create_index("ix_call_sessions_callee_id", "call_sessions", ["callee_id"])
    op.create_index("ix_call_sessions_status", "call_sessions", ["status"])


def downgrade() -> None:
    op.drop_table("call_sessions")
