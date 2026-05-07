"""initial schema

Revision ID: 20260502_0001
Revises:
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260502_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_users_phone", "users", ["phone"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("budget", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("primary_location", sa.String(length=255), nullable=False),
        sa.Column("additional_zones", sa.Text(), nullable=False, server_default=""),
        sa.Column("payment_method", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("accepted_by", sa.String(length=64), nullable=True),
        sa.Column("negotiated_budget", sa.Float(), nullable=True),
    )
    op.create_index("ix_tasks_primary_location", "tasks", ["primary_location"])

    op.create_table(
        "payment_methods",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("method_type", sa.String(length=64), nullable=False),
        sa.Column("details", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_payment_methods_user_id", "payment_methods", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_methods_user_id", table_name="payment_methods")
    op.drop_table("payment_methods")
    op.drop_index("ix_tasks_primary_location", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")
