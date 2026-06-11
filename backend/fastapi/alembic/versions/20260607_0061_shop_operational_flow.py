"""shop operational flow

Revision ID: 20260607_0061
Revises: 20260607_0060
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0061"
down_revision = "20260607_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchant_partners", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("merchant_partners", sa.Column("longitude", sa.Float(), nullable=True))

    op.create_table(
        "shop_payment_holds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shop_order_id", sa.String(length=36), nullable=False),
        sa.Column("payer_user_id", sa.String(length=36), nullable=False),
        sa.Column("beneficiary_user_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="funded"),
        sa.Column("funding_tx_id", sa.String(length=36), nullable=True),
        sa.Column("settlement_tx_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shop_order_id"], ["shop_orders.id"], name="fk_shop_payment_holds_order"),
        sa.ForeignKeyConstraint(["payer_user_id"], ["users.id"], name="fk_shop_payment_holds_payer"),
        sa.ForeignKeyConstraint(["beneficiary_user_id"], ["users.id"], name="fk_shop_payment_holds_beneficiary"),
        sa.ForeignKeyConstraint(["funding_tx_id"], ["transactions.id"], name="fk_shop_payment_holds_funding_tx"),
        sa.ForeignKeyConstraint(["settlement_tx_id"], ["transactions.id"], name="fk_shop_payment_holds_settlement_tx"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_payment_holds_shop_order_id", "shop_payment_holds", ["shop_order_id"], unique=False)
    op.create_index("ix_shop_payment_holds_status", "shop_payment_holds", ["status"], unique=False)
    op.alter_column("shop_payment_holds", "status", server_default=None)

    op.add_column("shop_orders", sa.Column("delivery_task_id", sa.String(length=36), nullable=True))
    op.add_column("shop_orders", sa.Column("delivery_escrow_id", sa.String(length=36), nullable=True))
    op.add_column("shop_orders", sa.Column("merchandise_hold_id", sa.String(length=36), nullable=True))
    op.add_column("shop_orders", sa.Column("ordered_for_other", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("shop_orders", sa.Column("delivery_address", sa.String(length=512), nullable=True))
    op.add_column("shop_orders", sa.Column("delivery_latitude", sa.Float(), nullable=True))
    op.add_column("shop_orders", sa.Column("delivery_longitude", sa.Float(), nullable=True))
    op.add_column("shop_orders", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column("shop_orders", sa.Column("city_name", sa.String(length=128), nullable=True))
    op.add_column("shop_orders", sa.Column("fulfillment_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("shop_orders", sa.Column("dispatch_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("shop_orders", sa.Column("customer_note", sa.Text(), nullable=True))
    op.add_column("shop_orders", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("shop_orders", sa.Column("customer_funded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_orders", sa.Column("merchant_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_orders", sa.Column("ready_for_dispatch_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_orders", sa.Column("payout_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_shop_orders_delivery_task_id", "shop_orders", ["delivery_task_id"], unique=False)
    op.create_index("ix_shop_orders_delivery_escrow_id", "shop_orders", ["delivery_escrow_id"], unique=False)
    op.create_index("ix_shop_orders_merchandise_hold_id", "shop_orders", ["merchandise_hold_id"], unique=False)
    op.create_index("ix_shop_orders_country_code", "shop_orders", ["country_code"], unique=False)
    op.create_index("ix_shop_orders_fulfillment_status", "shop_orders", ["fulfillment_status"], unique=False)
    op.create_index("ix_shop_orders_dispatch_status", "shop_orders", ["dispatch_status"], unique=False)
    op.create_foreign_key("fk_shop_orders_delivery_task", "shop_orders", "tasks", ["delivery_task_id"], ["id"])
    op.create_foreign_key("fk_shop_orders_delivery_escrow", "shop_orders", "escrows", ["delivery_escrow_id"], ["id"])
    op.create_foreign_key("fk_shop_orders_merchandise_hold", "shop_orders", "shop_payment_holds", ["merchandise_hold_id"], ["id"])
    op.alter_column("shop_orders", "ordered_for_other", server_default=None)
    op.alter_column("shop_orders", "fulfillment_status", server_default=None)
    op.alter_column("shop_orders", "dispatch_status", server_default=None)

    op.create_table(
        "shop_merchant_payout_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("period_key", sa.String(length=16), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_goods_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("released_payout_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("refunded_goods_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("pending_goods_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("delivery_fee_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant_partners.id"], name="fk_shop_payout_snapshots_merchant"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_merchant_payout_snapshots_period_key", "shop_merchant_payout_snapshots", ["period_key"], unique=False)
    op.create_index("ix_shop_merchant_payout_snapshots_merchant_id", "shop_merchant_payout_snapshots", ["merchant_id"], unique=False)
    op.create_index("ix_shop_merchant_payout_snapshots_currency", "shop_merchant_payout_snapshots", ["currency"], unique=False)
    op.alter_column("shop_merchant_payout_snapshots", "order_count", server_default=None)
    op.alter_column("shop_merchant_payout_snapshots", "gross_goods_total", server_default=None)
    op.alter_column("shop_merchant_payout_snapshots", "released_payout_total", server_default=None)
    op.alter_column("shop_merchant_payout_snapshots", "refunded_goods_total", server_default=None)
    op.alter_column("shop_merchant_payout_snapshots", "pending_goods_total", server_default=None)
    op.alter_column("shop_merchant_payout_snapshots", "delivery_fee_total", server_default=None)

    op.create_table(
        "shop_order_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shop_order_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_order_id"], ["shop_orders.id"], name="fk_shop_order_events_order"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_shop_order_events_actor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_order_events_shop_order_id", "shop_order_events", ["shop_order_id"], unique=False)
    op.create_index("ix_shop_order_events_event_type", "shop_order_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shop_order_events_event_type", table_name="shop_order_events")
    op.drop_index("ix_shop_order_events_shop_order_id", table_name="shop_order_events")
    op.drop_table("shop_order_events")

    op.drop_index("ix_shop_merchant_payout_snapshots_currency", table_name="shop_merchant_payout_snapshots")
    op.drop_index("ix_shop_merchant_payout_snapshots_merchant_id", table_name="shop_merchant_payout_snapshots")
    op.drop_index("ix_shop_merchant_payout_snapshots_period_key", table_name="shop_merchant_payout_snapshots")
    op.drop_table("shop_merchant_payout_snapshots")

    op.drop_constraint("fk_shop_orders_merchandise_hold", "shop_orders", type_="foreignkey")
    op.drop_constraint("fk_shop_orders_delivery_escrow", "shop_orders", type_="foreignkey")
    op.drop_constraint("fk_shop_orders_delivery_task", "shop_orders", type_="foreignkey")
    op.drop_index("ix_shop_orders_dispatch_status", table_name="shop_orders")
    op.drop_index("ix_shop_orders_fulfillment_status", table_name="shop_orders")
    op.drop_index("ix_shop_orders_country_code", table_name="shop_orders")
    op.drop_index("ix_shop_orders_merchandise_hold_id", table_name="shop_orders")
    op.drop_index("ix_shop_orders_delivery_escrow_id", table_name="shop_orders")
    op.drop_index("ix_shop_orders_delivery_task_id", table_name="shop_orders")
    op.drop_column("shop_orders", "payout_completed_at")
    op.drop_column("shop_orders", "cancelled_at")
    op.drop_column("shop_orders", "delivered_at")
    op.drop_column("shop_orders", "ready_for_dispatch_at")
    op.drop_column("shop_orders", "merchant_confirmed_at")
    op.drop_column("shop_orders", "customer_funded_at")
    op.drop_column("shop_orders", "cancellation_reason")
    op.drop_column("shop_orders", "customer_note")
    op.drop_column("shop_orders", "dispatch_status")
    op.drop_column("shop_orders", "fulfillment_status")
    op.drop_column("shop_orders", "city_name")
    op.drop_column("shop_orders", "country_code")
    op.drop_column("shop_orders", "delivery_longitude")
    op.drop_column("shop_orders", "delivery_latitude")
    op.drop_column("shop_orders", "delivery_address")
    op.drop_column("shop_orders", "ordered_for_other")
    op.drop_column("shop_orders", "merchandise_hold_id")
    op.drop_column("shop_orders", "delivery_escrow_id")
    op.drop_column("shop_orders", "delivery_task_id")

    op.drop_index("ix_shop_payment_holds_status", table_name="shop_payment_holds")
    op.drop_index("ix_shop_payment_holds_shop_order_id", table_name="shop_payment_holds")
    op.drop_table("shop_payment_holds")

    op.drop_column("merchant_partners", "longitude")
    op.drop_column("merchant_partners", "latitude")
