from __future__ import annotations

from app.core.pricing_catalog import (
    CONTINENT_PRICING_PROFILES,
    COUNTRY_PRICING_PROFILES,
    build_continent_pricing_profile,
    build_country_pricing_profile,
)
from app.db.session import SessionLocal
from app.services.country_rollout_service import CountryRolloutService
from app.services.geo_hierarchy_service import GeoHierarchyService


def run_seed() -> None:
    db = SessionLocal()
    try:
        geo = GeoHierarchyService(db)
        geo.seed_catalog()

        for continent_code in CONTINENT_PRICING_PROFILES.keys():
            geo.upsert_continent_pricing_profile(
                continent_code=continent_code,
                pricing_profile=build_continent_pricing_profile(continent_code),
            )

        country_rollout = CountryRolloutService(db)
        for country_code in COUNTRY_PRICING_PROFILES.keys():
            country = country_rollout.ensure_country(country_code)
            hierarchy = geo.ensure_country_hierarchy(country.iso_code or country.name)
            geo.upsert_country_pricing_profile(
                country_code=country.iso_code or country.name,
                pricing_profile=build_country_pricing_profile(
                    country.iso_code or country.name,
                    hierarchy.get("continent_code"),
                ),
            )
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
