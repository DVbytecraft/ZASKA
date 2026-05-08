"""admin: user flags (is_suspended, is_locked, ban_reason) + support_tickets table

Revision ID: 20260508_0017
Revises: 20260508_0016
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260508_0017"
down_revision = "20260508_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Users: add suspension/lock/ban fields ──────────────────────────────────
    op.add_column("users", sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("ban_reason", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("suspension_reason", sa.String(512), nullable=True))

    # ── Support tickets table ──────────────────────────────────────────────────
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("category", sa.String(32), nullable=False, server_default="other"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])


def downgrade() -> None:
    op.drop_index("ix_support_tickets_status", "support_tickets")
    op.drop_index("ix_support_tickets_user_id", "support_tickets")
    op.drop_table("support_tickets")
    op.drop_column("users", "suspension_reason")
    op.drop_column("users", "ban_reason")
    op.drop_column("users", "is_locked")
    op.drop_column("users", "is_suspended")
