"""food domain foundation

Revision ID: 20260606_0046
Revises: 20260606_0045
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0046"
down_revision = "20260606_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_partners",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("public_name", sa.String(length=160), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("city_name", sa.String(length=128), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("accepts_cash_on_delivery", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("launch_status", sa.String(length=24), nullable=False, server_default="CONFIGURED"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_partner_country_city", "restaurant_partners", ["country_code", "city_name"], unique=False)
    op.create_index(op.f("ix_restaurant_partners_country_code"), "restaurant_partners", ["country_code"], unique=False)
    op.create_index(op.f("ix_restaurant_partners_city_name"), "restaurant_partners", ["city_name"], unique=False)
    op.create_index(op.f("ix_restaurant_partners_currency"), "restaurant_partners", ["currency"], unique=False)
    op.create_index(op.f("ix_restaurant_partners_owner_user_id"), "restaurant_partners", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_restaurant_partners_public_name"), "restaurant_partners", ["public_name"], unique=False)

    op.create_table(
        "restaurant_staff_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("staff_role", sa.String(length=32), nullable=False, server_default="manager"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant_partners.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("restaurant_id", "user_id", name="uq_restaurant_staff_assignment"),
    )
    op.create_index(op.f("ix_restaurant_staff_assignments_restaurant_id"), "restaurant_staff_assignments", ["restaurant_id"], unique=False)
    op.create_index(op.f("ix_restaurant_staff_assignments_user_id"), "restaurant_staff_assignments", ["user_id"], unique=False)

    op.create_table(
        "restaurant_menus",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant_partners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_menu_restaurant_active", "restaurant_menus", ["restaurant_id", "is_active"], unique=False)
    op.create_index(op.f("ix_restaurant_menus_restaurant_id"), "restaurant_menus", ["restaurant_id"], unique=False)

    op.create_table(
        "restaurant_menu_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("menu_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("prep_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["menu_id"], ["restaurant_menus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_menu_item_menu_available", "restaurant_menu_items", ["menu_id", "is_available"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_items_category"), "restaurant_menu_items", ["category"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_items_currency"), "restaurant_menu_items", ["currency"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_items_menu_id"), "restaurant_menu_items", ["menu_id"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_items_name"), "restaurant_menu_items", ["name"], unique=False)

    op.create_table(
        "food_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_user_id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("delivery_task_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_restaurant"),
        sa.Column("payment_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("city_name", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("subtotal", sa.Numeric(20, 6), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("restaurant_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("delivery_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("ordered_for_other", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("beneficiary_name", sa.String(length=160), nullable=True),
        sa.Column("beneficiary_phone", sa.String(length=32), nullable=True),
        sa.Column("delivery_address", sa.String(length=512), nullable=False),
        sa.Column("delivery_latitude", sa.Float(), nullable=True),
        sa.Column("delivery_longitude", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("estimated_prep_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("restaurant_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delivery_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant_partners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_food_order_customer_status", "food_orders", ["customer_user_id", "status"], unique=False)
    op.create_index("ix_food_order_restaurant_status", "food_orders", ["restaurant_id", "status"], unique=False)
    op.create_index("ix_food_order_country_city", "food_orders", ["country_code", "city_name"], unique=False)
    op.create_index(op.f("ix_food_orders_city_name"), "food_orders", ["city_name"], unique=False)
    op.create_index(op.f("ix_food_orders_country_code"), "food_orders", ["country_code"], unique=False)
    op.create_index(op.f("ix_food_orders_currency"), "food_orders", ["currency"], unique=False)
    op.create_index(op.f("ix_food_orders_customer_user_id"), "food_orders", ["customer_user_id"], unique=False)
    op.create_index(op.f("ix_food_orders_delivery_task_id"), "food_orders", ["delivery_task_id"], unique=False)
    op.create_index(op.f("ix_food_orders_restaurant_id"), "food_orders", ["restaurant_id"], unique=False)

    op.create_table(
        "food_order_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("food_order_id", sa.String(length=36), nullable=False),
        sa.Column("menu_item_id", sa.String(length=36), nullable=False),
        sa.Column("item_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("line_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_order_id"], ["food_orders.id"]),
        sa.ForeignKeyConstraint(["menu_item_id"], ["restaurant_menu_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_food_order_items_food_order_id"), "food_order_items", ["food_order_id"], unique=False)
    op.create_index(op.f("ix_food_order_items_menu_item_id"), "food_order_items", ["menu_item_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_food_order_items_menu_item_id"), table_name="food_order_items")
    op.drop_index(op.f("ix_food_order_items_food_order_id"), table_name="food_order_items")
    op.drop_table("food_order_items")

    op.drop_index(op.f("ix_food_orders_restaurant_id"), table_name="food_orders")
    op.drop_index(op.f("ix_food_orders_delivery_task_id"), table_name="food_orders")
    op.drop_index(op.f("ix_food_orders_customer_user_id"), table_name="food_orders")
    op.drop_index(op.f("ix_food_orders_currency"), table_name="food_orders")
    op.drop_index(op.f("ix_food_orders_country_code"), table_name="food_orders")
    op.drop_index(op.f("ix_food_orders_city_name"), table_name="food_orders")
    op.drop_index("ix_food_order_country_city", table_name="food_orders")
    op.drop_index("ix_food_order_restaurant_status", table_name="food_orders")
    op.drop_index("ix_food_order_customer_status", table_name="food_orders")
    op.drop_table("food_orders")

    op.drop_index(op.f("ix_restaurant_menu_items_name"), table_name="restaurant_menu_items")
    op.drop_index(op.f("ix_restaurant_menu_items_menu_id"), table_name="restaurant_menu_items")
    op.drop_index(op.f("ix_restaurant_menu_items_currency"), table_name="restaurant_menu_items")
    op.drop_index(op.f("ix_restaurant_menu_items_category"), table_name="restaurant_menu_items")
    op.drop_index("ix_restaurant_menu_item_menu_available", table_name="restaurant_menu_items")
    op.drop_table("restaurant_menu_items")

    op.drop_index(op.f("ix_restaurant_menus_restaurant_id"), table_name="restaurant_menus")
    op.drop_index("ix_restaurant_menu_restaurant_active", table_name="restaurant_menus")
    op.drop_table("restaurant_menus")

    op.drop_index(op.f("ix_restaurant_staff_assignments_user_id"), table_name="restaurant_staff_assignments")
    op.drop_index(op.f("ix_restaurant_staff_assignments_restaurant_id"), table_name="restaurant_staff_assignments")
    op.drop_table("restaurant_staff_assignments")

    op.drop_index(op.f("ix_restaurant_partners_public_name"), table_name="restaurant_partners")
    op.drop_index(op.f("ix_restaurant_partners_owner_user_id"), table_name="restaurant_partners")
    op.drop_index(op.f("ix_restaurant_partners_currency"), table_name="restaurant_partners")
    op.drop_index(op.f("ix_restaurant_partners_city_name"), table_name="restaurant_partners")
    op.drop_index(op.f("ix_restaurant_partners_country_code"), table_name="restaurant_partners")
    op.drop_index("ix_restaurant_partner_country_city", table_name="restaurant_partners")
    op.drop_table("restaurant_partners")
