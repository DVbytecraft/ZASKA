"""food payment and dispatch

Revision ID: 20260606_0047
Revises: 20260606_0046
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0047"
down_revision = "20260606_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_payment_holds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("food_order_id", sa.String(length=36), nullable=False),
        sa.Column("payer_user_id", sa.String(length=36), nullable=False),
        sa.Column("beneficiary_user_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="funded"),
        sa.Column("hold_type", sa.String(length=32), nullable=False, server_default="restaurant_meal_payout"),
        sa.Column("funding_tx_id", sa.String(length=36), nullable=True),
        sa.Column("settlement_tx_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beneficiary_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["food_order_id"], ["food_orders.id"]),
        sa.ForeignKeyConstraint(["funding_tx_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["payer_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["settlement_tx_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_food_payment_hold_order_status", "food_payment_holds", ["food_order_id", "status"], unique=False)
    op.create_index(op.f("ix_food_payment_holds_beneficiary_user_id"), "food_payment_holds", ["beneficiary_user_id"], unique=False)
    op.create_index(op.f("ix_food_payment_holds_currency"), "food_payment_holds", ["currency"], unique=False)
    op.create_index(op.f("ix_food_payment_holds_food_order_id"), "food_payment_holds", ["food_order_id"], unique=False)
    op.create_index(op.f("ix_food_payment_holds_funding_tx_id"), "food_payment_holds", ["funding_tx_id"], unique=False)
    op.create_index(op.f("ix_food_payment_holds_payer_user_id"), "food_payment_holds", ["payer_user_id"], unique=False)
    op.create_index(op.f("ix_food_payment_holds_settlement_tx_id"), "food_payment_holds", ["settlement_tx_id"], unique=False)

    op.add_column("food_orders", sa.Column("meal_hold_id", sa.String(length=36), nullable=True))
    op.add_column("food_orders", sa.Column("delivery_escrow_id", sa.String(length=36), nullable=True))
    op.add_column("food_orders", sa.Column("dispatch_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.create_foreign_key(None, "food_orders", "food_payment_holds", ["meal_hold_id"], ["id"])
    op.create_foreign_key(None, "food_orders", "escrows", ["delivery_escrow_id"], ["id"])
    op.create_index(op.f("ix_food_orders_meal_hold_id"), "food_orders", ["meal_hold_id"], unique=False)
    op.create_index(op.f("ix_food_orders_delivery_escrow_id"), "food_orders", ["delivery_escrow_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_food_orders_delivery_escrow_id"), table_name="food_orders")
    op.drop_index(op.f("ix_food_orders_meal_hold_id"), table_name="food_orders")
    op.drop_constraint(None, "food_orders", type_="foreignkey")
    op.drop_constraint(None, "food_orders", type_="foreignkey")
    op.drop_column("food_orders", "dispatch_status")
    op.drop_column("food_orders", "delivery_escrow_id")
    op.drop_column("food_orders", "meal_hold_id")

    op.drop_index(op.f("ix_food_payment_holds_settlement_tx_id"), table_name="food_payment_holds")
    op.drop_index(op.f("ix_food_payment_holds_payer_user_id"), table_name="food_payment_holds")
    op.drop_index(op.f("ix_food_payment_holds_funding_tx_id"), table_name="food_payment_holds")
    op.drop_index(op.f("ix_food_payment_holds_food_order_id"), table_name="food_payment_holds")
    op.drop_index(op.f("ix_food_payment_holds_currency"), table_name="food_payment_holds")
    op.drop_index(op.f("ix_food_payment_holds_beneficiary_user_id"), table_name="food_payment_holds")
    op.drop_index("ix_food_payment_hold_order_status", table_name="food_payment_holds")
    op.drop_table("food_payment_holds")
