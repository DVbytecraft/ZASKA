"""create notifications table

Revision ID: 20260508_0020
Revises: 20260508_0019
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260508_0020"
down_revision = "20260508_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("type", sa.String(16), nullable=False, server_default="info"),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("body", sa.String(512), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notifications")
