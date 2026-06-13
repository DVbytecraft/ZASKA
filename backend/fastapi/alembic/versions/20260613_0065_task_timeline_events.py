"""task timeline events

Revision ID: 20260613_0065
Revises: 20260613_0064
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260613_0065"
down_revision = "20260613_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_timeline_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_timeline_events_task_created", "task_timeline_events", ["task_id", "created_at"], unique=False)
    op.create_index("ix_task_timeline_events_event_type", "task_timeline_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_task_timeline_events_task_id"), "task_timeline_events", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_timeline_events_actor_user_id"), "task_timeline_events", ["actor_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_timeline_events_actor_user_id"), table_name="task_timeline_events")
    op.drop_index(op.f("ix_task_timeline_events_task_id"), table_name="task_timeline_events")
    op.drop_index("ix_task_timeline_events_event_type", table_name="task_timeline_events")
    op.drop_index("ix_task_timeline_events_task_created", table_name="task_timeline_events")
    op.drop_table("task_timeline_events")
