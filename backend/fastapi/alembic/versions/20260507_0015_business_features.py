"""Business features: negotiation, completion codes, 24h hold, addresses, virtual cards

Revision ID: 20260507_0015
Revises: 20260507_0014
Create Date: 2026-05-07
"""

import sqlalchemy as sa
from alembic import op

revision = "20260507_0015"
down_revision = "20260507_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tasks: new columns ────────────────────────────────────────────────────
    op.add_column("tasks", sa.Column("address", sa.String(512), nullable=True))
    op.add_column("tasks", sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("tasks", sa.Column("negotiation_status", sa.String(16), nullable=False, server_default="none"))
    op.add_column("tasks", sa.Column("negotiated_price", sa.Numeric(20, 6), nullable=True))
    op.add_column("tasks", sa.Column("negotiated_by", sa.String(36), nullable=True))

    # ── escrows: new columns ──────────────────────────────────────────────────
    op.add_column("escrows", sa.Column("provider", sa.String(32), nullable=True))
    op.add_column("escrows", sa.Column("provider_tx_id", sa.String(128), nullable=True))
    op.add_column("escrows", sa.Column("payout_available_at", sa.DateTime(), nullable=True))
    op.add_column("escrows", sa.Column("contested_at", sa.DateTime(), nullable=True))

    # Extend escrow status to support new states
    op.alter_column("escrows", "status", type_=sa.String(24), existing_nullable=False)

    # Extend task status to support NEGOTIATING etc
    op.alter_column("tasks", "status", type_=sa.String(24), existing_nullable=True)

    # ── task_completion_codes table ───────────────────────────────────────────
    op.create_table(
        "task_completion_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_completion_codes_task", "task_completion_codes", ["task_id"])

    # ── user_addresses table ──────────────────────────────────────────────────
    op.create_table(
        "user_addresses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("street", sa.String(255), nullable=False),
        sa.Column("city", sa.String(128), nullable=False),
        sa.Column("country", sa.String(64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_addresses_user", "user_addresses", ["user_id"])

    # ── virtual_cards table ───────────────────────────────────────────────────
    op.create_table(
        "virtual_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("card_type", sa.String(12), nullable=False),
        sa.Column("card_number_masked", sa.String(24), nullable=False),
        sa.Column("card_number_hash", sa.String(64), nullable=False),
        sa.Column("expiry_month", sa.Integer(), nullable=False),
        sa.Column("expiry_year", sa.Integer(), nullable=False),
        sa.Column("cvv_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("wallet_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_virtual_cards_user", "virtual_cards", ["user_id"])


def downgrade() -> None:
    op.drop_table("virtual_cards")
    op.drop_table("user_addresses")
    op.drop_table("task_completion_codes")

    op.drop_column("escrows", "contested_at")
    op.drop_column("escrows", "payout_available_at")
    op.drop_column("escrows", "provider_tx_id")
    op.drop_column("escrows", "provider")

    op.drop_column("tasks", "negotiated_by")
    op.drop_column("tasks", "negotiated_price")
    op.drop_column("tasks", "negotiation_status")
    op.drop_column("tasks", "completion_percent")
    op.drop_column("tasks", "address")
