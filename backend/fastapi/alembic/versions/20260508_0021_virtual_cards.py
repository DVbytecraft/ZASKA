"""virtual_cards table

Revision ID: 20260508_0021
Revises: 20260508_0020
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0021"
down_revision = "20260508_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "virtual_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("card_type", sa.String(12), nullable=False),
        sa.Column("card_number_masked", sa.String(24), nullable=False),
        sa.Column("card_number_hash", sa.String(64), nullable=False),
        sa.Column("expiry_month", sa.Integer(), nullable=False),
        sa.Column("expiry_year", sa.Integer(), nullable=False),
        sa.Column("cvv_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("wallet_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_virtual_cards_user_id", "virtual_cards", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_virtual_cards_user_id", "virtual_cards")
    op.drop_table("virtual_cards")
