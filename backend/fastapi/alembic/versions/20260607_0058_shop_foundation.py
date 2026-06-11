"""shop foundation

Revision ID: 20260607_0058
Revises: 20260607_0057
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0058"
down_revision = "20260607_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_partners",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("service_zone_id", sa.String(length=36), nullable=True),
        sa.Column("public_name", sa.String(length=160), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("city_name", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("accepts_cash_on_delivery", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("accepting_orders", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("launch_status", sa.String(length=16), nullable=False, server_default="CONFIGURED"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_merchant_partners_owner"),
        sa.ForeignKeyConstraint(["service_zone_id"], ["service_zones.id"], name="fk_merchant_partners_service_zone"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_partners_owner_user_id", "merchant_partners", ["owner_user_id"], unique=False)
    op.create_index("ix_merchant_partners_public_name", "merchant_partners", ["public_name"], unique=False)
    op.create_index("ix_merchant_partners_country_code", "merchant_partners", ["country_code"], unique=False)

    op.create_table(
        "merchant_staff_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("staff_role", sa.String(length=32), nullable=False, server_default="manager"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant_partners.id"], name="fk_merchant_staff_assignments_merchant"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_merchant_staff_assignments_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_staff_assignments_merchant_id", "merchant_staff_assignments", ["merchant_id"], unique=False)
    op.create_index("ix_merchant_staff_assignments_user_id", "merchant_staff_assignments", ["user_id"], unique=False)

    op.create_table(
        "merchant_catalogs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant_partners.id"], name="fk_merchant_catalogs_merchant"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_catalogs_merchant_id", "merchant_catalogs", ["merchant_id"], unique=False)

    op.create_table(
        "merchant_catalog_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("catalog_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("track_inventory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_sold_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("attributes_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["catalog_id"], ["merchant_catalogs.id"], name="fk_merchant_catalog_items_catalog"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_catalog_items_catalog_id", "merchant_catalog_items", ["catalog_id"], unique=False)
    op.create_index("ix_merchant_catalog_items_name", "merchant_catalog_items", ["name"], unique=False)
    op.create_index("ix_merchant_catalog_items_category", "merchant_catalog_items", ["category"], unique=False)
    op.create_index("ix_merchant_catalog_items_sku", "merchant_catalog_items", ["sku"], unique=False)

    op.create_table(
        "shop_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("customer_user_id", sa.String(length=36), nullable=False),
        sa.Column("linked_task_id", sa.String(length=36), nullable=True),
        sa.Column("beneficiary_name", sa.String(length=160), nullable=True),
        sa.Column("beneficiary_phone", sa.String(length=32), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("delivery_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("payment_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="shop"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant_partners.id"], name="fk_shop_orders_merchant"),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], name="fk_shop_orders_customer"),
        sa.ForeignKeyConstraint(["linked_task_id"], ["tasks.id"], name="fk_shop_orders_linked_task"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_orders_merchant_id", "shop_orders", ["merchant_id"], unique=False)
    op.create_index("ix_shop_orders_customer_user_id", "shop_orders", ["customer_user_id"], unique=False)
    op.create_index("ix_shop_orders_status", "shop_orders", ["status"], unique=False)

    op.create_table(
        "shop_order_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shop_order_id", sa.String(length=36), nullable=False),
        sa.Column("catalog_item_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("line_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_order_id"], ["shop_orders.id"], name="fk_shop_order_items_order"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["merchant_catalog_items.id"], name="fk_shop_order_items_item"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_order_items_shop_order_id", "shop_order_items", ["shop_order_id"], unique=False)
    op.create_index("ix_shop_order_items_catalog_item_id", "shop_order_items", ["catalog_item_id"], unique=False)

    op.alter_column("merchant_partners", "accepts_cash_on_delivery", server_default=None)
    op.alter_column("merchant_partners", "is_active", server_default=None)
    op.alter_column("merchant_partners", "accepting_orders", server_default=None)
    op.alter_column("merchant_partners", "launch_status", server_default=None)
    op.alter_column("merchant_staff_assignments", "staff_role", server_default=None)
    op.alter_column("merchant_staff_assignments", "is_primary", server_default=None)
    op.alter_column("merchant_staff_assignments", "is_active", server_default=None)
    op.alter_column("merchant_catalogs", "is_active", server_default=None)
    op.alter_column("merchant_catalogs", "is_default", server_default=None)
    op.alter_column("merchant_catalog_items", "track_inventory", server_default=None)
    op.alter_column("merchant_catalog_items", "is_available", server_default=None)
    op.alter_column("merchant_catalog_items", "is_sold_out", server_default=None)
    op.alter_column("shop_orders", "delivery_amount", server_default=None)
    op.alter_column("shop_orders", "status", server_default=None)
    op.alter_column("shop_orders", "payment_status", server_default=None)
    op.alter_column("shop_orders", "source", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_shop_order_items_catalog_item_id", table_name="shop_order_items")
    op.drop_index("ix_shop_order_items_shop_order_id", table_name="shop_order_items")
    op.drop_table("shop_order_items")

    op.drop_index("ix_shop_orders_status", table_name="shop_orders")
    op.drop_index("ix_shop_orders_customer_user_id", table_name="shop_orders")
    op.drop_index("ix_shop_orders_merchant_id", table_name="shop_orders")
    op.drop_table("shop_orders")

    op.drop_index("ix_merchant_catalog_items_sku", table_name="merchant_catalog_items")
    op.drop_index("ix_merchant_catalog_items_category", table_name="merchant_catalog_items")
    op.drop_index("ix_merchant_catalog_items_name", table_name="merchant_catalog_items")
    op.drop_index("ix_merchant_catalog_items_catalog_id", table_name="merchant_catalog_items")
    op.drop_table("merchant_catalog_items")

    op.drop_index("ix_merchant_catalogs_merchant_id", table_name="merchant_catalogs")
    op.drop_table("merchant_catalogs")

    op.drop_index("ix_merchant_staff_assignments_user_id", table_name="merchant_staff_assignments")
    op.drop_index("ix_merchant_staff_assignments_merchant_id", table_name="merchant_staff_assignments")
    op.drop_table("merchant_staff_assignments")

    op.drop_index("ix_merchant_partners_country_code", table_name="merchant_partners")
    op.drop_index("ix_merchant_partners_public_name", table_name="merchant_partners")
    op.drop_index("ix_merchant_partners_owner_user_id", table_name="merchant_partners")
    op.drop_table("merchant_partners")
