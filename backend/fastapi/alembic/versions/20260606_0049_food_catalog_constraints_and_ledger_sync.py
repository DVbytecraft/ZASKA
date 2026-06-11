"""food catalog constraints and ledger sync

Revision ID: 20260606_0049
Revises: 20260606_0048
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0049"
down_revision = "20260606_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("food_order_items", sa.Column("modifier_total", sa.Numeric(20, 6), nullable=False, server_default="0"))

    op.create_table(
        "restaurant_menu_item_modifier_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("menu_item_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("min_select", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_select", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["restaurant_menu_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_modifier_group_item_active", "restaurant_menu_item_modifier_groups", ["menu_item_id", "is_active"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_item_modifier_groups_menu_item_id"), "restaurant_menu_item_modifier_groups", ["menu_item_id"], unique=False)

    op.create_table(
        "restaurant_menu_item_modifier_options",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("modifier_group_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("price_delta", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["modifier_group_id"], ["restaurant_menu_item_modifier_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_modifier_option_group_active", "restaurant_menu_item_modifier_options", ["modifier_group_id", "is_active"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_item_modifier_options_currency"), "restaurant_menu_item_modifier_options", ["currency"], unique=False)
    op.create_index(op.f("ix_restaurant_menu_item_modifier_options_modifier_group_id"), "restaurant_menu_item_modifier_options", ["modifier_group_id"], unique=False)

    op.create_table(
        "food_order_item_modifier_selections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("food_order_item_id", sa.String(length=36), nullable=False),
        sa.Column("modifier_group_id", sa.String(length=36), nullable=False),
        sa.Column("modifier_option_id", sa.String(length=36), nullable=False),
        sa.Column("group_name", sa.String(length=120), nullable=False),
        sa.Column("option_name", sa.String(length=120), nullable=False),
        sa.Column("price_delta", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_order_item_id"], ["food_order_items.id"]),
        sa.ForeignKeyConstraint(["modifier_group_id"], ["restaurant_menu_item_modifier_groups.id"]),
        sa.ForeignKeyConstraint(["modifier_option_id"], ["restaurant_menu_item_modifier_options.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_food_order_item_modifier_selections_food_order_item_id"), "food_order_item_modifier_selections", ["food_order_item_id"], unique=False)
    op.create_index(op.f("ix_food_order_item_modifier_selections_modifier_group_id"), "food_order_item_modifier_selections", ["modifier_group_id"], unique=False)
    op.create_index(op.f("ix_food_order_item_modifier_selections_modifier_option_id"), "food_order_item_modifier_selections", ["modifier_option_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_food_order_item_modifier_selections_modifier_option_id"), table_name="food_order_item_modifier_selections")
    op.drop_index(op.f("ix_food_order_item_modifier_selections_modifier_group_id"), table_name="food_order_item_modifier_selections")
    op.drop_index(op.f("ix_food_order_item_modifier_selections_food_order_item_id"), table_name="food_order_item_modifier_selections")
    op.drop_table("food_order_item_modifier_selections")

    op.drop_index(op.f("ix_restaurant_menu_item_modifier_options_modifier_group_id"), table_name="restaurant_menu_item_modifier_options")
    op.drop_index(op.f("ix_restaurant_menu_item_modifier_options_currency"), table_name="restaurant_menu_item_modifier_options")
    op.drop_index("ix_restaurant_modifier_option_group_active", table_name="restaurant_menu_item_modifier_options")
    op.drop_table("restaurant_menu_item_modifier_options")

    op.drop_index(op.f("ix_restaurant_menu_item_modifier_groups_menu_item_id"), table_name="restaurant_menu_item_modifier_groups")
    op.drop_index("ix_restaurant_modifier_group_item_active", table_name="restaurant_menu_item_modifier_groups")
    op.drop_table("restaurant_menu_item_modifier_groups")

    op.drop_column("food_order_items", "modifier_total")
