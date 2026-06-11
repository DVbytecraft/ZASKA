"""b2b and exports foundation

Revision ID: 20260607_0057
Revises: 20260607_0056
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0057"
down_revision = "20260607_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("registration_number", sa.String(length=64), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("continent_code", sa.String(length=8), nullable=True),
        sa.Column("billing_mode", sa.String(length=24), nullable=False, server_default="monthly_invoice"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_business_organizations_created_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_organizations_name", "business_organizations", ["name"], unique=False)
    op.create_index("ix_business_organizations_registration_number", "business_organizations", ["registration_number"], unique=False)
    op.create_index("ix_business_organizations_country_code", "business_organizations", ["country_code"], unique=False)
    op.create_index("ix_business_organizations_continent_code", "business_organizations", ["continent_code"], unique=False)
    op.create_index("ix_business_organizations_status", "business_organizations", ["status"], unique=False)

    op.create_table(
        "business_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_role", sa.String(length=32), nullable=False, server_default="manager"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["business_organizations.id"], name="fk_business_memberships_org"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_business_memberships_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_memberships_org_id", "business_memberships", ["organization_id"], unique=False)
    op.create_index("ix_business_memberships_user_id", "business_memberships", ["user_id"], unique=False)

    op.create_table(
        "business_contracts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("plan_name", sa.String(length=64), nullable=False),
        sa.Column("monthly_task_quota", sa.Integer(), nullable=True),
        sa.Column("overage_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["business_organizations.id"], name="fk_business_contracts_org"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_contracts_org_id", "business_contracts", ["organization_id"], unique=False)
    op.create_index("ix_business_contracts_status", "business_contracts", ["status"], unique=False)

    op.create_table(
        "business_task_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service_category", sa.String(length=32), nullable=False, server_default="TASK"),
        sa.Column("default_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("template_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["business_organizations.id"], name="fk_business_task_templates_org"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_task_templates_org_id", "business_task_templates", ["organization_id"], unique=False)

    op.create_table(
        "business_work_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_tasker_id", sa.String(length=36), nullable=True),
        sa.Column("linked_task_id", sa.String(length=36), nullable=True),
        sa.Column("beneficiary_name", sa.String(length=160), nullable=True),
        sa.Column("beneficiary_phone", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="b2b"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["business_organizations.id"], name="fk_business_work_orders_org"),
        sa.ForeignKeyConstraint(["template_id"], ["business_task_templates.id"], name="fk_business_work_orders_template"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name="fk_business_work_orders_requested_by"),
        sa.ForeignKeyConstraint(["assigned_tasker_id"], ["users.id"], name="fk_business_work_orders_tasker"),
        sa.ForeignKeyConstraint(["linked_task_id"], ["tasks.id"], name="fk_business_work_orders_linked_task"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_work_orders_org_id", "business_work_orders", ["organization_id"], unique=False)
    op.create_index("ix_business_work_orders_status", "business_work_orders", ["status"], unique=False)
    op.create_index("ix_business_work_orders_linked_task_id", "business_work_orders", ["linked_task_id"], unique=False)

    op.create_table(
        "admin_export_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("export_format", sa.String(length=16), nullable=False, server_default="csv"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("continent_code", sa.String(length=8), nullable=True),
        sa.Column("filters_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name="fk_admin_export_jobs_requested_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_export_jobs_report_type", "admin_export_jobs", ["report_type"], unique=False)
    op.create_index("ix_admin_export_jobs_status", "admin_export_jobs", ["status"], unique=False)
    op.create_index("ix_admin_export_jobs_country_code", "admin_export_jobs", ["country_code"], unique=False)
    op.create_index("ix_admin_export_jobs_continent_code", "admin_export_jobs", ["continent_code"], unique=False)

    op.alter_column("business_organizations", "billing_mode", server_default=None)
    op.alter_column("business_organizations", "status", server_default=None)
    op.alter_column("business_memberships", "member_role", server_default=None)
    op.alter_column("business_memberships", "status", server_default=None)
    op.alter_column("business_memberships", "is_primary", server_default=None)
    op.alter_column("business_contracts", "currency", server_default=None)
    op.alter_column("business_contracts", "status", server_default=None)
    op.alter_column("business_task_templates", "service_category", server_default=None)
    op.alter_column("business_task_templates", "currency", server_default=None)
    op.alter_column("business_task_templates", "is_active", server_default=None)
    op.alter_column("business_work_orders", "status", server_default=None)
    op.alter_column("business_work_orders", "source", server_default=None)
    op.alter_column("business_work_orders", "currency", server_default=None)
    op.alter_column("admin_export_jobs", "export_format", server_default=None)
    op.alter_column("admin_export_jobs", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_admin_export_jobs_continent_code", table_name="admin_export_jobs")
    op.drop_index("ix_admin_export_jobs_country_code", table_name="admin_export_jobs")
    op.drop_index("ix_admin_export_jobs_status", table_name="admin_export_jobs")
    op.drop_index("ix_admin_export_jobs_report_type", table_name="admin_export_jobs")
    op.drop_table("admin_export_jobs")

    op.drop_index("ix_business_work_orders_linked_task_id", table_name="business_work_orders")
    op.drop_index("ix_business_work_orders_status", table_name="business_work_orders")
    op.drop_index("ix_business_work_orders_org_id", table_name="business_work_orders")
    op.drop_table("business_work_orders")

    op.drop_index("ix_business_task_templates_org_id", table_name="business_task_templates")
    op.drop_table("business_task_templates")

    op.drop_index("ix_business_contracts_status", table_name="business_contracts")
    op.drop_index("ix_business_contracts_org_id", table_name="business_contracts")
    op.drop_table("business_contracts")

    op.drop_index("ix_business_memberships_user_id", table_name="business_memberships")
    op.drop_index("ix_business_memberships_org_id", table_name="business_memberships")
    op.drop_table("business_memberships")

    op.drop_index("ix_business_organizations_status", table_name="business_organizations")
    op.drop_index("ix_business_organizations_continent_code", table_name="business_organizations")
    op.drop_index("ix_business_organizations_country_code", table_name="business_organizations")
    op.drop_index("ix_business_organizations_registration_number", table_name="business_organizations")
    op.drop_index("ix_business_organizations_name", table_name="business_organizations")
    op.drop_table("business_organizations")
