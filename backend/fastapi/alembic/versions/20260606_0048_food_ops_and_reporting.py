"""food ops and reporting

Revision ID: 20260606_0048
Revises: 20260606_0047
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0048"
down_revision = "20260606_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_partners", sa.Column("service_zone_id", sa.String(length=36), nullable=True))
    op.add_column("restaurant_partners", sa.Column("accepting_orders", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("restaurant_partners", sa.Column("is_temporarily_closed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("restaurant_partners", sa.Column("prep_buffer_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("restaurant_partners", sa.Column("opening_hours_json", sa.Text(), nullable=True))
    op.create_foreign_key(None, "restaurant_partners", "service_zones", ["service_zone_id"], ["id"])
    op.create_index(op.f("ix_restaurant_partners_service_zone_id"), "restaurant_partners", ["service_zone_id"], unique=False)

    op.add_column("restaurant_menu_items", sa.Column("is_sold_out", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("restaurant_menu_items", sa.Column("track_inventory", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("restaurant_menu_items", sa.Column("stock_quantity", sa.Integer(), nullable=True))
    op.add_column("restaurant_menu_items", sa.Column("available_from_hour", sa.String(length=5), nullable=True))
    op.add_column("restaurant_menu_items", sa.Column("available_to_hour", sa.String(length=5), nullable=True))

    op.create_table(
        "restaurant_payout_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_meal_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("released_payout_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("refunded_meal_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("pending_meal_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("delivery_fee_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant_partners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_key", "restaurant_id", "currency", name="uq_restaurant_payout_snapshot_period_restaurant_currency"),
    )
    op.create_index(op.f("ix_restaurant_payout_snapshots_currency"), "restaurant_payout_snapshots", ["currency"], unique=False)
    op.create_index(op.f("ix_restaurant_payout_snapshots_period_key"), "restaurant_payout_snapshots", ["period_key"], unique=False)
    op.create_index(op.f("ix_restaurant_payout_snapshots_restaurant_id"), "restaurant_payout_snapshots", ["restaurant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_restaurant_payout_snapshots_restaurant_id"), table_name="restaurant_payout_snapshots")
    op.drop_index(op.f("ix_restaurant_payout_snapshots_period_key"), table_name="restaurant_payout_snapshots")
    op.drop_index(op.f("ix_restaurant_payout_snapshots_currency"), table_name="restaurant_payout_snapshots")
    op.drop_table("restaurant_payout_snapshots")

    op.drop_column("restaurant_menu_items", "available_to_hour")
    op.drop_column("restaurant_menu_items", "available_from_hour")
    op.drop_column("restaurant_menu_items", "stock_quantity")
    op.drop_column("restaurant_menu_items", "track_inventory")
    op.drop_column("restaurant_menu_items", "is_sold_out")

    op.drop_index(op.f("ix_restaurant_partners_service_zone_id"), table_name="restaurant_partners")
    op.drop_constraint(None, "restaurant_partners", type_="foreignkey")
    op.drop_column("restaurant_partners", "opening_hours_json")
    op.drop_column("restaurant_partners", "prep_buffer_minutes")
    op.drop_column("restaurant_partners", "is_temporarily_closed")
    op.drop_column("restaurant_partners", "accepting_orders")
    op.drop_column("restaurant_partners", "service_zone_id")
