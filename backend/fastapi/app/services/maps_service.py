from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.geo_hierarchy_service import GeoHierarchyService


class MapsService:
    def __init__(self, db: Session):
        self.db = db
        self.geo = GeoHierarchyService(db)

    def provider_status(self) -> dict[str, Any]:
        provider = str(settings.maps_provider or "mock").strip().lower()
        key_present = False
        if provider == "google":
            key_present = bool(settings.google_maps_api_key.strip())
        elif provider == "mapbox":
            key_present = bool(settings.mapbox_api_key.strip())
        return {
            "provider": provider,
            "requestsEnabled": bool(settings.maps_requests_enabled),
            "externalReady": bool(settings.maps_requests_enabled and key_present),
            "fallbackEnabled": True,
        }

    def autocomplete_places(
        self,
        *,
        query: str,
        country_code: str | None = None,
        city_name: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        text = query.strip()
        if not text:
            return []
        status = self.provider_status()
        if status["externalReady"]:
            try:
                if status["provider"] == "google":
                    return self._google_autocomplete(text, country_code=country_code, city_name=city_name, limit=limit)
                if status["provider"] == "mapbox":
                    return self._mapbox_autocomplete(text, country_code=country_code, city_name=city_name, limit=limit)
            except Exception:
                pass
        return self._fallback_autocomplete(text, country_code=country_code, city_name=city_name, limit=limit)

    def geocode_address(
        self,
        *,
        address: str,
        country_code: str | None = None,
        city_name: str | None = None,
    ) -> dict[str, Any] | None:
        text = address.strip()
        if not text:
            return None
        status = self.provider_status()
        if status["externalReady"]:
            try:
                if status["provider"] == "google":
                    return self._google_geocode(text, country_code=country_code, city_name=city_name)
                if status["provider"] == "mapbox":
                    return self._mapbox_geocode(text, country_code=country_code, city_name=city_name)
            except Exception:
                pass
        suggestions = self._fallback_autocomplete(text, country_code=country_code, city_name=city_name, limit=1)
        return suggestions[0] if suggestions else None

    def _fallback_autocomplete(
        self,
        query: str,
        *,
        country_code: str | None,
        city_name: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        cities = self.geo.list_cities(country_code=country_code, query=query, active_only=True)
        for city in cities[:limit]:
            payload.append(
                {
                    "label": ", ".join(
                        part for part in [city["name"], city["country_code"]] if part
                    ),
                    "countryCode": city["country_code"],
                    "cityName": city["name"],
                    "latitude": city["latitude"],
                    "longitude": city["longitude"],
                    "source": "catalog",
                }
            )
        if payload:
            return payload[:limit]

        countries = self.geo.search_countries(query=query, active_only=True)
        for country in countries[:limit]:
            payload.append(
                {
                    "label": country["name_fr"] or country["name_en"],
                    "countryCode": country["code"],
                    "cityName": country["primary_city_name"],
                    "latitude": None,
                    "longitude": None,
                    "source": "catalog",
                }
            )
        return payload[:limit]

    def _google_autocomplete(
        self,
        query: str,
        *,
        country_code: str | None,
        city_name: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        params = {
            "input": " ".join(part for part in [query, city_name] if part),
            "key": settings.google_maps_api_key,
            "language": settings.maps_default_language,
            "types": "geocode",
        }
        if country_code:
            params["components"] = f"country:{country_code.lower()}"
        data = self._fetch_json(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json?" + urlencode(params)
        )
        predictions = data.get("predictions") or []
        return [
            {
                "label": item.get("description"),
                "placeId": item.get("place_id"),
                "countryCode": country_code.upper() if country_code else None,
                "cityName": city_name,
                "latitude": None,
                "longitude": None,
                "source": "google",
            }
            for item in predictions[:limit]
        ]

    def _google_geocode(
        self,
        address: str,
        *,
        country_code: str | None,
        city_name: str | None,
    ) -> dict[str, Any] | None:
        query = ", ".join(part for part in [address, city_name, country_code] if part)
        params = {
            "address": query,
            "key": settings.google_maps_api_key,
            "language": settings.maps_default_language,
        }
        data = self._fetch_json("https://maps.googleapis.com/maps/api/geocode/json?" + urlencode(params))
        results = data.get("results") or []
        if not results:
            return None
        item = results[0]
        location = ((item.get("geometry") or {}).get("location") or {})
        return {
            "label": item.get("formatted_address"),
            "countryCode": country_code.upper() if country_code else None,
            "cityName": city_name,
            "latitude": location.get("lat"),
            "longitude": location.get("lng"),
            "source": "google",
        }

    def _mapbox_autocomplete(
        self,
        query: str,
        *,
        country_code: str | None,
        city_name: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        params = {
            "access_token": settings.mapbox_api_key,
            "language": settings.maps_default_language,
            "limit": str(limit),
            "types": "address,place,locality,neighborhood",
        }
        if country_code:
            params["country"] = country_code.lower()
        text = ", ".join(part for part in [query, city_name] if part)
        url = (
            "https://api.mapbox.com/geocoding/v5/mapbox.places/"
            + quote_plus(text)
            + ".json?"
            + urlencode(params)
        )
        data = self._fetch_json(url)
        features = data.get("features") or []
        return [
            {
                "label": item.get("place_name"),
                "countryCode": country_code.upper() if country_code else None,
                "cityName": city_name,
                "latitude": (item.get("center") or [None, None])[1],
                "longitude": (item.get("center") or [None, None])[0],
                "source": "mapbox",
            }
            for item in features[:limit]
        ]

    def _mapbox_geocode(
        self,
        address: str,
        *,
        country_code: str | None,
        city_name: str | None,
    ) -> dict[str, Any] | None:
        suggestions = self._mapbox_autocomplete(
            address,
            country_code=country_code,
            city_name=city_name,
            limit=1,
        )
        return suggestions[0] if suggestions else None

    @staticmethod
    def _fetch_json(url: str) -> dict[str, Any]:
        req = Request(url, headers={"User-Agent": "ZASKA/1.0"})
        with urlopen(req, timeout=max(1, int(settings.maps_request_timeout_seconds))) as response:
            return json.loads(response.read().decode("utf-8"))
