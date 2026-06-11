"""aml foundation

Revision ID: 20260607_0055
Revises: 20260606_0054
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0055"
down_revision = "20260606_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("aml_status", sa.String(length=24), nullable=False, server_default="clear"))
    op.add_column("users", sa.Column("aml_review_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("aml_review_reason", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("aml_last_case_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("tasks", sa.Column("aml_status", sa.String(length=24), nullable=False, server_default="clear"))
    op.add_column("tasks", sa.Column("aml_case_id", sa.String(length=36), nullable=True))
    op.add_column("tasks", sa.Column("aml_hold_reason", sa.String(length=512), nullable=True))
    op.add_column("tasks", sa.Column("aml_flagged_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_tasks_aml_case_id", "tasks", ["aml_case_id"], unique=False)
    op.create_index("ix_users_aml_status", "users", ["aml_status"], unique=False)

    op.create_table(
        "aml_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("counterparty_user_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("escrow_id", sa.String(length=36), nullable=True),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("amount_eur", sa.Numeric(20, 6), nullable=True),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("authority_name", sa.String(length=128), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("assigned_admin_user_id", sa.String(length=36), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_admin_user_id"], ["users.id"], name="fk_aml_cases_assigned_admin"),
        sa.ForeignKeyConstraint(["counterparty_user_id"], ["users.id"], name="fk_aml_cases_counterparty"),
        sa.ForeignKeyConstraint(["escrow_id"], ["escrows.id"], name="fk_aml_cases_escrow"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_aml_cases_task"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_aml_cases_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aml_cases_status", "aml_cases", ["status"], unique=False)
    op.create_index("ix_aml_cases_case_type", "aml_cases", ["case_type"], unique=False)
    op.create_index("ix_aml_cases_country_code", "aml_cases", ["country_code"], unique=False)
    op.create_index("ix_aml_cases_user_id", "aml_cases", ["user_id"], unique=False)
    op.create_index("ix_aml_cases_task_id", "aml_cases", ["task_id"], unique=False)

    op.create_table(
        "aml_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("aml_case_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_aml_events_actor"),
        sa.ForeignKeyConstraint(["aml_case_id"], ["aml_cases.id"], name="fk_aml_events_case"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aml_events_case_id", "aml_events", ["aml_case_id"], unique=False)
    op.create_index("ix_aml_events_event_type", "aml_events", ["event_type"], unique=False)

    op.alter_column("users", "aml_status", server_default=None)
    op.alter_column("users", "aml_review_required", server_default=None)
    op.alter_column("tasks", "aml_status", server_default=None)
    op.alter_column("aml_cases", "severity", server_default=None)
    op.alter_column("aml_cases", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_aml_events_event_type", table_name="aml_events")
    op.drop_index("ix_aml_events_case_id", table_name="aml_events")
    op.drop_table("aml_events")

    op.drop_index("ix_aml_cases_task_id", table_name="aml_cases")
    op.drop_index("ix_aml_cases_user_id", table_name="aml_cases")
    op.drop_index("ix_aml_cases_country_code", table_name="aml_cases")
    op.drop_index("ix_aml_cases_case_type", table_name="aml_cases")
    op.drop_index("ix_aml_cases_status", table_name="aml_cases")
    op.drop_table("aml_cases")

    op.drop_index("ix_users_aml_status", table_name="users")
    op.drop_index("ix_tasks_aml_case_id", table_name="tasks")
    op.drop_column("tasks", "aml_flagged_at")
    op.drop_column("tasks", "aml_hold_reason")
    op.drop_column("tasks", "aml_case_id")
    op.drop_column("tasks", "aml_status")
    op.drop_column("users", "aml_last_case_at")
    op.drop_column("users", "aml_review_reason")
    op.drop_column("users", "aml_review_required")
    op.drop_column("users", "aml_status")
