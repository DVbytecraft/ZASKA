from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_CATALOG_PATH = Path(__file__).with_name("world_countries_timezones.raw.json")

_REGION_TO_CONTINENT = {
    "Africa": "AF",
    "Europe": "EU",
    "Americas": "NA",
    "Asia": "AS",
    "Oceania": "OC",
    "Antarctic": "AN",
}

_NAME_OVERRIDES_FR = {
    "CI": "Cote d'Ivoire",
    "TL": "Timor oriental",
    "US": "Etats-Unis",
}


def _normalize_phone_prefix(phone_code: str | None) -> str | None:
    if not phone_code:
        return None
    raw = str(phone_code).strip()
    if not raw:
        return None
    return raw if raw.startswith("+") else f"+{raw}"


def _first_timezone(entry: dict) -> str:
    timezones = entry.get("timezones") or []
    if timezones and isinstance(timezones[0], dict):
        return str(timezones[0].get("zoneName") or "UTC")
    return "UTC"


def _first_capital(entry: dict) -> str:
    capital = entry.get("capital")
    if isinstance(capital, list) and capital:
        return str(capital[0]).strip() or str(entry.get("name") or entry.get("iso2") or "").strip()
    if isinstance(capital, str) and capital.strip():
        return capital.strip()
    return str(entry.get("name") or entry.get("iso2") or "").strip()


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, object]]:
    rows = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    catalog: dict[str, dict[str, object]] = {}
    for row in rows:
        iso2 = str(row.get("iso2") or "").strip().upper()
        if len(iso2) != 2:
            continue
        translations = row.get("translations") or {}
        region_name = str(row.get("region") or "").strip()
        timezone_name = _first_timezone(row)
        capital_name = _first_capital(row)
        catalog[iso2] = {
            "iso_code": iso2,
            "name_en": str(row.get("name") or iso2).strip(),
            "name_fr": _NAME_OVERRIDES_FR.get(iso2) or str(translations.get("fr") or row.get("name") or iso2).strip(),
            "continent_code": _REGION_TO_CONTINENT.get(region_name, "OTHER"),
            "continent_name": region_name or "Other",
            "primary_city_name": capital_name,
            "currency_code": str(row.get("currency") or "").strip().upper() or None,
            "currency_symbol": str(row.get("currency_symbol") or "").strip() or None,
            "phone_prefix": _normalize_phone_prefix(row.get("phonecode")),
            "timezone": timezone_name,
            "latitude": float(row["latitude"]) if row.get("latitude") is not None else None,
            "longitude": float(row["longitude"]) if row.get("longitude") is not None else None,
            "emoji": str(row.get("emoji") or "").strip() or None,
        }
    return catalog


def get_country_reference(country_code: str) -> dict[str, object] | None:
    return _load_catalog().get(country_code.strip().upper())


def iter_country_references() -> list[dict[str, object]]:
    return [value for _, value in sorted(_load_catalog().items(), key=lambda item: item[0])]
