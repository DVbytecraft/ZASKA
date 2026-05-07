"""CHECK constraints, missing indexes, payment_method unique constraint, webhook_idempotency table

Revision ID: 20260507_0014
Revises: 20260507_0013
Create Date: 2026-05-07
"""

import sqlalchemy as sa
from alembic import op

revision = "20260507_0014"
down_revision = "20260507_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── webhook_idempotency table ──────────────────────────────────────────────
    op.create_table(
        "webhook_idempotency",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload_fingerprint", sa.String(64), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_webhook_idempotency_key", "webhook_idempotency", ["idempotency_key"], unique=True)

    # ── Missing indexes ────────────────────────────────────────────────────────

    # tasks: assigned_to and status
    op.create_index("ix_task_assigned_to", "tasks", ["assigned_to"])
    op.create_index("ix_task_status", "tasks", ["status"])

    # payouts: status
    op.create_index("ix_payout_status", "payouts", ["status"])

    # escrows: funding_tx_id, settlement_tx_id
    op.create_index("ix_escrow_funding_tx", "escrows", ["funding_tx_id"])
    op.create_index("ix_escrow_settlement_tx", "escrows", ["settlement_tx_id"])

    # ── Unique constraint: payment_methods (user_id, provider, phone_number) ───
    op.create_unique_constraint(
        "uq_payment_method_user_provider_phone",
        "payment_methods",
        ["user_id", "provider", "phone_number"],
    )

    # ── CHECK constraints ──────────────────────────────────────────────────────
    # wallet balance >= 0
    op.create_check_constraint(
        "ck_wallet_balance_non_negative",
        "wallets",
        "balance >= 0",
    )
    # transaction amount > 0
    op.create_check_constraint(
        "ck_transaction_amount_positive",
        "transactions",
        "amount > 0",
    )
    # task price > 0
    op.create_check_constraint(
        "ck_task_price_positive",
        "tasks",
        "price > 0",
    )
    # payout amount > 0
    op.create_check_constraint(
        "ck_payout_amount_positive",
        "payouts",
        "amount > 0",
    )
    # task latitude bounds
    op.create_check_constraint(
        "ck_task_latitude_bounds",
        "tasks",
        "latitude >= -90 AND latitude <= 90",
    )
    # task longitude bounds
    op.create_check_constraint(
        "ck_task_longitude_bounds",
        "tasks",
        "longitude >= -180 AND longitude <= 180",
    )


def downgrade() -> None:
    op.drop_constraint("ck_task_longitude_bounds", "tasks", type_="check")
    op.drop_constraint("ck_task_latitude_bounds", "tasks", type_="check")
    op.drop_constraint("ck_payout_amount_positive", "payouts", type_="check")
    op.drop_constraint("ck_task_price_positive", "tasks", type_="check")
    op.drop_constraint("ck_transaction_amount_positive", "transactions", type_="check")
    op.drop_constraint("ck_wallet_balance_non_negative", "wallets", type_="check")
    op.drop_constraint("uq_payment_method_user_provider_phone", "payment_methods", type_="unique")
    op.drop_index("ix_escrow_settlement_tx", "escrows")
    op.drop_index("ix_escrow_funding_tx", "escrows")
    op.drop_index("ix_payout_status", "payouts")
    op.drop_index("ix_task_status", "tasks")
    op.drop_index("ix_task_assigned_to", "tasks")
    op.drop_index("ix_webhook_idempotency_key", "webhook_idempotency")
    op.drop_table("webhook_idempotency")
