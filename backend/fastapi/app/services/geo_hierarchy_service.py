from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.world_country_catalog import get_country_reference
from app.models.geography import City, Continent, ServiceZone
from app.models.location_config import Country
from app.services.country_rollout_service import CountryRolloutService


def _uuid() -> str:
    return str(uuid.uuid4())


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "default"


_CONTINENTS = {
    "AF": {"name_en": "Africa", "name_fr": "Afrique"},
    "EU": {"name_en": "Europe", "name_fr": "Europe"},
    "NA": {"name_en": "North America", "name_fr": "Amérique du Nord"},
    "SA": {"name_en": "South America", "name_fr": "Amérique du Sud"},
    "AS": {"name_en": "Asia", "name_fr": "Asie"},
    "OC": {"name_en": "Oceania", "name_fr": "Océanie"},
    "AN": {"name_en": "Antarctica", "name_fr": "Antarctique"},
    "OTHER": {"name_en": "Other", "name_fr": "Autre"},
}

_COUNTRY_TO_CONTINENT: dict[str, str] = {
    "TG": "AF",
    "BJ": "AF",
    "GH": "AF",
    "NG": "AF",
    "CI": "AF",
    "SN": "AF",
    "BF": "AF",
    "ML": "AF",
    "NE": "AF",
    "CM": "AF",
    "KE": "AF",
    "RW": "AF",
    "UG": "AF",
    "TZ": "AF",
    "ZA": "AF",
    "FR": "EU",
    "ES": "EU",
    "EE": "EU",
    "BE": "EU",
    "DE": "EU",
    "IT": "EU",
    "PT": "EU",
    "NL": "EU",
    "GB": "EU",
    "US": "NA",
    "CA": "NA",
}

_CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "LOME": (6.1319, 1.2228),
    "COTONOU": (6.3703, 2.3912),
    "ACCRA": (5.6037, -0.1870),
    "LAGOS": (6.5244, 3.3792),
    "ABIDJAN": (5.3599, -4.0083),
    "DAKAR": (14.7167, -17.4677),
    "OUAGADOUGOU": (12.3714, -1.5197),
    "BAMAKO": (12.6392, -8.0029),
    "NIAMEY": (13.5116, 2.1254),
    "DOUALA": (4.0511, 9.7679),
    "NAIROBI": (-1.2921, 36.8219),
    "PARIS": (48.8566, 2.3522),
    "MADRID": (40.4168, -3.7038),
    "TALLINN": (59.4370, 24.7536),
    "BRUSSELS": (50.8503, 4.3517),
    "NEW YORK": (40.7128, -74.0060),
    "TORONTO": (43.6532, -79.3832),
}


class GeoHierarchyService:
    def __init__(self, db: Session):
        self.db = db

    def seed_catalog(self) -> None:
        changed = False
        existing = {
            row.code: row
            for row in self.db.execute(select(Continent)).scalars().all()
        }
        for code, config in _CONTINENTS.items():
            row = existing.get(code)
            if row is None:
                self.db.add(
                    Continent(
                        code=code,
                        name_en=config["name_en"],
                        name_fr=config["name_fr"],
                    )
                )
                changed = True
                continue
            if row.name_en != config["name_en"] or row.name_fr != config["name_fr"]:
                row.name_en = config["name_en"]
                row.name_fr = config["name_fr"]
                row.updated_at = datetime.now(timezone.utc)
                changed = True
        if changed:
            self.db.commit()

    def ensure_country_hierarchy(self, country_code: str) -> dict:
        self.seed_catalog()
        country = CountryRolloutService(self.db).ensure_country(country_code)
        continent_code = self.get_continent_code(country.iso_code or country.name)
        continent = self.db.execute(
            select(Continent).where(Continent.code == continent_code)
        ).scalars().one_or_none()

        changed = False
        if country.continent_code != continent_code:
            country.continent_code = continent_code
            changed = True
        continent_name = continent.name_en if continent else _CONTINENTS[continent_code]["name_en"]
        if country.continent_name != continent_name:
            country.continent_name = continent_name
            changed = True

        city_name = (country.primary_city_name or country.city or "").strip()
        if city_name:
            if country.primary_city_name != city_name:
                country.primary_city_name = city_name
                changed = True
            self._ensure_city(country, continent_code, city_name, is_primary=True)

        if changed:
            self.db.commit()
            self.db.refresh(country)

        return {
            "country_code": country.iso_code or country.name,
            "continent_code": country.continent_code,
            "continent_name": country.continent_name,
            "primary_city_name": country.primary_city_name,
        }

    def list_continents(self) -> list[dict]:
        self.seed_catalog()
        rows = self.db.execute(select(Continent).order_by(Continent.code.asc())).scalars().all()
        return [
            {
                "code": row.code,
                "name_en": row.name_en,
                "name_fr": row.name_fr,
                "pricing_profile": self._decode_json(row.pricing_profile_json),
                "is_active": bool(row.is_active),
                "launch_status": row.launch_status,
            }
            for row in rows
        ]

    def list_countries(self) -> list[dict]:
        countries = CountryRolloutService(self.db).list_countries()
        result: list[dict] = []
        for country in countries:
            geo = self.ensure_country_hierarchy(country.iso_code or country.name)
            result.append(
                {
                    "code": country.iso_code or country.name,
                    "name_en": country.display_name_en or country.name,
                    "name_fr": country.display_name_fr or country.display_name_en or country.name,
                    "continent_code": geo["continent_code"],
                    "continent_name": geo["continent_name"],
                    "primary_city_name": geo["primary_city_name"],
                    "pricing_profile": self._decode_json(country.pricing_profile_json),
                    "launch_status": country.launch_status,
                    "is_active": bool(country.is_active),
                }
            )
        return result

    def search_countries(
        self,
        *,
        query: str | None = None,
        signup_only: bool = False,
        active_only: bool = False,
    ) -> list[dict]:
        countries = (
            CountryRolloutService(self.db).list_signup_countries(query=query)
            if signup_only
            else CountryRolloutService(self.db).list_countries()
        )
        if query and not signup_only:
            term = query.strip().lower()
            countries = [
                country
                for country in countries
                if term in (country.name or "").lower()
                or term in (country.display_name_en or "").lower()
                or term in (country.display_name_fr or "").lower()
                or term in (country.iso_code or "").lower()
            ]
        if active_only:
            countries = [country for country in countries if country.is_active]
        return [
            {
                "code": country.iso_code or country.name,
                "name_en": country.display_name_en or country.name,
                "name_fr": country.display_name_fr or country.display_name_en or country.name,
                "continent_code": country.continent_code,
                "continent_name": country.continent_name,
                "primary_city_name": country.primary_city_name,
                "currency_code": country.currency_code,
                "currency_symbol": country.currency_symbol,
                "phone_prefix": country.phone_prefix,
                "timezone": country.timezone,
                "is_active": bool(country.is_active),
                "signup_enabled": bool(country.signup_enabled),
                "launch_status": country.launch_status,
            }
            for country in countries
        ]

    def list_cities(
        self,
        country_code: str | None = None,
        *,
        query: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        stmt = select(City)
        if country_code:
            country = CountryRolloutService(self.db).ensure_country(country_code)
            self.ensure_country_hierarchy(country.iso_code or country.name)
            stmt = stmt.where(City.country_id == country.id)
        if query:
            stmt = stmt.where(City.name.ilike(f"%{query.strip()}%"))
        if active_only:
            stmt = stmt.where(City.is_active.is_(True))
        rows = self.db.execute(stmt.order_by(City.continent_code.asc(), City.name.asc())).scalars().all()
        countries = {
            row.id: row
            for row in self.db.execute(select(Country)).scalars().all()
        }
        return [
            {
                "id": row.id,
                "country_code": countries[row.country_id].iso_code if row.country_id in countries else None,
                "continent_code": row.continent_code,
                "code": row.code,
                "name": row.name,
                "slug": row.slug,
                "timezone": row.timezone,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "is_active": bool(row.is_active),
                "launch_status": row.launch_status,
                "is_primary": bool(row.is_primary),
            }
            for row in rows
        ]

    def upsert_city(
        self,
        *,
        country_code: str,
        name: str,
        timezone_name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        is_primary: bool = False,
        is_active: bool = True,
        launch_status: str = "CONFIGURED",
    ) -> dict:
        country = CountryRolloutService(self.db).ensure_country(country_code)
        hierarchy = self.ensure_country_hierarchy(country.iso_code or country.name)
        row = self._ensure_city(
            country,
            hierarchy["continent_code"] or "OTHER",
            name,
            timezone_name=timezone_name,
            latitude=latitude,
            longitude=longitude,
            is_primary=is_primary,
            is_active=is_active,
            launch_status=launch_status,
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "id": row.id,
            "country_code": country.iso_code or country.name,
            "continent_code": row.continent_code,
            "code": row.code,
            "name": row.name,
            "slug": row.slug,
            "is_primary": bool(row.is_primary),
            "is_active": bool(row.is_active),
            "launch_status": row.launch_status,
        }

    def list_service_zones(
        self,
        *,
        module_code: str | None = None,
        country_code: str | None = None,
        city_code: str | None = None,
    ) -> list[dict]:
        stmt = select(ServiceZone)
        if module_code:
            stmt = stmt.where(ServiceZone.module_code == module_code.strip().upper())
        if country_code:
            country = CountryRolloutService(self.db).ensure_country(country_code)
            self.ensure_country_hierarchy(country.iso_code or country.name)
            stmt = stmt.where(ServiceZone.country_id == country.id)
        if city_code:
            city_ids = [
                row.id
                for row in self.db.execute(
                    select(City).where(City.code == city_code.strip().upper())
                ).scalars().all()
            ]
            if city_ids:
                stmt = stmt.where(ServiceZone.city_id.in_(city_ids))
        rows = self.db.execute(stmt.order_by(ServiceZone.module_code.asc(), ServiceZone.name.asc())).scalars().all()
        countries = {
            row.id: row
            for row in self.db.execute(select(Country)).scalars().all()
        }
        cities = {
            row.id: row
            for row in self.db.execute(select(City)).scalars().all()
        }
        return [
            {
                "id": row.id,
                "module_code": row.module_code,
                "country_code": countries[row.country_id].iso_code if row.country_id in countries else None,
                "city_code": cities[row.city_id].code if row.city_id in cities else None,
                "continent_code": row.continent_code,
                "code": row.code,
                "name": row.name,
                "slug": row.slug,
                "zone_type": row.zone_type,
                "is_active": bool(row.is_active),
                "launch_status": row.launch_status,
                "center_latitude": row.center_latitude,
                "center_longitude": row.center_longitude,
                "radius_km": row.radius_km,
                "coverage": self._decode_json(row.coverage_json),
                "pricing_profile": self._decode_json(row.pricing_profile_json),
            }
            for row in rows
        ]

    def upsert_service_zone(
        self,
        *,
        country_code: str,
        city_name: str,
        module_code: str,
        name: str,
        zone_type: str = "radius",
        is_active: bool = False,
        launch_status: str = "CONFIGURED",
        center_latitude: float | None = None,
        center_longitude: float | None = None,
        radius_km: float | None = None,
        coverage: dict | None = None,
        pricing_profile: dict | None = None,
    ) -> dict:
        country = CountryRolloutService(self.db).ensure_country(country_code)
        hierarchy = self.ensure_country_hierarchy(country.iso_code or country.name)
        city = self._ensure_city(country, hierarchy["continent_code"] or "OTHER", city_name)
        slug = _slugify(name)
        code = f"{(country.iso_code or country.name).upper()}-{city.code}-{module_code.strip().upper()}-{slug}".upper()[:64]

        row = self.db.execute(
            select(ServiceZone)
            .where(
                ServiceZone.city_id == city.id,
                ServiceZone.module_code == module_code.strip().upper(),
                ServiceZone.slug == slug,
            )
            .with_for_update()
        ).scalars().one_or_none()

        if row is None:
            row = ServiceZone(
                country_id=country.id,
                city_id=city.id,
                continent_code=city.continent_code,
                module_code=module_code.strip().upper(),
                code=code,
                name=name.strip(),
                slug=slug,
                zone_type=zone_type,
                is_active=is_active,
                launch_status=launch_status,
                center_latitude=center_latitude,
                center_longitude=center_longitude,
                radius_km=radius_km,
                coverage_json=json.dumps(coverage or {}, sort_keys=True),
                pricing_profile_json=json.dumps(pricing_profile or {}, sort_keys=True),
            )
            self.db.add(row)
        else:
            row.name = name.strip()
            row.zone_type = zone_type
            row.is_active = is_active
            row.launch_status = launch_status
            row.center_latitude = center_latitude
            row.center_longitude = center_longitude
            row.radius_km = radius_km
            row.coverage_json = json.dumps(coverage or {}, sort_keys=True)
            row.pricing_profile_json = json.dumps(pricing_profile or {}, sort_keys=True)
            row.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(row)
        return {
            "id": row.id,
            "module_code": row.module_code,
            "country_code": country.iso_code or country.name,
            "city_code": city.code,
            "continent_code": row.continent_code,
            "code": row.code,
            "name": row.name,
            "zone_type": row.zone_type,
            "is_active": bool(row.is_active),
            "launch_status": row.launch_status,
        }

    def resolve_country_geo(self, country_code: str) -> dict:
        country = CountryRolloutService(self.db).ensure_country(country_code)
        hierarchy = self.ensure_country_hierarchy(country.iso_code or country.name)
        cities = self.list_cities(country.iso_code or country.name)
        zones = self.list_service_zones(country_code=country.iso_code or country.name)
        return {
            "country_code": country.iso_code or country.name,
            "country_name": country.display_name_en or country.name,
            "continent_code": hierarchy["continent_code"],
            "continent_name": hierarchy["continent_name"],
            "primary_city_name": hierarchy["primary_city_name"],
            "pricing_profile": self._decode_json(country.pricing_profile_json),
            "cities": cities,
            "service_zones": zones,
        }

    def upsert_continent_pricing_profile(self, *, continent_code: str, pricing_profile: dict | None = None) -> dict:
        self.seed_catalog()
        code = continent_code.strip().upper()
        row = self.db.execute(select(Continent).where(Continent.code == code).with_for_update()).scalars().one_or_none()
        if row is None:
            raise ValueError("Continent introuvable")
        row.pricing_profile_json = json.dumps(pricing_profile or {}, sort_keys=True)
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return {
            "code": row.code,
            "name_en": row.name_en,
            "name_fr": row.name_fr,
            "pricing_profile": self._decode_json(row.pricing_profile_json),
        }

    def upsert_country_pricing_profile(self, *, country_code: str, pricing_profile: dict | None = None) -> dict:
        country = CountryRolloutService(self.db).ensure_country(country_code)
        self.ensure_country_hierarchy(country.iso_code or country.name)
        country.pricing_profile_json = json.dumps(pricing_profile or {}, sort_keys=True)
        self.db.commit()
        self.db.refresh(country)
        return {
            "code": country.iso_code or country.name,
            "name_en": country.display_name_en or country.name,
            "name_fr": country.display_name_fr or country.display_name_en or country.name,
            "continent_code": country.continent_code,
            "pricing_profile": self._decode_json(country.pricing_profile_json),
        }

    def get_continent_code(self, country_code: str) -> str:
        cc = country_code.strip().upper()
        reference = get_country_reference(cc)
        if reference and reference.get("continent_code"):
            return str(reference["continent_code"])
        return _COUNTRY_TO_CONTINENT.get(cc, "OTHER")

    def _ensure_city(
        self,
        country: Country,
        continent_code: str,
        name: str,
        *,
        timezone_name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        is_primary: bool = False,
        is_active: bool = True,
        launch_status: str = "CONFIGURED",
    ) -> City:
        clean_name = name.strip()
        slug = _slugify(clean_name)
        code = slug.replace("-", "_").upper()[:64]
        row = self.db.execute(
            select(City)
            .where(City.country_id == country.id, City.slug == slug)
            .with_for_update()
        ).scalars().one_or_none()
        default_coords = _CITY_COORDINATES.get(clean_name.upper())
        if default_coords is None and is_primary:
            reference = get_country_reference(country.iso_code or country.name)
            if reference and reference.get("latitude") is not None and reference.get("longitude") is not None:
                default_coords = (float(reference["latitude"]), float(reference["longitude"]))
        lat = latitude if latitude is not None else (default_coords[0] if default_coords else None)
        lng = longitude if longitude is not None else (default_coords[1] if default_coords else None)
        if row is None:
            row = City(
                id=_uuid(),
                country_id=country.id,
                continent_code=continent_code,
                code=code,
                name=clean_name,
                slug=slug,
                timezone=timezone_name or country.timezone,
                latitude=lat,
                longitude=lng,
                is_active=is_active,
                launch_status=launch_status,
                is_primary=is_primary,
            )
            self.db.add(row)
            self.db.flush()
        else:
            row.continent_code = continent_code
            row.code = code
            row.name = clean_name
            row.timezone = timezone_name or row.timezone or country.timezone
            row.latitude = lat if lat is not None else row.latitude
            row.longitude = lng if lng is not None else row.longitude
            row.is_active = is_active
            row.launch_status = launch_status
            row.updated_at = datetime.now(timezone.utc)
            if is_primary:
                row.is_primary = True

        if is_primary:
            self.db.execute(
                City.__table__.update()
                .where(City.country_id == country.id, City.id != row.id)
                .values(is_primary=False)
            )
            country.primary_city_name = clean_name
            country.city = clean_name

        return row

    @staticmethod
    def _decode_json(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
