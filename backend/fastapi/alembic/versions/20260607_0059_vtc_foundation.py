"""vtc foundation

Revision ID: 20260607_0059
Revises: 20260607_0058
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0059"
down_revision = "20260607_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vtc_fleet_operators",
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("accepting_rides", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("launch_status", sa.String(length=16), nullable=False, server_default="CONFIGURED"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_vtc_fleet_operators_owner"),
        sa.ForeignKeyConstraint(["service_zone_id"], ["service_zones.id"], name="fk_vtc_fleet_operators_service_zone"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vtc_fleet_operators_public_name", "vtc_fleet_operators", ["public_name"], unique=False)
    op.create_index("ix_vtc_fleet_operators_country_code", "vtc_fleet_operators", ["country_code"], unique=False)

    op.create_table(
        "vtc_driver_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("license_number", sa.String(length=64), nullable=True),
        sa.Column("license_country_code", sa.String(length=2), nullable=True),
        sa.Column("license_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vehicle_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["operator_id"], ["vtc_fleet_operators.id"], name="fk_vtc_driver_profiles_operator"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_vtc_driver_profiles_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vtc_driver_profiles_user_id", "vtc_driver_profiles", ["user_id"], unique=False)
    op.create_index("ix_vtc_driver_profiles_operator_id", "vtc_driver_profiles", ["operator_id"], unique=False)
    op.create_index("ix_vtc_driver_profiles_license_number", "vtc_driver_profiles", ["license_number"], unique=False)

    op.create_table(
        "vtc_vehicles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("driver_user_id", sa.String(length=36), nullable=True),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("plate_number", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False, server_default="standard"),
        sa.Column("seats_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["driver_user_id"], ["users.id"], name="fk_vtc_vehicles_driver"),
        sa.ForeignKeyConstraint(["operator_id"], ["vtc_fleet_operators.id"], name="fk_vtc_vehicles_operator"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vtc_vehicles_plate_number", "vtc_vehicles", ["plate_number"], unique=False)
    op.create_index("ix_vtc_vehicles_driver_user_id", "vtc_vehicles", ["driver_user_id"], unique=False)

    op.create_table(
        "vtc_ride_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_user_id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("driver_user_id", sa.String(length=36), nullable=True),
        sa.Column("linked_task_id", sa.String(length=36), nullable=True),
        sa.Column("pickup_address", sa.String(length=512), nullable=False),
        sa.Column("pickup_latitude", sa.Float(), nullable=True),
        sa.Column("pickup_longitude", sa.Float(), nullable=True),
        sa.Column("destination_address", sa.String(length=512), nullable=False),
        sa.Column("destination_latitude", sa.Float(), nullable=True),
        sa.Column("destination_longitude", sa.Float(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_distance_km", sa.Numeric(12, 3), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_fare", sa.Numeric(20, 6), nullable=True),
        sa.Column("final_fare", sa.Numeric(20, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("ride_type", sa.String(length=24), nullable=False, server_default="standard"),
        sa.Column("passenger_name", sa.String(length=160), nullable=True),
        sa.Column("passenger_phone", sa.String(length=32), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], name="fk_vtc_ride_requests_customer"),
        sa.ForeignKeyConstraint(["driver_user_id"], ["users.id"], name="fk_vtc_ride_requests_driver"),
        sa.ForeignKeyConstraint(["linked_task_id"], ["tasks.id"], name="fk_vtc_ride_requests_linked_task"),
        sa.ForeignKeyConstraint(["operator_id"], ["vtc_fleet_operators.id"], name="fk_vtc_ride_requests_operator"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vtc_ride_requests_customer_user_id", "vtc_ride_requests", ["customer_user_id"], unique=False)
    op.create_index("ix_vtc_ride_requests_operator_id", "vtc_ride_requests", ["operator_id"], unique=False)
    op.create_index("ix_vtc_ride_requests_driver_user_id", "vtc_ride_requests", ["driver_user_id"], unique=False)
    op.create_index("ix_vtc_ride_requests_status", "vtc_ride_requests", ["status"], unique=False)

    op.alter_column("vtc_fleet_operators", "is_active", server_default=None)
    op.alter_column("vtc_fleet_operators", "accepting_rides", server_default=None)
    op.alter_column("vtc_fleet_operators", "launch_status", server_default=None)
    op.alter_column("vtc_driver_profiles", "vehicle_ready", server_default=None)
    op.alter_column("vtc_driver_profiles", "is_active", server_default=None)
    op.alter_column("vtc_driver_profiles", "verification_status", server_default=None)
    op.alter_column("vtc_vehicles", "category", server_default=None)
    op.alter_column("vtc_vehicles", "is_active", server_default=None)
    op.alter_column("vtc_vehicles", "verification_status", server_default=None)
    op.alter_column("vtc_ride_requests", "status", server_default=None)
    op.alter_column("vtc_ride_requests", "ride_type", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_vtc_ride_requests_status", table_name="vtc_ride_requests")
    op.drop_index("ix_vtc_ride_requests_driver_user_id", table_name="vtc_ride_requests")
    op.drop_index("ix_vtc_ride_requests_operator_id", table_name="vtc_ride_requests")
    op.drop_index("ix_vtc_ride_requests_customer_user_id", table_name="vtc_ride_requests")
    op.drop_table("vtc_ride_requests")

    op.drop_index("ix_vtc_vehicles_driver_user_id", table_name="vtc_vehicles")
    op.drop_index("ix_vtc_vehicles_plate_number", table_name="vtc_vehicles")
    op.drop_table("vtc_vehicles")

    op.drop_index("ix_vtc_driver_profiles_license_number", table_name="vtc_driver_profiles")
    op.drop_index("ix_vtc_driver_profiles_operator_id", table_name="vtc_driver_profiles")
    op.drop_index("ix_vtc_driver_profiles_user_id", table_name="vtc_driver_profiles")
    op.drop_table("vtc_driver_profiles")

    op.drop_index("ix_vtc_fleet_operators_country_code", table_name="vtc_fleet_operators")
    op.drop_index("ix_vtc_fleet_operators_public_name", table_name="vtc_fleet_operators")
    op.drop_table("vtc_fleet_operators")
