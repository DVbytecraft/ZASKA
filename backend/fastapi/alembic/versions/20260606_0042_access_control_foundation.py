"""access control foundation

Revision ID: 20260606_0042
Revises: 20260606_0041
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0042"
down_revision = "20260606_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_staff_role", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_access_roles_code"), "access_roles", ["code"], unique=False)

    op.create_table(
        "access_permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module_key", sa.String(length=64), nullable=False, server_default="core"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_access_permissions_code"), "access_permissions", ["code"], unique=False)

    op.create_table(
        "access_role_permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("permission_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["access_permissions.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["access_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_access_role_permission"),
    )
    op.create_index(op.f("ix_access_role_permissions_permission_id"), "access_role_permissions", ["permission_id"], unique=False)
    op.create_index(op.f("ix_access_role_permissions_role_id"), "access_role_permissions", ["role_id"], unique=False)

    op.create_table(
        "access_user_role_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["access_roles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_access_user_role"),
    )
    op.create_index(op.f("ix_access_user_role_assignments_role_id"), "access_user_role_assignments", ["role_id"], unique=False)
    op.create_index(op.f("ix_access_user_role_assignments_user_id"), "access_user_role_assignments", ["user_id"], unique=False)

    op.create_table(
        "access_admin_scopes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_value", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("module_key", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("can_read", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "scope_type",
            "scope_value",
            "module_key",
            name="uq_access_admin_scope",
        ),
    )
    op.create_index(op.f("ix_access_admin_scopes_scope_type"), "access_admin_scopes", ["scope_type"], unique=False)
    op.create_index(op.f("ix_access_admin_scopes_user_id"), "access_admin_scopes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_access_admin_scopes_user_id"), table_name="access_admin_scopes")
    op.drop_index(op.f("ix_access_admin_scopes_scope_type"), table_name="access_admin_scopes")
    op.drop_table("access_admin_scopes")
    op.drop_index(op.f("ix_access_user_role_assignments_user_id"), table_name="access_user_role_assignments")
    op.drop_index(op.f("ix_access_user_role_assignments_role_id"), table_name="access_user_role_assignments")
    op.drop_table("access_user_role_assignments")
    op.drop_index(op.f("ix_access_role_permissions_role_id"), table_name="access_role_permissions")
    op.drop_index(op.f("ix_access_role_permissions_permission_id"), table_name="access_role_permissions")
    op.drop_table("access_role_permissions")
    op.drop_index(op.f("ix_access_permissions_code"), table_name="access_permissions")
    op.drop_table("access_permissions")
    op.drop_index(op.f("ix_access_roles_code"), table_name="access_roles")
    op.drop_table("access_roles")
