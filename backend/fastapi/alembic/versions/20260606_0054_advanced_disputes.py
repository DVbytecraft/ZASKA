"""advanced disputes

Revision ID: 20260606_0054
Revises: 20260606_0053
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0054"
down_revision = "20260606_0053"
branch_labels = None
depends_on = None


DISPUTES_FK_TASK = "fk_disputes_task_id_tasks"
DISPUTES_FK_ESCROW = "fk_disputes_escrow_id_escrows"
DISPUTES_FK_COUNTERPARTY = "fk_disputes_counterparty_user_id_users"
DISPUTES_FK_ASSIGNED_AGENT = "fk_disputes_assigned_agent_id_users"
DISPUTES_FK_ESCALATED_TO = "fk_disputes_escalated_to_user_id_users"
DISPUTE_EVENTS_FK_DISPUTE = "fk_dispute_events_dispute_id_disputes"
DISPUTE_EVENTS_FK_ACTOR = "fk_dispute_events_actor_user_id_users"


def upgrade() -> None:
    op.add_column("disputes", sa.Column("task_id", sa.String(length=36), nullable=True))
    op.add_column("disputes", sa.Column("escrow_id", sa.String(length=36), nullable=True))
    op.add_column("disputes", sa.Column("counterparty_user_id", sa.String(length=36), nullable=True))
    op.add_column("disputes", sa.Column("opened_by_role", sa.String(length=20), nullable=True))
    op.add_column("disputes", sa.Column("assigned_agent_id", sa.String(length=36), nullable=True))
    op.add_column("disputes", sa.Column("escalated_to_user_id", sa.String(length=36), nullable=True))
    op.add_column("disputes", sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"))
    op.add_column("disputes", sa.Column("amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("disputes", sa.Column("currency", sa.String(length=8), nullable=True))
    op.add_column("disputes", sa.Column("resolution_type", sa.String(length=32), nullable=True))
    op.add_column("disputes", sa.Column("source_channel", sa.String(length=32), nullable=False, server_default="task"))
    op.add_column("disputes", sa.Column("task_snapshot_json", sa.Text(), nullable=True))
    op.add_column("disputes", sa.Column("chat_snapshot_json", sa.Text(), nullable=True))
    op.add_column("disputes", sa.Column("geo_snapshot_json", sa.Text(), nullable=True))
    op.add_column("disputes", sa.Column("photos_snapshot_json", sa.Text(), nullable=True))
    op.add_column("disputes", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("disputes", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("disputes", sa.Column("latest_action_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(DISPUTES_FK_TASK, "disputes", "tasks", ["task_id"], ["id"])
    op.create_foreign_key(DISPUTES_FK_ESCROW, "disputes", "escrows", ["escrow_id"], ["id"])
    op.create_foreign_key(
        DISPUTES_FK_COUNTERPARTY,
        "disputes",
        "users",
        ["counterparty_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        DISPUTES_FK_ASSIGNED_AGENT,
        "disputes",
        "users",
        ["assigned_agent_id"],
        ["id"],
    )
    op.create_foreign_key(
        DISPUTES_FK_ESCALATED_TO,
        "disputes",
        "users",
        ["escalated_to_user_id"],
        ["id"],
    )

    op.create_index("ix_disputes_task_id", "disputes", ["task_id"], unique=False)
    op.create_index("ix_disputes_escrow_id", "disputes", ["escrow_id"], unique=False)
    op.create_index("ix_disputes_priority", "disputes", ["priority"], unique=False)
    op.create_index("ix_disputes_due_at", "disputes", ["due_at"], unique=False)
    op.create_index("ix_disputes_latest_action_at", "disputes", ["latest_action_at"], unique=False)

    op.create_table(
        "dispute_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dispute_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=DISPUTE_EVENTS_FK_ACTOR),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], name=DISPUTE_EVENTS_FK_DISPUTE),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dispute_events_dispute_id", "dispute_events", ["dispute_id"], unique=False)
    op.create_index("ix_dispute_events_event_type", "dispute_events", ["event_type"], unique=False)

    op.alter_column("disputes", "priority", server_default=None)
    op.alter_column("disputes", "source_channel", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_dispute_events_event_type", table_name="dispute_events")
    op.drop_index("ix_dispute_events_dispute_id", table_name="dispute_events")
    op.drop_table("dispute_events")

    op.drop_index("ix_disputes_latest_action_at", table_name="disputes")
    op.drop_index("ix_disputes_due_at", table_name="disputes")
    op.drop_index("ix_disputes_priority", table_name="disputes")
    op.drop_index("ix_disputes_escrow_id", table_name="disputes")
    op.drop_index("ix_disputes_task_id", table_name="disputes")

    op.drop_constraint(DISPUTES_FK_ESCALATED_TO, "disputes", type_="foreignkey")
    op.drop_constraint(DISPUTES_FK_ASSIGNED_AGENT, "disputes", type_="foreignkey")
    op.drop_constraint(DISPUTES_FK_COUNTERPARTY, "disputes", type_="foreignkey")
    op.drop_constraint(DISPUTES_FK_ESCROW, "disputes", type_="foreignkey")
    op.drop_constraint(DISPUTES_FK_TASK, "disputes", type_="foreignkey")

    op.drop_column("disputes", "latest_action_at")
    op.drop_column("disputes", "resolved_at")
    op.drop_column("disputes", "due_at")
    op.drop_column("disputes", "photos_snapshot_json")
    op.drop_column("disputes", "geo_snapshot_json")
    op.drop_column("disputes", "chat_snapshot_json")
    op.drop_column("disputes", "task_snapshot_json")
    op.drop_column("disputes", "source_channel")
    op.drop_column("disputes", "resolution_type")
    op.drop_column("disputes", "currency")
    op.drop_column("disputes", "amount")
    op.drop_column("disputes", "priority")
    op.drop_column("disputes", "escalated_to_user_id")
    op.drop_column("disputes", "assigned_agent_id")
    op.drop_column("disputes", "opened_by_role")
    op.drop_column("disputes", "counterparty_user_id")
    op.drop_column("disputes", "escrow_id")
    op.drop_column("disputes", "task_id")
