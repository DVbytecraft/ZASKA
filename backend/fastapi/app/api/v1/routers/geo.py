from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_geo_hierarchy_service, get_maps_service
from app.core.responses import success_response
from app.services.geo_hierarchy_service import GeoHierarchyService
from app.services.maps_service import MapsService


router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/countries")
def list_geo_countries(
    query: str | None = Query(default=None),
    signup_only: bool = Query(default=False),
    active_only: bool = Query(default=False),
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
):
    return success_response(
        geo.search_countries(
            query=query,
            signup_only=signup_only,
            active_only=active_only,
        )
    )


@router.get("/cities")
def list_geo_cities(
    country_code: str | None = Query(default=None),
    query: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
):
    return success_response(
        geo.list_cities(
            country_code=country_code,
            query=query,
            active_only=active_only,
        )
    )


@router.get("/places/autocomplete")
def autocomplete_places(
    query: str = Query(min_length=2),
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    maps: MapsService = Depends(get_maps_service),
):
    return success_response(
        {
            "provider": maps.provider_status(),
            "results": maps.autocomplete_places(
                query=query,
                country_code=country_code,
                city_name=city_name,
                limit=limit,
            ),
        }
    )


@router.get("/places/geocode")
def geocode_place(
    address: str = Query(min_length=3),
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    maps: MapsService = Depends(get_maps_service),
):
    return success_response(
        {
            "provider": maps.provider_status(),
            "result": maps.geocode_address(
                address=address,
                country_code=country_code,
                city_name=city_name,
            ),
        }
    )
