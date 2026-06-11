"""subscriptions foundation

Revision ID: 20260606_0052
Revises: 20260606_0051
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0052"
down_revision = "20260606_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("subscription_type", sa.String(length=24), nullable=False, server_default="GENERAL"),
        sa.Column("service_category", sa.String(length=64), nullable=True),
        sa.Column("billing_cycle", sa.String(length=16), nullable=False, server_default="MONTHLY"),
        sa.Column("price_monthly", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("tasks_included_monthly", sa.Integer(), nullable=True),
        sa.Column("overage_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("priority_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("diaspora_included", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("support_priority", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscription_plans_code"), "subscription_plans", ["code"], unique=True)
    op.create_index(op.f("ix_subscription_plans_service_category"), "subscription_plans", ["service_category"], unique=False)

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column("subscription_type", sa.String(length=24), nullable=False),
        sa.Column("service_category", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("price_monthly", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("tasks_included_monthly", sa.Integer(), nullable=True),
        sa.Column("tasks_used_this_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("renewal_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="self_service"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_subscriptions_user_id"), "user_subscriptions", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_plan_id"), "user_subscriptions", ["plan_id"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_plan_code"), "user_subscriptions", ["plan_code"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_service_category"), "user_subscriptions", ["service_category"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_status"), "user_subscriptions", ["status"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_country_code"), "user_subscriptions", ["country_code"], unique=False)

    op.create_table(
        "subscription_usages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column("service_category", sa.String(length=64), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("benefit_type", sa.String(length=24), nullable=False, server_default="SERVICE_QUOTA"),
        sa.Column("units_used", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount_saved", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("period_key", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["user_subscriptions.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscription_usages_subscription_id"), "subscription_usages", ["subscription_id"], unique=False)
    op.create_index(op.f("ix_subscription_usages_user_id"), "subscription_usages", ["user_id"], unique=False)
    op.create_index(op.f("ix_subscription_usages_plan_code"), "subscription_usages", ["plan_code"], unique=False)
    op.create_index(op.f("ix_subscription_usages_service_category"), "subscription_usages", ["service_category"], unique=False)
    op.create_index(op.f("ix_subscription_usages_task_id"), "subscription_usages", ["task_id"], unique=False)
    op.create_index(op.f("ix_subscription_usages_period_key"), "subscription_usages", ["period_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_subscription_usages_period_key"), table_name="subscription_usages")
    op.drop_index(op.f("ix_subscription_usages_task_id"), table_name="subscription_usages")
    op.drop_index(op.f("ix_subscription_usages_service_category"), table_name="subscription_usages")
    op.drop_index(op.f("ix_subscription_usages_plan_code"), table_name="subscription_usages")
    op.drop_index(op.f("ix_subscription_usages_user_id"), table_name="subscription_usages")
    op.drop_index(op.f("ix_subscription_usages_subscription_id"), table_name="subscription_usages")
    op.drop_table("subscription_usages")
    op.drop_index(op.f("ix_user_subscriptions_country_code"), table_name="user_subscriptions")
    op.drop_index(op.f("ix_user_subscriptions_status"), table_name="user_subscriptions")
    op.drop_index(op.f("ix_user_subscriptions_service_category"), table_name="user_subscriptions")
    op.drop_index(op.f("ix_user_subscriptions_plan_code"), table_name="user_subscriptions")
    op.drop_index(op.f("ix_user_subscriptions_plan_id"), table_name="user_subscriptions")
    op.drop_index(op.f("ix_user_subscriptions_user_id"), table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
    op.drop_index(op.f("ix_subscription_plans_service_category"), table_name="subscription_plans")
    op.drop_index(op.f("ix_subscription_plans_code"), table_name="subscription_plans")
    op.drop_table("subscription_plans")
