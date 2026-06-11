"""referral foundation

Revision ID: 20260606_0053
Revises: 20260606_0052
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0053"
down_revision = "20260606_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("referred_by_user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_users_referral_code"), "users", ["referral_code"], unique=True)
    op.create_index(op.f("ix_users_referred_by_user_id"), "users", ["referred_by_user_id"], unique=False)

    op.create_table(
        "referral_programs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("referral_type", sa.String(length=16), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("reward_kind", sa.String(length=24), nullable=False),
        sa.Column("reward_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("reward_currency", sa.String(length=8), nullable=False),
        sa.Column("qualification_threshold", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_referral_programs_code"), "referral_programs", ["code"], unique=True)
    op.create_index(op.f("ix_referral_programs_referral_type"), "referral_programs", ["referral_type"], unique=False)
    op.create_index(op.f("ix_referral_programs_country_code"), "referral_programs", ["country_code"], unique=False)

    op.create_table(
        "referral_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("referral_type", sa.String(length=16), nullable=False),
        sa.Column("referral_code", sa.String(length=32), nullable=False),
        sa.Column("referrer_user_id", sa.String(length=36), nullable=False),
        sa.Column("referred_user_id", sa.String(length=36), nullable=False),
        sa.Column("program_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("qualification_threshold", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("progress_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trigger_task_id", sa.String(length=36), nullable=True),
        sa.Column("reward_kind", sa.String(length=24), nullable=False),
        sa.Column("reward_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("reward_currency", sa.String(length=8), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["referral_programs.id"]),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["trigger_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_referral_events_referral_type"), "referral_events", ["referral_type"], unique=False)
    op.create_index(op.f("ix_referral_events_referral_code"), "referral_events", ["referral_code"], unique=False)
    op.create_index(op.f("ix_referral_events_referrer_user_id"), "referral_events", ["referrer_user_id"], unique=False)
    op.create_index(op.f("ix_referral_events_referred_user_id"), "referral_events", ["referred_user_id"], unique=False)
    op.create_index(op.f("ix_referral_events_program_id"), "referral_events", ["program_id"], unique=False)
    op.create_index(op.f("ix_referral_events_status"), "referral_events", ["status"], unique=False)
    op.create_index(op.f("ix_referral_events_trigger_task_id"), "referral_events", ["trigger_task_id"], unique=False)
    op.create_index(op.f("ix_referral_events_country_code"), "referral_events", ["country_code"], unique=False)

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("referral_event_id", sa.String(length=36), nullable=False),
        sa.Column("beneficiary_user_id", sa.String(length=36), nullable=False),
        sa.Column("reward_kind", sa.String(length=24), nullable=False),
        sa.Column("amount_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("amount_remaining", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="AVAILABLE"),
        sa.Column("wallet_transaction_id", sa.String(length=36), nullable=True),
        sa.Column("applied_task_id", sa.String(length=36), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["applied_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["beneficiary_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["referral_event_id"], ["referral_events.id"]),
        sa.ForeignKeyConstraint(["wallet_transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_referral_rewards_referral_event_id"), "referral_rewards", ["referral_event_id"], unique=False)
    op.create_index(op.f("ix_referral_rewards_beneficiary_user_id"), "referral_rewards", ["beneficiary_user_id"], unique=False)
    op.create_index(op.f("ix_referral_rewards_status"), "referral_rewards", ["status"], unique=False)
    op.create_index(op.f("ix_referral_rewards_wallet_transaction_id"), "referral_rewards", ["wallet_transaction_id"], unique=False)
    op.create_index(op.f("ix_referral_rewards_applied_task_id"), "referral_rewards", ["applied_task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_referral_rewards_applied_task_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_wallet_transaction_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_status"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_beneficiary_user_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_referral_event_id"), table_name="referral_rewards")
    op.drop_table("referral_rewards")
    op.drop_index(op.f("ix_referral_events_country_code"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_trigger_task_id"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_status"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_program_id"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_referred_user_id"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_referrer_user_id"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_referral_code"), table_name="referral_events")
    op.drop_index(op.f("ix_referral_events_referral_type"), table_name="referral_events")
    op.drop_table("referral_events")
    op.drop_index(op.f("ix_referral_programs_country_code"), table_name="referral_programs")
    op.drop_index(op.f("ix_referral_programs_referral_type"), table_name="referral_programs")
    op.drop_index(op.f("ix_referral_programs_code"), table_name="referral_programs")
    op.drop_table("referral_programs")
    op.drop_index(op.f("ix_users_referred_by_user_id"), table_name="users")
    op.drop_index(op.f("ix_users_referral_code"), table_name="users")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
