"""geography hierarchy foundation

Revision ID: 20260606_0044
Revises: 20260606_0043
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0044"
down_revision = "20260606_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("countries", sa.Column("continent_code", sa.String(length=8), nullable=True))
    op.add_column("countries", sa.Column("continent_name", sa.String(length=128), nullable=True))
    op.add_column("countries", sa.Column("primary_city_name", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_countries_continent_code"), "countries", ["continent_code"], unique=False)

    op.create_table(
        "continents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=False),
        sa.Column("name_fr", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("launch_status", sa.String(length=16), nullable=False, server_default="CONFIGURED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_continents_code"), "continents", ["code"], unique=False)

    op.create_table(
        "cities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("country_id", sa.String(length=36), nullable=False),
        sa.Column("continent_code", sa.String(length=8), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("launch_status", sa.String(length=16), nullable=False, server_default="CONFIGURED"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_id", "slug", name="uq_city_country_slug"),
    )
    op.create_index(op.f("ix_cities_code"), "cities", ["code"], unique=False)
    op.create_index(op.f("ix_cities_continent_code"), "cities", ["continent_code"], unique=False)
    op.create_index(op.f("ix_cities_country_id"), "cities", ["country_id"], unique=False)

    op.create_table(
        "service_zones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("country_id", sa.String(length=36), nullable=False),
        sa.Column("city_id", sa.String(length=36), nullable=False),
        sa.Column("continent_code", sa.String(length=8), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("zone_type", sa.String(length=32), nullable=False, server_default="radius"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("launch_status", sa.String(length=16), nullable=False, server_default="CONFIGURED"),
        sa.Column("center_latitude", sa.Float(), nullable=True),
        sa.Column("center_longitude", sa.Float(), nullable=True),
        sa.Column("radius_km", sa.Float(), nullable=True),
        sa.Column("coverage_json", sa.Text(), nullable=True),
        sa.Column("pricing_profile_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"]),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("city_id", "module_code", "slug", name="uq_service_zone_city_module_slug"),
    )
    op.create_index(op.f("ix_service_zones_city_id"), "service_zones", ["city_id"], unique=False)
    op.create_index(op.f("ix_service_zones_continent_code"), "service_zones", ["continent_code"], unique=False)
    op.create_index(op.f("ix_service_zones_country_id"), "service_zones", ["country_id"], unique=False)
    op.create_index(op.f("ix_service_zones_module_code"), "service_zones", ["module_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_service_zones_module_code"), table_name="service_zones")
    op.drop_index(op.f("ix_service_zones_country_id"), table_name="service_zones")
    op.drop_index(op.f("ix_service_zones_continent_code"), table_name="service_zones")
    op.drop_index(op.f("ix_service_zones_city_id"), table_name="service_zones")
    op.drop_table("service_zones")
    op.drop_index(op.f("ix_cities_country_id"), table_name="cities")
    op.drop_index(op.f("ix_cities_continent_code"), table_name="cities")
    op.drop_index(op.f("ix_cities_code"), table_name="cities")
    op.drop_table("cities")
    op.drop_index(op.f("ix_continents_code"), table_name="continents")
    op.drop_table("continents")
    op.drop_index(op.f("ix_countries_continent_code"), table_name="countries")
    op.drop_column("countries", "primary_city_name")
    op.drop_column("countries", "continent_name")
    op.drop_column("countries", "continent_code")
