"""vtc operational flow

Revision ID: 20260607_0060
Revises: 20260607_0059
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0060"
down_revision = "20260607_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vtc_driver_profiles", sa.Column("current_ride_id", sa.String(length=36), nullable=True))
    op.add_column("vtc_driver_profiles", sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("vtc_driver_profiles", sa.Column("availability_status", sa.String(length=24), nullable=False, server_default="offline"))
    op.add_column("vtc_driver_profiles", sa.Column("current_latitude", sa.Float(), nullable=True))
    op.add_column("vtc_driver_profiles", sa.Column("current_longitude", sa.Float(), nullable=True))
    op.add_column("vtc_driver_profiles", sa.Column("last_location_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_driver_profiles", sa.Column("rides_completed_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vtc_driver_profiles", sa.Column("rides_cancelled_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_vtc_driver_profiles_current_ride_id", "vtc_driver_profiles", ["current_ride_id"], unique=False)
    op.create_index("ix_vtc_driver_profiles_availability_status", "vtc_driver_profiles", ["availability_status"], unique=False)
    op.create_foreign_key(
        "fk_vtc_driver_profiles_current_ride",
        "vtc_driver_profiles",
        "vtc_ride_requests",
        ["current_ride_id"],
        ["id"],
    )

    op.add_column("vtc_ride_requests", sa.Column("cancelled_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("ride_code", sa.String(length=24), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("driver_en_route_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("driver_arrived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("payout_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("driver_offer_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("quoted_fare", sa.Numeric(20, 6), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("base_fare_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("distance_fare_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("time_fare_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("surge_multiplier", sa.Numeric(8, 4), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("platform_fee_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("driver_payout_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("dispatch_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("vtc_ride_requests", sa.Column("payout_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("vtc_ride_requests", sa.Column("customer_note", sa.Text(), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("last_driver_latitude", sa.Float(), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("last_driver_longitude", sa.Float(), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("last_driver_heading", sa.Float(), nullable=True))
    op.add_column("vtc_ride_requests", sa.Column("last_driver_location_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_vtc_ride_requests_ride_code", "vtc_ride_requests", ["ride_code"], unique=False)
    op.create_index("ix_vtc_ride_requests_dispatch_status", "vtc_ride_requests", ["dispatch_status"], unique=False)
    op.create_index("ix_vtc_ride_requests_payout_status", "vtc_ride_requests", ["payout_status"], unique=False)
    op.create_index("ix_vtc_ride_requests_cancelled_by_user_id", "vtc_ride_requests", ["cancelled_by_user_id"], unique=False)
    op.create_foreign_key(
        "fk_vtc_ride_requests_cancelled_by_user",
        "vtc_ride_requests",
        "users",
        ["cancelled_by_user_id"],
        ["id"],
    )

    op.execute("UPDATE vtc_ride_requests SET requested_at = created_at WHERE requested_at IS NULL")
    op.alter_column("vtc_ride_requests", "requested_at", nullable=False)

    op.create_table(
        "vtc_ride_dispatch_offers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ride_id", sa.String(length=36), nullable=False),
        sa.Column("driver_user_id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("vehicle_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("distance_to_pickup_km", sa.Numeric(12, 3), nullable=True),
        sa.Column("ranking_score", sa.Numeric(12, 6), nullable=True),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ride_id"], ["vtc_ride_requests.id"], name="fk_vtc_dispatch_offers_ride"),
        sa.ForeignKeyConstraint(["driver_user_id"], ["users.id"], name="fk_vtc_dispatch_offers_driver"),
        sa.ForeignKeyConstraint(["operator_id"], ["vtc_fleet_operators.id"], name="fk_vtc_dispatch_offers_operator"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vtc_vehicles.id"], name="fk_vtc_dispatch_offers_vehicle"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vtc_ride_dispatch_offers_ride_id", "vtc_ride_dispatch_offers", ["ride_id"], unique=False)
    op.create_index("ix_vtc_ride_dispatch_offers_driver_user_id", "vtc_ride_dispatch_offers", ["driver_user_id"], unique=False)
    op.create_index("ix_vtc_ride_dispatch_offers_status", "vtc_ride_dispatch_offers", ["status"], unique=False)
    op.alter_column("vtc_ride_dispatch_offers", "status", server_default=None)

    op.create_table(
        "vtc_ride_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ride_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ride_id"], ["vtc_ride_requests.id"], name="fk_vtc_ride_events_ride"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_vtc_ride_events_actor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vtc_ride_events_ride_id", "vtc_ride_events", ["ride_id"], unique=False)
    op.create_index("ix_vtc_ride_events_event_type", "vtc_ride_events", ["event_type"], unique=False)

    op.alter_column("vtc_driver_profiles", "is_online", server_default=None)
    op.alter_column("vtc_driver_profiles", "availability_status", server_default=None)
    op.alter_column("vtc_driver_profiles", "rides_completed_count", server_default=None)
    op.alter_column("vtc_driver_profiles", "rides_cancelled_count", server_default=None)
    op.alter_column("vtc_ride_requests", "dispatch_status", server_default=None)
    op.alter_column("vtc_ride_requests", "payout_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_vtc_ride_events_event_type", table_name="vtc_ride_events")
    op.drop_index("ix_vtc_ride_events_ride_id", table_name="vtc_ride_events")
    op.drop_table("vtc_ride_events")

    op.drop_index("ix_vtc_ride_dispatch_offers_status", table_name="vtc_ride_dispatch_offers")
    op.drop_index("ix_vtc_ride_dispatch_offers_driver_user_id", table_name="vtc_ride_dispatch_offers")
    op.drop_index("ix_vtc_ride_dispatch_offers_ride_id", table_name="vtc_ride_dispatch_offers")
    op.drop_table("vtc_ride_dispatch_offers")

    op.drop_constraint("fk_vtc_ride_requests_cancelled_by_user", "vtc_ride_requests", type_="foreignkey")
    op.drop_index("ix_vtc_ride_requests_cancelled_by_user_id", table_name="vtc_ride_requests")
    op.drop_index("ix_vtc_ride_requests_payout_status", table_name="vtc_ride_requests")
    op.drop_index("ix_vtc_ride_requests_dispatch_status", table_name="vtc_ride_requests")
    op.drop_index("ix_vtc_ride_requests_ride_code", table_name="vtc_ride_requests")
    op.drop_column("vtc_ride_requests", "last_driver_location_at")
    op.drop_column("vtc_ride_requests", "last_driver_heading")
    op.drop_column("vtc_ride_requests", "last_driver_longitude")
    op.drop_column("vtc_ride_requests", "last_driver_latitude")
    op.drop_column("vtc_ride_requests", "cancellation_reason")
    op.drop_column("vtc_ride_requests", "customer_note")
    op.drop_column("vtc_ride_requests", "payout_status")
    op.drop_column("vtc_ride_requests", "dispatch_status")
    op.drop_column("vtc_ride_requests", "driver_payout_amount")
    op.drop_column("vtc_ride_requests", "platform_fee_amount")
    op.drop_column("vtc_ride_requests", "surge_multiplier")
    op.drop_column("vtc_ride_requests", "time_fare_amount")
    op.drop_column("vtc_ride_requests", "distance_fare_amount")
    op.drop_column("vtc_ride_requests", "base_fare_amount")
    op.drop_column("vtc_ride_requests", "quoted_fare")
    op.drop_column("vtc_ride_requests", "driver_offer_expires_at")
    op.drop_column("vtc_ride_requests", "payout_completed_at")
    op.drop_column("vtc_ride_requests", "cancelled_at")
    op.drop_column("vtc_ride_requests", "completed_at")
    op.drop_column("vtc_ride_requests", "started_at")
    op.drop_column("vtc_ride_requests", "driver_arrived_at")
    op.drop_column("vtc_ride_requests", "driver_en_route_at")
    op.drop_column("vtc_ride_requests", "accepted_at")
    op.drop_column("vtc_ride_requests", "assigned_at")
    op.drop_column("vtc_ride_requests", "requested_at")
    op.drop_column("vtc_ride_requests", "ride_code")
    op.drop_column("vtc_ride_requests", "cancelled_by_user_id")

    op.drop_constraint("fk_vtc_driver_profiles_current_ride", "vtc_driver_profiles", type_="foreignkey")
    op.drop_index("ix_vtc_driver_profiles_availability_status", table_name="vtc_driver_profiles")
    op.drop_index("ix_vtc_driver_profiles_current_ride_id", table_name="vtc_driver_profiles")
    op.drop_column("vtc_driver_profiles", "rides_cancelled_count")
    op.drop_column("vtc_driver_profiles", "rides_completed_count")
    op.drop_column("vtc_driver_profiles", "last_location_at")
    op.drop_column("vtc_driver_profiles", "current_longitude")
    op.drop_column("vtc_driver_profiles", "current_latitude")
    op.drop_column("vtc_driver_profiles", "availability_status")
    op.drop_column("vtc_driver_profiles", "is_online")
    op.drop_column("vtc_driver_profiles", "current_ride_id")
