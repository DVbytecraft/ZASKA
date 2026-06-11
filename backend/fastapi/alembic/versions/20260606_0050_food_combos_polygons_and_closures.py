"""food combos polygons and closures

Revision ID: 20260606_0050
Revises: 20260606_0049
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0050"
down_revision = "20260606_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("food_order_items", sa.Column("combo_offer_id", sa.String(length=36), nullable=True))
    op.add_column("food_order_items", sa.Column("line_type", sa.String(length=24), nullable=False, server_default="menu_item"))

    op.create_table(
        "restaurant_special_closures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant_partners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_special_closure_window", "restaurant_special_closures", ["restaurant_id", "starts_at", "ends_at"], unique=False)
    op.create_index(op.f("ix_restaurant_special_closures_restaurant_id"), "restaurant_special_closures", ["restaurant_id"], unique=False)

    op.create_table(
        "restaurant_combo_offers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("available_from_hour", sa.String(length=5), nullable=True),
        sa.Column("available_to_hour", sa.String(length=5), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant_partners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_combo_offer_restaurant_active", "restaurant_combo_offers", ["restaurant_id", "is_active"], unique=False)
    op.create_index(op.f("ix_restaurant_combo_offers_currency"), "restaurant_combo_offers", ["currency"], unique=False)
    op.create_index(op.f("ix_restaurant_combo_offers_restaurant_id"), "restaurant_combo_offers", ["restaurant_id"], unique=False)

    op.create_table(
        "restaurant_combo_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("combo_offer_id", sa.String(length=36), nullable=False),
        sa.Column("menu_item_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["combo_offer_id"], ["restaurant_combo_offers.id"]),
        sa.ForeignKeyConstraint(["menu_item_id"], ["restaurant_menu_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_combo_item_combo", "restaurant_combo_items", ["combo_offer_id", "menu_item_id"], unique=False)
    op.create_index(op.f("ix_restaurant_combo_items_combo_offer_id"), "restaurant_combo_items", ["combo_offer_id"], unique=False)
    op.create_index(op.f("ix_restaurant_combo_items_menu_item_id"), "restaurant_combo_items", ["menu_item_id"], unique=False)

    op.create_foreign_key(None, "food_order_items", "restaurant_combo_offers", ["combo_offer_id"], ["id"])
    op.create_index(op.f("ix_food_order_items_combo_offer_id"), "food_order_items", ["combo_offer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_restaurant_combo_items_menu_item_id"), table_name="restaurant_combo_items")
    op.drop_index(op.f("ix_restaurant_combo_items_combo_offer_id"), table_name="restaurant_combo_items")
    op.drop_index("ix_restaurant_combo_item_combo", table_name="restaurant_combo_items")
    op.drop_table("restaurant_combo_items")

    op.drop_index(op.f("ix_restaurant_combo_offers_restaurant_id"), table_name="restaurant_combo_offers")
    op.drop_index(op.f("ix_restaurant_combo_offers_currency"), table_name="restaurant_combo_offers")
    op.drop_index("ix_restaurant_combo_offer_restaurant_active", table_name="restaurant_combo_offers")
    op.drop_table("restaurant_combo_offers")

    op.drop_index(op.f("ix_restaurant_special_closures_restaurant_id"), table_name="restaurant_special_closures")
    op.drop_index("ix_restaurant_special_closure_window", table_name="restaurant_special_closures")
    op.drop_table("restaurant_special_closures")

    op.drop_index(op.f("ix_food_order_items_combo_offer_id"), table_name="food_order_items")
    op.drop_constraint(None, "food_order_items", type_="foreignkey")
    op.drop_column("food_order_items", "line_type")
    op.drop_column("food_order_items", "combo_offer_id")
