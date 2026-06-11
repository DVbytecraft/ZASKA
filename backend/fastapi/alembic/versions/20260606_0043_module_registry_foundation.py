"""module registry foundation

Revision ID: 20260606_0043
Revises: 20260606_0042
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0043"
down_revision = "20260606_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_modules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module_group", sa.String(length=64), nullable=False, server_default="core"),
        sa.Column("default_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("requires_country_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_platform_modules_code"), "platform_modules", ["code"], unique=False)

    op.create_table(
        "module_activation_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("module_id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_value", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["module_id"], ["platform_modules.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module_id", "scope_type", "scope_value", name="uq_module_scope"),
    )
    op.create_index(op.f("ix_module_activation_settings_module_id"), "module_activation_settings", ["module_id"], unique=False)
    op.create_index(op.f("ix_module_activation_settings_scope_type"), "module_activation_settings", ["scope_type"], unique=False)
    op.create_index(op.f("ix_module_activation_settings_scope_value"), "module_activation_settings", ["scope_value"], unique=False)

    op.create_table(
        "module_activation_audit",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_value", sa.String(length=64), nullable=False),
        sa.Column("previous_enabled", sa.Boolean(), nullable=True),
        sa.Column("new_enabled", sa.Boolean(), nullable=False),
        sa.Column("previous_config_json", sa.Text(), nullable=True),
        sa.Column("new_config_json", sa.Text(), nullable=True),
        sa.Column("changed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_module_activation_audit_module_code"), "module_activation_audit", ["module_code"], unique=False)
    op.create_index(op.f("ix_module_activation_audit_scope_type"), "module_activation_audit", ["scope_type"], unique=False)
    op.create_index(op.f("ix_module_activation_audit_scope_value"), "module_activation_audit", ["scope_value"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_module_activation_audit_scope_value"), table_name="module_activation_audit")
    op.drop_index(op.f("ix_module_activation_audit_scope_type"), table_name="module_activation_audit")
    op.drop_index(op.f("ix_module_activation_audit_module_code"), table_name="module_activation_audit")
    op.drop_table("module_activation_audit")
    op.drop_index(op.f("ix_module_activation_settings_scope_value"), table_name="module_activation_settings")
    op.drop_index(op.f("ix_module_activation_settings_scope_type"), table_name="module_activation_settings")
    op.drop_index(op.f("ix_module_activation_settings_module_id"), table_name="module_activation_settings")
    op.drop_table("module_activation_settings")
    op.drop_index(op.f("ix_platform_modules_code"), table_name="platform_modules")
    op.drop_table("platform_modules")
