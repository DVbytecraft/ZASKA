from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import (
    assert_admin_scope_access,
    filter_records_for_admin_scope,
    get_access_control_service,
    get_accounting_ledger_service,
    get_aml_service,
    get_b2b_service,
    get_db,
    get_dispute_service,
    get_food_service,
    get_geo_hierarchy_service,
    get_module_control_service,
    get_shop_service,
    get_subscription_service,
    get_vtc_service,
    get_wallet_service,
    require_admin,
    require_permission,
)
from app.core.config import settings
from app.core.country_engine.definitions import COUNTRY_REGISTRY as COUNTRY_CONFIGS
from app.core.fx_rate import get_live_fx_rate
from app.core.pricing_catalog import build_continent_pricing_profile, build_country_pricing_profile
from app.core.redis_client import redis_sync
from app.core.responses import success_response
from app.models.dispute import DisputeRecord, ReconciliationReport
from app.models.kyc import KycSubmission
from app.models.payout import Payout
from app.models.support_ticket import SupportTicket
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow, Transaction, Wallet
from app.payment.limits import TransactionLimits
from app.services.access_control_service import AccessControlService
from app.services.accounting_ledger_service import AccountingLedgerService
from app.services.aml_service import AmlService
from app.services.b2b_service import B2BService
from app.services.country_rollout_service import CountryRolloutService
from app.services.dispute_service import DisputeService
from app.services.food_service import FoodService
from app.services.geo_hierarchy_service import GeoHierarchyService
from app.services.module_control_service import ModuleControlService
from app.services.shop_service import ShopService
from app.services.social_protection_service import SocialProtectionService
from app.services.subscription_service import SubscriptionService
from app.services.vtc_service import VtcService
from app.services.wallet_service import InsufficientFundsError, WalletService

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Bootstrap: promote first admin (one-time, secret-protected) ──────────────

class BootstrapPayload(BaseModel):
    email: str
    secret: str


class StaffScopePayload(BaseModel):
    scope_type: str
    scope_value: str = "*"
    module_key: str = "*"
    can_read: bool = True
    can_write: bool = False


class StaffCreatePayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role_codes: list[str]
    scopes: list[StaffScopePayload] = []
    country_code: str | None = None
    phone: str | None = None


class StaffRolesUpdatePayload(BaseModel):
    role_codes: list[str]


class StaffScopesUpdatePayload(BaseModel):
    scopes: list[StaffScopePayload]


class ModuleSettingPayload(BaseModel):
    scope_type: str
    scope_value: str
    enabled: bool
    config: dict | None = None
    reason: str | None = None


class AdminCityPayload(BaseModel):
    country_code: str
    name: str
    timezone_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_primary: bool = False
    is_active: bool = True
    launch_status: str = "CONFIGURED"


class AdminServiceZonePayload(BaseModel):
    country_code: str
    city_name: str
    module_code: str
    name: str
    zone_type: str = "radius"
    is_active: bool = False
    launch_status: str = "CONFIGURED"
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_km: float | None = None
    coverage: dict | None = None
    pricing_profile: dict | None = None


class AdminPricingProfilePayload(BaseModel):
    pricing_profile: dict | None = None


class RestaurantUserCreatePayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    country_code: str
    phone: str | None = None


class AdminRestaurantPayload(BaseModel):
    public_name: str
    country_code: str
    city_name: str
    currency: str
    owner_user_id: str | None = None
    service_zone_id: str | None = None
    legal_name: str | None = None
    description: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    email: str | None = None
    accepts_cash_on_delivery: bool = False
    is_active: bool = True
    accepting_orders: bool = True
    is_temporarily_closed: bool = False
    prep_buffer_minutes: int = 0
    launch_status: str = "CONFIGURED"
    opening_hours: dict | None = None


class AdminRestaurantStaffPayload(BaseModel):
    user_id: str
    staff_role: str = "manager"
    is_primary: bool = False


class AdminRestaurantMenuPayload(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True
    is_default: bool = False


class AdminRestaurantMenuItemPayload(BaseModel):
    name: str
    price: str
    currency: str
    description: str | None = None
    category: str | None = None
    prep_minutes: int = 20
    is_available: bool = True
    is_sold_out: bool = False
    track_inventory: bool = False
    stock_quantity: int | None = None
    available_from_hour: str | None = None
    available_to_hour: str | None = None
    image_url: str | None = None


class AdminRestaurantOpsPayload(BaseModel):
    service_zone_id: str | None = None
    accepting_orders: bool | None = None
    is_temporarily_closed: bool | None = None
    prep_buffer_minutes: int | None = None
    opening_hours: dict | None = None


class AdminMenuItemOpsPayload(BaseModel):
    is_available: bool | None = None
    is_sold_out: bool | None = None
    track_inventory: bool | None = None
    stock_quantity: int | None = None
    available_from_hour: str | None = None
    available_to_hour: str | None = None


class AdminModifierGroupPayload(BaseModel):
    name: str
    is_required: bool = False
    min_select: int = 0
    max_select: int = 1
    is_active: bool = True


class AdminModifierOptionPayload(BaseModel):
    name: str
    currency: str
    price_delta: str = "0"
    is_default: bool = False
    is_active: bool = True


class AdminSpecialClosurePayload(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None
    is_active: bool = True


class AdminComboOfferPayload(BaseModel):
    name: str
    price: str
    currency: str
    description: str | None = None
    is_active: bool = True
    available_from_hour: str | None = None
    available_to_hour: str | None = None


class AdminComboItemPayload(BaseModel):
    menu_item_id: str
    quantity: int = 1


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _serialize_restaurant_admin(restaurant) -> dict[str, object]:
    return {
        "id": restaurant.id,
        "owner_user_id": restaurant.owner_user_id,
        "service_zone_id": restaurant.service_zone_id,
        "public_name": restaurant.public_name,
        "legal_name": restaurant.legal_name,
        "description": restaurant.description,
        "country_code": restaurant.country_code,
        "city_name": restaurant.city_name,
        "address": restaurant.address,
        "latitude": restaurant.latitude,
        "longitude": restaurant.longitude,
        "currency": restaurant.currency,
        "phone": restaurant.phone,
        "email": restaurant.email,
        "accepts_cash_on_delivery": bool(restaurant.accepts_cash_on_delivery),
        "is_active": bool(restaurant.is_active),
        "accepting_orders": bool(restaurant.accepting_orders),
        "is_temporarily_closed": bool(restaurant.is_temporarily_closed),
        "prep_buffer_minutes": restaurant.prep_buffer_minutes,
        "launch_status": restaurant.launch_status,
        "opening_hours": json.loads(restaurant.opening_hours_json) if restaurant.opening_hours_json else None,
        "created_at": restaurant.created_at.isoformat() if restaurant.created_at else None,
    }


def _serialize_menu_admin(menu) -> dict[str, object]:
    return {
        "id": menu.id,
        "restaurant_id": menu.restaurant_id,
        "name": menu.name,
        "description": menu.description,
        "is_active": bool(menu.is_active),
        "is_default": bool(menu.is_default),
        "created_at": menu.created_at.isoformat() if menu.created_at else None,
    }


def _serialize_menu_item_admin(item) -> dict[str, object]:
    return {
        "id": item.id,
        "menu_id": item.menu_id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "price": str(item.price),
        "currency": item.currency,
        "is_available": bool(item.is_available),
        "is_sold_out": bool(item.is_sold_out),
        "track_inventory": bool(item.track_inventory),
        "stock_quantity": item.stock_quantity,
        "prep_minutes": item.prep_minutes,
        "available_from_hour": item.available_from_hour,
        "available_to_hour": item.available_to_hour,
        "image_url": item.image_url,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_modifier_group_admin(group, options: list[object]) -> dict[str, object]:
    return {
        "id": group.id,
        "menu_item_id": group.menu_item_id,
        "name": group.name,
        "is_required": bool(group.is_required),
        "min_select": group.min_select,
        "max_select": group.max_select,
        "is_active": bool(group.is_active),
        "options": [
            {
                "id": option.id,
                "modifier_group_id": option.modifier_group_id,
                "name": option.name,
                "price_delta": str(option.price_delta),
                "currency": option.currency,
                "is_default": bool(option.is_default),
                "is_active": bool(option.is_active),
            }
            for option in options
        ],
    }


def _serialize_combo_offer_admin(combo, combo_items: list[object]) -> dict[str, object]:
    return {
        "id": combo.id,
        "restaurant_id": combo.restaurant_id,
        "name": combo.name,
        "description": combo.description,
        "price": str(combo.price),
        "currency": combo.currency,
        "is_active": bool(combo.is_active),
        "available_from_hour": combo.available_from_hour,
        "available_to_hour": combo.available_to_hour,
        "items": [
            {
                "id": item.id,
                "menu_item_id": item.menu_item_id,
                "quantity": item.quantity,
            }
            for item in combo_items
        ],
    }


@router.post("/bootstrap", include_in_schema=False)
def bootstrap_admin(payload: BootstrapPayload, db: Session = Depends(get_db)):
    """Promote a user to admin role using the ADMIN_BOOTSTRAP_SECRET.

    SECURITY RULES:
    1. Only works when ADMIN_BOOTSTRAP_SECRET is set in env.
    2. Refused if an admin already exists in the system (one-time operation).
    3. Audit-logged in Redis with timestamp and IP (if available).
    4. ADMIN_BOOTSTRAP_SECRET MUST be removed from env after first success.

    After calling this endpoint successfully:
      - Remove ADMIN_BOOTSTRAP_SECRET from your .env / Kubernetes secret.
      - The endpoint will return 403 on all subsequent calls (no secret = locked).
    """
    from app.core.observability import logger

    if not settings.admin_bootstrap_secret.strip():
        raise HTTPException(status_code=403, detail="Bootstrap not available — ADMIN_BOOTSTRAP_SECRET not set")

    # Constant-time comparison — prevents timing attacks on secret comparison
    import hmac as _hmac
    if not _hmac.compare_digest(
        payload.secret.encode(),
        settings.admin_bootstrap_secret.encode(),
    ):
        logger.warning("bootstrap_admin: invalid secret attempt for email={}", payload.email)
        raise HTTPException(status_code=403, detail="Invalid secret")

    # ONE-SHOT GUARD: refuse if any admin already exists.
    # This prevents the endpoint from being used to create a second admin
    # even while the secret is still set (e.g. operator forgot to remove it).
    existing_admin = db.execute(
        select(User).where(User.role == settings.admin_role).limit(1)
    ).scalars().one_or_none()
    if existing_admin is not None:
        logger.warning(
            "bootstrap_admin: blocked — admin already exists (email={}) attempted by {}",
            payload.email, existing_admin.email,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Bootstrap refused — an admin account already exists. "
                "Remove ADMIN_BOOTSTRAP_SECRET from your environment immediately."
            ),
        )

    user = db.execute(
        select(User).where(User.email == payload.email.strip().lower())
    ).scalars().one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = settings.admin_role
    db.commit()

    # Audit log in Redis — persistent for 90 days
    audit_key = f"audit:bootstrap:{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    redis_sync.setex(audit_key, 86400 * 90, f"admin_promoted:{user.email}")

    logger.warning(
        "BOOTSTRAP_ADMIN: user {} promoted to admin role. "
        "REMOVE ADMIN_BOOTSTRAP_SECRET FROM ENV NOW.",
        user.email,
    )

    return success_response({
        "promoted": user.email,
        "role": user.role,
        "action_required": "REMOVE ADMIN_BOOTSTRAP_SECRET from your environment immediately. "
                           "This endpoint is now permanently locked (one admin already exists).",
    })


@router.get("/access-control/catalog")
def access_control_catalog(
    svc: AccessControlService = Depends(get_access_control_service),
    _: str = Depends(require_permission("admin.staff.manage")),
):
    return success_response({"roles": svc.list_role_catalog()})


@router.get("/staff")
def list_staff_accounts(
    svc: AccessControlService = Depends(get_access_control_service),
    _: str = Depends(require_permission("admin.staff.manage")),
):
    return success_response(svc.list_staff_accounts())


@router.get("/modules/catalog")
def module_catalog(
    svc: ModuleControlService = Depends(get_module_control_service),
    _: str = Depends(require_permission("admin.modules.manage")),
):
    return success_response({"modules": svc.list_modules()})


@router.get("/modules/settings")
def list_module_settings(
    module_code: str | None = Query(default=None),
    scope_type: str | None = Query(default=None),
    scope_value: str | None = Query(default=None),
    svc: ModuleControlService = Depends(get_module_control_service),
    _: str = Depends(require_permission("admin.modules.manage")),
):
    return success_response(
        svc.list_settings(
            module_code=module_code,
            scope_type=scope_type,
            scope_value=scope_value,
        )
    )


@router.get("/modules/runtime/{country_code}")
def module_runtime_for_country(
    country_code: str,
    svc: ModuleControlService = Depends(get_module_control_service),
    _: str = Depends(require_permission("admin.modules.manage")),
):
    return success_response(svc.resolve_modules_for_country(country_code))


@router.put("/modules/{module_code}/settings")
def upsert_module_setting(
    module_code: str,
    payload: ModuleSettingPayload,
    svc: ModuleControlService = Depends(get_module_control_service),
    admin_id: str = Depends(require_permission("admin.modules.manage")),
):
    try:
        return success_response(
            svc.upsert_setting(
                module_code=module_code,
                scope_type=payload.scope_type,
                scope_value=payload.scope_value,
                enabled=payload.enabled,
                changed_by_user_id=admin_id,
                config=payload.config,
                reason=payload.reason,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/geo/continents")
def list_geo_continents(
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    return success_response(geo.list_continents())


@router.put("/geo/continents/{continent_code}/pricing")
def upsert_geo_continent_pricing(
    continent_code: str,
    payload: AdminPricingProfilePayload,
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    try:
        return success_response(
            geo.upsert_continent_pricing_profile(
                continent_code=continent_code,
                pricing_profile=payload.pricing_profile,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/geo/countries")
def list_geo_countries(
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    return success_response(geo.list_countries())


@router.get("/geo/countries/{country_code}")
def get_geo_country_runtime(
    country_code: str,
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    return success_response(geo.resolve_country_geo(country_code))


@router.put("/geo/countries/{country_code}/pricing")
def upsert_geo_country_pricing(
    country_code: str,
    payload: AdminPricingProfilePayload,
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    try:
        return success_response(
            geo.upsert_country_pricing_profile(
                country_code=country_code,
                pricing_profile=payload.pricing_profile,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pricing/templates/continents/{continent_code}")
def get_continent_pricing_template(
    continent_code: str,
    _: str = Depends(require_permission("admin.countries.manage")),
):
    return success_response(
        {
            "continent_code": continent_code.strip().upper(),
            "pricing_profile": build_continent_pricing_profile(continent_code),
        }
    )


@router.get("/pricing/templates/countries/{country_code}")
def get_country_pricing_template(
    country_code: str,
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    runtime = geo.resolve_country_geo(country_code)
    return success_response(
        {
            "country_code": country_code.strip().upper(),
            "continent_code": runtime.get("continent_code"),
            "pricing_profile": build_country_pricing_profile(country_code, runtime.get("continent_code")),
        }
    )


@router.get("/geo/cities")
def list_geo_cities(
    country_code: str | None = Query(default=None),
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    return success_response(geo.list_cities(country_code=country_code))


@router.put("/geo/cities")
def upsert_geo_city(
    payload: AdminCityPayload,
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    try:
        return success_response(
            geo.upsert_city(
                country_code=payload.country_code,
                name=payload.name,
                timezone_name=payload.timezone_name,
                latitude=payload.latitude,
                longitude=payload.longitude,
                is_primary=payload.is_primary,
                is_active=payload.is_active,
                launch_status=payload.launch_status,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/geo/service-zones")
def list_geo_service_zones(
    module_code: str | None = Query(default=None),
    country_code: str | None = Query(default=None),
    city_code: str | None = Query(default=None),
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    return success_response(
        geo.list_service_zones(
            module_code=module_code,
            country_code=country_code,
            city_code=city_code,
        )
    )


@router.put("/geo/service-zones")
def upsert_geo_service_zone(
    payload: AdminServiceZonePayload,
    geo: GeoHierarchyService = Depends(get_geo_hierarchy_service),
    _: str = Depends(require_permission("admin.countries.manage")),
):
    try:
        return success_response(
            geo.upsert_service_zone(
                country_code=payload.country_code,
                city_name=payload.city_name,
                module_code=payload.module_code,
                name=payload.name,
                zone_type=payload.zone_type,
                is_active=payload.is_active,
                launch_status=payload.launch_status,
                center_latitude=payload.center_latitude,
                center_longitude=payload.center_longitude,
                radius_km=payload.radius_km,
                coverage=payload.coverage,
                pricing_profile=payload.pricing_profile,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/food/restaurant-users")
def create_food_restaurant_user(
    payload: RestaurantUserCreatePayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        user = svc.create_restaurant_user(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            country_code=payload.country_code,
            phone=payload.phone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "country_code": user.country_code,
        }
    )


@router.get("/food/restaurants")
def list_food_restaurants_admin(
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    include_inactive: bool = Query(default=True),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    restaurants = svc.list_restaurants(
        country_code=country_code,
        city_name=city_name,
        include_inactive=include_inactive,
    )
    return success_response([_serialize_restaurant_admin(restaurant) for restaurant in restaurants])


@router.post("/food/restaurants")
def create_food_restaurant_admin(
    payload: AdminRestaurantPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        restaurant = svc.create_restaurant(
            public_name=payload.public_name,
            country_code=payload.country_code,
            city_name=payload.city_name,
            currency=payload.currency,
            owner_user_id=payload.owner_user_id,
            service_zone_id=payload.service_zone_id,
            legal_name=payload.legal_name,
            description=payload.description,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            phone=payload.phone,
            email=payload.email,
            accepts_cash_on_delivery=payload.accepts_cash_on_delivery,
            is_active=payload.is_active,
            accepting_orders=payload.accepting_orders,
            is_temporarily_closed=payload.is_temporarily_closed,
            prep_buffer_minutes=payload.prep_buffer_minutes,
            launch_status=payload.launch_status,
            opening_hours=payload.opening_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_restaurant_admin(restaurant))


@router.post("/food/restaurants/{restaurant_id}/staff")
def assign_food_restaurant_staff_admin(
    restaurant_id: str,
    payload: AdminRestaurantStaffPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        assignment = svc.assign_restaurant_staff(
            restaurant_id=restaurant_id,
            user_id=payload.user_id,
            staff_role=payload.staff_role,
            is_primary=payload.is_primary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        {
            "id": assignment.id,
            "restaurant_id": assignment.restaurant_id,
            "user_id": assignment.user_id,
            "staff_role": assignment.staff_role,
            "is_primary": bool(assignment.is_primary),
            "is_active": bool(assignment.is_active),
        }
    )


@router.patch("/food/restaurants/{restaurant_id}/operations")
def update_food_restaurant_operations_admin(
    restaurant_id: str,
    payload: AdminRestaurantOpsPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        restaurant = svc.update_restaurant_operations(
            restaurant_id=restaurant_id,
            service_zone_id=payload.service_zone_id,
            accepting_orders=payload.accepting_orders,
            is_temporarily_closed=payload.is_temporarily_closed,
            prep_buffer_minutes=payload.prep_buffer_minutes,
            opening_hours=payload.opening_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_restaurant_admin(restaurant))


@router.get("/food/restaurants/{restaurant_id}/menus")
def list_food_restaurant_menus_admin(
    restaurant_id: str,
    include_inactive: bool = Query(default=True),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    menus = svc.list_menus(restaurant_id, include_inactive=include_inactive)
    items = svc.list_menu_items(restaurant_id=restaurant_id, include_unavailable=include_inactive)
    return success_response(
        {
            "menus": [_serialize_menu_admin(menu) for menu in menus],
            "menu_items": [_serialize_menu_item_admin(item) for item in items],
        }
    )


@router.post("/food/restaurants/{restaurant_id}/menus")
def create_food_restaurant_menu_admin(
    restaurant_id: str,
    payload: AdminRestaurantMenuPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        menu = svc.create_menu(
            restaurant_id=restaurant_id,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
            is_default=payload.is_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_menu_admin(menu))


@router.post("/food/menus/{menu_id}/items")
def create_food_menu_item_admin(
    menu_id: str,
    payload: AdminRestaurantMenuItemPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        item = svc.create_menu_item(
            menu_id=menu_id,
            name=payload.name,
            price=Decimal(payload.price),
            currency=payload.currency,
            description=payload.description,
            category=payload.category,
            prep_minutes=payload.prep_minutes,
            is_available=payload.is_available,
            is_sold_out=payload.is_sold_out,
            track_inventory=payload.track_inventory,
            stock_quantity=payload.stock_quantity,
            available_from_hour=payload.available_from_hour,
            available_to_hour=payload.available_to_hour,
            image_url=payload.image_url,
        )
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_menu_item_admin(item))


@router.patch("/food/menu-items/{item_id}/operations")
def update_food_menu_item_operations_admin(
    item_id: str,
    payload: AdminMenuItemOpsPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        item = svc.update_menu_item_operations(
            item_id=item_id,
            is_available=payload.is_available,
            is_sold_out=payload.is_sold_out,
            track_inventory=payload.track_inventory,
            stock_quantity=payload.stock_quantity,
            available_from_hour=payload.available_from_hour,
            available_to_hour=payload.available_to_hour,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_menu_item_admin(item))


@router.get("/food/menu-items/{item_id}/modifiers")
def list_food_menu_item_modifiers_admin(
    item_id: str,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    groups = svc.list_modifier_groups(menu_item_id=item_id)
    return success_response(
        [
            _serialize_modifier_group_admin(group, svc.list_modifier_options(modifier_group_id=group.id))
            for group in groups
        ]
    )


@router.get("/food/restaurants/{restaurant_id}/closures")
def list_food_restaurant_closures_admin(
    restaurant_id: str,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    closures = svc.list_special_closures(restaurant_id=restaurant_id)
    return success_response(
        [
            {
                "id": closure.id,
                "restaurant_id": closure.restaurant_id,
                "reason": closure.reason,
                "starts_at": closure.starts_at.isoformat() if closure.starts_at else None,
                "ends_at": closure.ends_at.isoformat() if closure.ends_at else None,
                "is_active": bool(closure.is_active),
            }
            for closure in closures
        ]
    )


@router.post("/food/restaurants/{restaurant_id}/closures")
def create_food_restaurant_closure_admin(
    restaurant_id: str,
    payload: AdminSpecialClosurePayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        closure = svc.create_special_closure(
            restaurant_id=restaurant_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        {
            "id": closure.id,
            "restaurant_id": closure.restaurant_id,
            "reason": closure.reason,
            "starts_at": closure.starts_at.isoformat() if closure.starts_at else None,
            "ends_at": closure.ends_at.isoformat() if closure.ends_at else None,
            "is_active": bool(closure.is_active),
        }
    )


@router.post("/food/menu-items/{item_id}/modifier-groups")
def create_food_modifier_group_admin(
    item_id: str,
    payload: AdminModifierGroupPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        group = svc.create_modifier_group(
            menu_item_id=item_id,
            name=payload.name,
            is_required=payload.is_required,
            min_select=payload.min_select,
            max_select=payload.max_select,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_modifier_group_admin(group, []))


@router.get("/food/restaurants/{restaurant_id}/combos")
def list_food_combo_offers_admin(
    restaurant_id: str,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    combos = svc.list_combo_offers(restaurant_id=restaurant_id)
    return success_response(
        [
            _serialize_combo_offer_admin(combo, svc.list_combo_items(combo_offer_id=combo.id))
            for combo in combos
        ]
    )


@router.post("/food/restaurants/{restaurant_id}/combos")
def create_food_combo_offer_admin(
    restaurant_id: str,
    payload: AdminComboOfferPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        combo = svc.create_combo_offer(
            restaurant_id=restaurant_id,
            name=payload.name,
            price=Decimal(payload.price),
            currency=payload.currency,
            description=payload.description,
            is_active=payload.is_active,
            available_from_hour=payload.available_from_hour,
            available_to_hour=payload.available_to_hour,
        )
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(_serialize_combo_offer_admin(combo, []))


@router.post("/food/combos/{combo_id}/items")
def add_food_combo_item_admin(
    combo_id: str,
    payload: AdminComboItemPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        row = svc.add_combo_item(
            combo_offer_id=combo_id,
            menu_item_id=payload.menu_item_id,
            quantity=payload.quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        {
            "id": row.id,
            "combo_offer_id": row.combo_offer_id,
            "menu_item_id": row.menu_item_id,
            "quantity": row.quantity,
        }
    )


@router.post("/food/modifier-groups/{group_id}/options")
def create_food_modifier_option_admin(
    group_id: str,
    payload: AdminModifierOptionPayload,
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.manage")),
):
    try:
        option = svc.create_modifier_option(
            modifier_group_id=group_id,
            name=payload.name,
            currency=payload.currency,
            price_delta=Decimal(payload.price_delta),
            is_default=payload.is_default,
            is_active=payload.is_active,
        )
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        {
            "id": option.id,
            "modifier_group_id": option.modifier_group_id,
            "name": option.name,
            "price_delta": str(option.price_delta),
            "currency": option.currency,
            "is_default": bool(option.is_default),
            "is_active": bool(option.is_active),
        }
    )


@router.get("/food/orders")
def list_food_orders_admin(
    actor_user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    if actor_user_id:
        orders = svc.list_restaurant_orders(actor_user_id)
    else:
        from app.models.food import FoodOrder

        orders = db.execute(select(FoodOrder).order_by(FoodOrder.created_at.desc()).limit(500)).scalars().all()
    return success_response(
        [
            {
                "id": order.id,
                "customer_user_id": order.customer_user_id,
                "restaurant_id": order.restaurant_id,
                "status": order.status,
                "payment_status": order.payment_status,
                "currency": order.currency,
                "total_amount": str(order.total_amount),
                "delivery_amount": str(order.delivery_amount),
                "restaurant_amount": str(order.restaurant_amount),
                "country_code": order.country_code,
                "city_name": order.city_name,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
            for order in orders
        ]
    )


@router.post("/food/dispatch-candidates")
def list_food_dispatch_candidates_admin(
    latitude: float = Query(...),
    longitude: float = Query(...),
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    return success_response(
        svc.get_dispatch_candidates(
            tasker_latitude=latitude,
            tasker_longitude=longitude,
            country_code=country_code,
            city_name=city_name,
            limit=limit,
        )
    )


@router.post("/food/payout-snapshots")
def build_food_payout_snapshots_admin(
    period_key: str | None = Query(default=None),
    restaurant_id: str | None = Query(default=None),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    return success_response(
        svc.build_restaurant_payout_snapshots(
            period_key=period_key,
            restaurant_id=restaurant_id,
        )
    )


@router.get("/food/payout-snapshots")
def list_food_payout_snapshots_admin(
    period_key: str | None = Query(default=None),
    restaurant_id: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.food.read")),
):
    return success_response(
        svc.list_restaurant_payout_snapshots(
            period_key=period_key,
            restaurant_id=restaurant_id,
            currency=currency,
            limit=limit,
        )
    )


@router.post("/food/payout-snapshots/sync-ledger")
def sync_food_payout_snapshots_to_ledger_admin(
    period_key: str | None = Query(default=None),
    restaurant_id: str | None = Query(default=None),
    svc: FoodService = Depends(get_food_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    return success_response(
        svc.sync_payout_snapshots_to_accounting(
            period_key=period_key,
            restaurant_id=restaurant_id,
        )
    )


@router.get("/ledger/overview")
def get_ledger_overview(
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    return success_response(svc.get_ledger_overview())


@router.get("/ledger/accounts")
def list_ledger_accounts(
    currency: str | None = Query(default=None),
    code: str | None = Query(default=None),
    account_type: str | None = Query(default=None),
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    return success_response(
        svc.list_accounts(
            currency=currency,
            code=code,
            account_type=account_type,
        )
    )


@router.post("/ledger/ingest-wallet-mirror")
def ingest_ledger_wallet_mirror(
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    return success_response(svc.ingest_wallet_mirror_entries())


@router.post("/ledger/reconciliation-snapshots")
def create_ledger_reconciliation_snapshots(
    snapshot_date: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    try:
        parsed_date = _parse_iso_date(snapshot_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date invalide. Utilisez YYYY-MM-DD.") from exc
    return success_response(
        svc.create_reconciliation_snapshots(
            snapshot_date=parsed_date,
            currency=currency,
        )
    )


@router.get("/ledger/reconciliation-snapshots")
def list_ledger_reconciliation_snapshots(
    snapshot_date: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    try:
        parsed_date = _parse_iso_date(snapshot_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date invalide. Utilisez YYYY-MM-DD.") from exc
    return success_response(
        svc.list_reconciliation_snapshots(
            snapshot_date=parsed_date,
            currency=currency,
            limit=limit,
        )
    )


@router.post("/ledger/country-revenue-snapshots")
def create_country_revenue_snapshots(
    period_key: str | None = Query(default=None),
    country_code: str | None = Query(default=None),
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    return success_response(
        svc.build_country_revenue_snapshots(
            period_key=period_key,
            country_code=country_code,
        )
    )


@router.get("/ledger/country-revenue-snapshots")
def list_country_revenue_snapshots(
    period_key: str | None = Query(default=None),
    country_code: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
    svc: AccountingLedgerService = Depends(get_accounting_ledger_service),
    _: str = Depends(require_permission("admin.finance.read")),
):
    return success_response(
        svc.list_country_revenue_snapshots(
            period_key=period_key,
            country_code=country_code,
            currency=currency,
            limit=limit,
        )
    )


@router.post("/staff")
def create_staff_account(
    payload: StaffCreatePayload,
    svc: AccessControlService = Depends(get_access_control_service),
    admin_id: str = Depends(require_permission("admin.staff.manage")),
):
    try:
        user = svc.create_staff_account(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            created_by_user_id=admin_id,
            role_codes=payload.role_codes,
            scopes=[scope.model_dump() for scope in payload.scopes],
            country_code=payload.country_code,
            phone=payload.phone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(
        {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "admin_roles": svc.get_user_role_codes(user.id),
            "scopes": svc.get_user_scopes(user.id),
        }
    )


@router.put("/staff/{user_id}/roles")
def update_staff_roles(
    user_id: str,
    payload: StaffRolesUpdatePayload,
    db: Session = Depends(get_db),
    svc: AccessControlService = Depends(get_access_control_service),
    admin_id: str = Depends(require_permission("admin.staff.manage")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.role != settings.admin_role:
        user.role = "staff"
    try:
        role_codes = svc.replace_role_assignments(
            user_id=user_id,
            role_codes=payload.role_codes,
            granted_by_user_id=admin_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(user)
    return success_response({"user_id": user_id, "role": user.role, "admin_roles": role_codes})


@router.put("/staff/{user_id}/scopes")
def update_staff_scopes(
    user_id: str,
    payload: StaffScopesUpdatePayload,
    db: Session = Depends(get_db),
    svc: AccessControlService = Depends(get_access_control_service),
    admin_id: str = Depends(require_permission("admin.staff.manage")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    try:
        scopes = svc.replace_scopes(
            user_id=user_id,
            scopes=[scope.model_dump() for scope in payload.scopes],
            granted_by_user_id=admin_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response({"user_id": user_id, "scopes": scopes})


# ── Existing endpoints (preserved) ───────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from sqlalchemy import func as _func
    total_tasks = db.query(Task).count()
    open_tasks = db.query(Task).filter(Task.status == "OPEN").count()
    assigned_tasks = db.query(Task).filter(Task.status == "ASSIGNED").count()
    completed_tasks = db.query(Task).filter(Task.status == "COMPLETED").count()
    total_users = db.query(User).count()
    verified_users = db.query(User).filter(User.is_verified.is_(True)).count()

    # Total revenue = sum of completed escrow releases (credit transactions of type escrow_release)
    revenue_row = db.execute(
        select(
            _func.coalesce(_func.sum(Transaction.amount), Decimal("0")).label("revenue"),
            Wallet.currency.label("currency"),
        )
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.status == "completed",
            Transaction.type == "credit",
            Transaction.reference.like("escrow_release:%"),
        )
        .group_by(Wallet.currency)
        .order_by(desc(_func.sum(Transaction.amount)))
        .limit(1)
    ).first()

    total_revenue = str(revenue_row.revenue) if revenue_row else "0"
    revenue_currency = revenue_row.currency if revenue_row else "XOF"

    return success_response(
        {
            "total_tasks": total_tasks,
            "open_tasks": open_tasks,
            "assigned_tasks": assigned_tasks,
            "completed_tasks": completed_tasks,
            "total_users": total_users,
            "verified_users": verified_users,
            "total_revenue": total_revenue,
            "revenue_currency": revenue_currency,
        }
    )


@router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Résumé des métriques pour le tableau de bord admin."""
    from sqlalchemy import func as _func
    from app.models.dispute import DisputeRecord

    total_tasks = db.query(Task).count()
    open_tasks = db.query(Task).filter(Task.status == "OPEN").count()
    assigned_tasks = db.query(Task).filter(Task.status == "ASSIGNED").count()
    completed_tasks = db.query(Task).filter(Task.status == "COMPLETED").count()
    total_users = db.query(User).count()

    # Active users: users with at least one task or transaction in the last 24h
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    active_users_today = db.query(Task.created_by).filter(Task.created_at >= cutoff).distinct().count()

    # Total volume (completed escrow releases)
    revenue_row = db.execute(
        select(
            _func.coalesce(_func.sum(Transaction.amount), Decimal("0")).label("total"),
            Wallet.currency.label("currency"),
        )
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.status == "completed",
            Transaction.type == "credit",
            Transaction.reference.like("escrow_release:%"),
        )
        .group_by(Wallet.currency)
        .order_by(desc(_func.sum(Transaction.amount)))
        .limit(1)
    ).first()

    open_disputes = db.query(DisputeRecord).filter(
        DisputeRecord.status.in_(["open", "pending"])
    ).count()

    return success_response({
        "total_tasks": total_tasks,
        "open_tasks": open_tasks,
        "assigned_tasks": assigned_tasks,
        "completed_tasks": completed_tasks,
        "total_users": total_users,
        "active_users_today": active_users_today,
        "total_volume": str(revenue_row.total) if revenue_row else "0",
        "currency": revenue_row.currency if revenue_row else "XOF",
        "open_disputes": open_disputes,
    })


@router.get("/tasks/recent")
def get_recent_tasks(
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """20 dernières tâches toutes statuts confondus."""
    tasks = (
        db.query(Task)
        .order_by(Task.created_at.desc())
        .limit(limit)
        .all()
    )
    return success_response([
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "price": float(t.price),
            "currency": t.currency,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ])


@router.get("/analytics/summary")
def analytics_summary(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Aggregate analytics data: user growth, task funnel, revenue by month, geo distribution."""
    from sqlalchemy import func as _func, extract as _extract

    # User counts by role
    role_counts = db.execute(
        select(User.role, _func.count(User.id).label("count"))
        .group_by(User.role)
    ).all()
    users_by_role = {r.role: r.count for r in role_counts}

    # Tasks by status
    status_counts = db.execute(
        select(Task.status, _func.count(Task.id).label("count"))
        .group_by(Task.status)
    ).all()
    tasks_by_status = {s.status: s.count for s in status_counts}

    # Monthly revenue (last 6 months) — sum of escrow_release credits
    # Fetch raw rows and aggregate in Python for DB-agnostic compatibility
    revenue_rows = db.execute(
        select(
            Transaction.created_at,
            Transaction.amount,
            Wallet.currency,
        )
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.status == "completed",
            Transaction.type == "credit",
            Transaction.reference.like("escrow_release:%"),
        )
        .order_by(Transaction.created_at)
    ).all()

    # Aggregate by YYYY-MM
    _rev_by_month: dict[str, dict] = {}
    for row in revenue_rows:
        dt = row.created_at
        key = f"{dt.year}-{str(dt.month).zfill(2)}"
        if key not in _rev_by_month:
            _rev_by_month[key] = {"revenue": Decimal("0"), "count": 0, "currency": row.currency}
        _rev_by_month[key]["revenue"] += row.amount
        _rev_by_month[key]["count"] += 1

    monthly_revenue_list = [
        {
            "month": k,
            "revenue": str(v["revenue"]),
            "transactions": v["count"],
            "currency": v["currency"],
        }
        for k, v in sorted(_rev_by_month.items())[-6:]
    ]

    # Top countries by user count
    country_counts = db.execute(
        select(
            User.country_code.label("country"),
            _func.count(User.id).label("users"),
        )
        .where(User.country_code.isnot(None))
        .group_by(User.country_code)
        .order_by(desc(_func.count(User.id)))
        .limit(10)
    ).all()

    # KYC stats
    kyc_counts = db.execute(
        select(KycSubmission.status, _func.count(KycSubmission.id).label("count"))
        .group_by(KycSubmission.status)
    ).all()

    # Dispute stats
    dispute_counts = db.execute(
        select(DisputeRecord.status, _func.count(DisputeRecord.id).label("count"))
        .group_by(DisputeRecord.status)
    ).all()

    return success_response({
        "users_by_role": users_by_role,
        "tasks_by_status": tasks_by_status,
        "monthly_revenue": monthly_revenue_list,
        "top_countries": [
            {"country": r.country, "users": r.users}
            for r in country_counts
        ],
        "kyc_by_status": {r.status: r.count for r in kyc_counts},
        "disputes_by_status": {r.status: r.count for r in dispute_counts},
    })


@router.get("/tasks")
def list_all_tasks(
    status: str | None = Query(default=None, description="Filter by task status"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = select(Task).order_by(desc(Task.created_at)).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Task.status == status.upper())
    tasks = db.execute(stmt).scalars().all()
    return success_response(
        [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "price": str(t.price),
                "currency": t.currency,
                "status": t.status,
                "created_by": t.created_by,
                "assigned_to": t.assigned_to,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    )


class AdminTaskAssignPayload(BaseModel):
    tasker_id: str


class AdminTaskCancelPayload(BaseModel):
    reason: str = ""


@router.post("/tasks/{task_id}/assign")
def admin_force_assign_task(
    task_id: str,
    payload: AdminTaskAssignPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    """Force-assign a task to a specific tasker (admin override)."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    tasker = db.get(User, payload.tasker_id)
    if tasker is None:
        raise HTTPException(status_code=404, detail="Tasker introuvable")
    if task.status not in {"OPEN", "ASSIGNED"}:
        raise HTTPException(status_code=409, detail=f"Tâche ne peut pas être assignée (statut: {task.status})")
    task.assigned_to = payload.tasker_id
    task.status = "ASSIGNED"
    db.commit()
    db.refresh(task)
    return success_response({
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "assigned_by_admin": admin_id,
    })


@router.post("/tasks/{task_id}/cancel")
def admin_cancel_task(
    task_id: str,
    payload: AdminTaskCancelPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    """Cancel a task and refund escrow if funded (admin action)."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    if task.status == "COMPLETED":
        raise HTTPException(status_code=409, detail="Impossible d'annuler une tâche déjà complétée")

    # Refund any active escrow
    escrow = svc.get_escrow_by_task(task_id)
    escrow_refunded = False
    if escrow and escrow.status in {"pending", "funded", "hold"}:
        try:
            if escrow.status == "pending":
                svc.cancel_pending_escrow(escrow.id)
            else:
                svc.refund_escrow(escrow.id)
            escrow_refunded = True
        except Exception as e:
            raise HTTPException(status_code=409, detail=f"Impossible de rembourser l'escrow: {e}")

    task.status = "CANCELLED"
    db.commit()
    return success_response({
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "escrow_refunded": escrow_refunded,
        "cancelled_by_admin": admin_id,
        "reason": payload.reason,
    })


@router.get("/countries")
def list_countries(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    countries = CountryRolloutService(db).list_countries()
    return success_response(
        [
            {
                "code": country.iso_code or country.name,
                "name_en": country.display_name_en or country.name,
                "name_fr": country.display_name_fr or country.display_name_en or country.name,
                "currency": country.currency_code or "EUR",
                "mobile_money_enabled": bool(country.mobile_money_enabled),
                "payment_providers": json.loads(country.payment_providers_json or "[]"),
                "is_active": bool(country.is_active),
                "signup_enabled": bool(country.signup_enabled),
                "launch_status": country.launch_status,
                "food_delivery_enabled": bool(country.food_delivery_enabled),
                "food_delivery_escrow_minutes": country.food_delivery_escrow_minutes,
            }
            for country in countries
        ]
    )


class AdminCountryUpdatePayload(BaseModel):
    is_active: bool | None = None
    signup_enabled: bool | None = None
    launch_status: str | None = None
    food_delivery_enabled: bool | None = None
    food_delivery_escrow_minutes: int | None = None


@router.patch("/countries/{country_code}")
def update_country_rollout(
    country_code: str,
    payload: AdminCountryUpdatePayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    module_svc: ModuleControlService = Depends(get_module_control_service),
):
    country = CountryRolloutService(db).update_country(
        country_code=country_code,
        is_active=payload.is_active,
        signup_enabled=payload.signup_enabled,
        launch_status=payload.launch_status,
        food_delivery_enabled=payload.food_delivery_enabled,
        food_delivery_escrow_minutes=payload.food_delivery_escrow_minutes,
    )
    if payload.food_delivery_enabled is not None:
        module_svc.upsert_setting(
            module_code="FOOD",
            scope_type="country",
            scope_value=country_code,
            enabled=payload.food_delivery_enabled,
            changed_by_user_id=admin_id,
            config={"escrow_minutes": country.food_delivery_escrow_minutes},
            reason="country_rollout_sync",
        )
    return success_response(
        {
            "code": country.iso_code or country.name,
            "is_active": bool(country.is_active),
            "signup_enabled": bool(country.signup_enabled),
            "launch_status": country.launch_status,
            "food_delivery_enabled": bool(country.food_delivery_enabled),
            "food_delivery_escrow_minutes": country.food_delivery_escrow_minutes,
        }
    )


@router.get("/social-protection/overview")
def social_protection_overview(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    return success_response(SocialProtectionService(db).get_admin_overview())


@router.get("/accounting/overview")
def accounting_overview(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    return success_response(SocialProtectionService(db).get_accounting_overview())


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    return success_response(
        [
            {
                "id": u.id,
                "email": u.email,
                "phone": u.phone,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "full_name": u.full_name,
                "role": u.role,
                "is_verified": u.is_verified,
                "country_code": u.country_code,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    )


# ── Payout management ─────────────────────────────────────────────────────────

@router.get("/payouts")
def list_payouts(
    status: str | None = None,
    user_id_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = select(Payout).order_by(desc(Payout.created_at)).limit(min(limit, 200))
    if status:
        stmt = stmt.where(Payout.status == status)
    if user_id_filter:
        stmt = stmt.where(Payout.user_id == user_id_filter)
    payouts = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": p.id,
            "user_id": p.user_id,
            "amount": str(p.amount),
            "currency": p.currency,
            "provider": p.provider,
            "phone_number": p.phone_number[-4:].rjust(len(p.phone_number), "*"),
            "country_code": p.country_code,
            "status": p.status,
            "provider_tx_id": p.provider_tx_id,
            "failure_reason": p.failure_reason,
            "retry_count": p.retry_count,
            "admin_notes": p.admin_notes,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in payouts
    ])


class ResolvePayoutPayload(BaseModel):
    status: str       # "completed" | "failed"
    admin_notes: str = ""


@router.post("/payouts/{payout_id}/resolve")
def resolve_payout(
    payout_id: str,
    payload: ResolvePayoutPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    if payload.status not in {"completed", "failed"}:
        raise HTTPException(status_code=400, detail="status must be 'completed' or 'failed'")
    payout = db.get(Payout, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout introuvable")
    if payout.status == "completed":
        raise HTTPException(status_code=409, detail="Payout already completed")

    reconciled = False
    if payload.status == "completed" and payout.status == "failed":
        # The payout actually succeeded after all — undo the automatic rollback credit
        # (rollback credit is issued with reference "rollback:{payout.reference}")
        from app.models.wallet import Transaction as WalletTransaction, Wallet as WalletModel
        from app.services.wallet_service import InsufficientFundsError
        # Transaction has no user_id column — join through Wallet to filter by owner
        rollback_tx = (
            db.query(WalletTransaction)
            .join(WalletModel, WalletTransaction.wallet_id == WalletModel.id)
            .filter(
                WalletTransaction.reference == f"rollback:{payout.reference}",
                WalletModel.user_id == payout.user_id,
            )
            .one_or_none()
        )
        if rollback_tx is not None:
            try:
                svc.debit_wallet(
                    user_id=payout.user_id,
                    currency=payout.currency,
                    amount=payout.amount,
                    reference=f"admin_reconcile:{payout_id}",
                    provider="admin",
                    metadata={
                        "type": "payout_reconcile",
                        "payout_id": payout_id,
                        "admin_id": admin_user_id,
                        "rollback_tx_id": rollback_tx.id,
                    },
                )
                reconciled = True
            except InsufficientFundsError as exc:
                raise HTTPException(
                    status_code=402,
                    detail=f"Réconciliation impossible : solde insuffisant ({exc})",
                )

    payout.status = payload.status
    payout.admin_notes = payload.admin_notes or f"Manually resolved by admin {admin_user_id}"
    db.commit()
    return success_response({
        "payout_id": payout_id,
        "status": payout.status,
        "wallet_reconciled": reconciled,
    })


@router.post("/payouts/{payout_id}/retry")
def queue_payout_retry(
    payout_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    payout = db.get(Payout, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout introuvable")
    if payout.status == "completed":
        raise HTTPException(status_code=409, detail="Payout already completed")

    # Reset retry counter so admin override is not blocked by max_retries
    payout.retry_count = 0
    payout.status = "failed"
    db.commit()

    from app.workers.payout_worker import retry_payout
    result = retry_payout(payout_id)
    return success_response({"payout_id": payout_id, "result": result})


# ── KYC management ────────────────────────────────────────────────────────────

@router.get("/kyc")
def list_kyc(
    status: str | None = "pending",
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(KycSubmission)
        .order_by(desc(KycSubmission.created_at))
        .limit(min(limit, 200))
    )
    if status:
        stmt = stmt.where(KycSubmission.status == status)
    submissions = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": s.id,
            "user_id": s.user_id,
            "status": s.status,
            "submission_kind": getattr(s, "submission_kind", "full"),
            "id_document_url": s.id_document_url,
            "id_document_back_url": getattr(s, "id_document_back_url", None),
            "selfie_url": s.selfie_url,
            "biometric_selfie_url": getattr(s, "biometric_selfie_url", None),
            "biometric_status": getattr(s, "biometric_status", None),
            "ocr_status": getattr(s, "ocr_status", None),
            "id_document_type": getattr(s, "id_document_type", None),
            "id_document_number_masked": getattr(s, "id_document_number_masked", None),
            "document_country_code": getattr(s, "document_country_code", None),
            "criminal_record_url": getattr(s, "criminal_record_url", None),
            "criminal_record_status": getattr(s, "criminal_record_status", None),
            "criminal_record_risk_level": getattr(s, "criminal_record_risk_level", None),
            "reviewed_by": s.reviewed_by,
            "reviewer_note": s.reviewer_note,
            "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "is_expired": bool(s.is_expired),
            "created_at": s.created_at.isoformat(),
        }
        for s in submissions
    ])


class KYCDecisionPayload(BaseModel):
    reason: str = ""


@router.post("/kyc/{submission_id}/approve")
def approve_kyc(
    submission_id: str,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
):
    from app.services.kyc_service import KycService
    try:
        KycService(db).approve(submission_id, reviewer_id=admin_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success_response({"submission_id": submission_id, "status": "approved"})


@router.post("/kyc/{submission_id}/reject")
def reject_kyc(
    submission_id: str,
    payload: KYCDecisionPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
):
    from app.services.kyc_service import KycService
    try:
        KycService(db).reject(
            submission_id,
            reviewer_id=admin_user_id,
            note=payload.reason or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success_response({"submission_id": submission_id, "status": "rejected"})


# ── Fraud flags ───────────────────────────────────────────────────────────────

def _scan_redis_keys(pattern: str, count: int = 100) -> list[str]:
    """Scan Redis keys matching pattern using SCAN (non-blocking, O(1) per call)."""
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = redis_sync.scan(cursor, match=pattern, count=count)
        for k in batch:
            keys.append(k if isinstance(k, str) else k.decode())
        if cursor == 0:
            break
    return keys


@router.get("/fraud/flags")
def list_fraud_flags(
    _: str = Depends(require_admin),
):
    """Return currently flagged users: payout-blocked and rapid-cycle candidates."""
    payout_fail_keys = _scan_redis_keys("fraud:payout_fails:*")
    rapid_cycle_keys = _scan_redis_keys("fraud:last_deposit:*")

    payout_blocked = []
    for key in payout_fail_keys:
        raw = redis_sync.get(key)
        count = int(raw) if raw else 0
        if count >= settings.payout_fail_block_threshold:
            uid = key.split(":")[-1]
            payout_blocked.append({"user_id": uid, "consecutive_failures": count})

    rapid_cycle_candidates = []
    for key in rapid_cycle_keys:
        uid = key.split(":")[-1]
        rapid_cycle_candidates.append({"user_id": uid})

    return success_response({
        "payout_blocked": payout_blocked,
        "rapid_cycle_candidates": rapid_cycle_candidates,
    })


@router.delete("/fraud/flags/{user_id}")
def clear_fraud_flags(
    user_id: str,
    _: str = Depends(require_admin),
):
    """Admin: clear all fraud flags for a user (unblock payout + rapid-cycle)."""
    limits = TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))
    limits.clear_payout_failures(user_id=user_id)
    redis_sync.delete(f"fraud:last_deposit:{user_id}")
    return success_response({"user_id": user_id, "flags_cleared": True})


# ── Transaction reversal ──────────────────────────────────────────────────────

class ReversalPayload(BaseModel):
    reason: str


@router.post("/transactions/{transaction_id}/reverse")
def reverse_transaction(
    transaction_id: str,
    payload: ReversalPayload,
    db: Session = Depends(get_db),
    admin_user_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    from app.services.wallet_service import InsufficientFundsError
    try:
        rev_tx, dispute = svc.reverse_transaction(
            transaction_id=transaction_id,
            reason=payload.reason,
            admin_user_id=admin_user_id,
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return success_response({
        "reversal_tx_id": rev_tx.id,
        "dispute_id": dispute.id,
        "original_tx_id": transaction_id,
        "status": "reversed",
    })


# ── Disputes ─────────────────────────────────────────────────────────────────

@router.get("/disputes")
def list_disputes(
    status: str | None = "open",
    priority: str | None = None,
    limit: int = 50,
    svc: DisputeService = Depends(get_dispute_service),
    _: str = Depends(require_permission("admin.disputes.manage")),
):
    items = svc.list_disputes(
        admin_view=True,
        status=status,
        priority=priority,
        limit=limit,
    )
    order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda item: (order.get(item.get("priority", "medium"), 9), item.get("createdAt") or ""))
    return success_response(items)


class DisputeAssignPayload(BaseModel):
    agent_user_id: str


class DisputeNotePayload(BaseModel):
    note: str


class DisputeEscalationPayload(BaseModel):
    escalate_to_user_id: str | None = None
    note: str = ""

class DisputeResolutionPayload(BaseModel):
    resolution: str
    admin_notes: str = ""
    tasker_percent: int | None = None


@router.get("/disputes/{dispute_id}")
def get_dispute_detail(
    dispute_id: str,
    svc: DisputeService = Depends(get_dispute_service),
    _: str = Depends(require_permission("admin.disputes.manage")),
):
    try:
        return success_response(svc.get_dispute_detail(dispute_id=dispute_id, admin_view=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/disputes/{dispute_id}/assign")
def assign_dispute(
    dispute_id: str,
    payload: DisputeAssignPayload,
    admin_user_id: str = Depends(require_permission("admin.disputes.manage")),
    svc: DisputeService = Depends(get_dispute_service),
):
    try:
        return success_response(
            svc.assign_agent(
                dispute_id=dispute_id,
                agent_user_id=payload.agent_user_id,
                actor_user_id=admin_user_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/disputes/{dispute_id}/note")
def add_dispute_note(
    dispute_id: str,
    payload: DisputeNotePayload,
    admin_user_id: str = Depends(require_permission("admin.disputes.manage")),
    svc: DisputeService = Depends(get_dispute_service),
):
    try:
        return success_response(
            svc.add_note(
                dispute_id=dispute_id,
                note=payload.note,
                actor_user_id=admin_user_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/disputes/{dispute_id}/escalate")
def escalate_dispute(
    dispute_id: str,
    payload: DisputeEscalationPayload,
    admin_user_id: str = Depends(require_permission("admin.disputes.manage")),
    svc: DisputeService = Depends(get_dispute_service),
):
    try:
        return success_response(
            svc.escalate(
                dispute_id=dispute_id,
                actor_user_id=admin_user_id,
                escalate_to_user_id=payload.escalate_to_user_id,
                note=payload.note,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: str,
    payload: DisputeResolutionPayload,
    admin_user_id: str = Depends(require_permission("admin.disputes.manage")),
    svc: DisputeService = Depends(get_dispute_service),
):
    try:
        dispute = svc.decide(
            dispute_id=dispute_id,
            actor_user_id=admin_user_id,
            decision=payload.resolution,
            admin_notes=payload.admin_notes,
            tasker_percent=payload.tasker_percent,
        )
        return success_response(dispute)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ── Reconciliation reports ────────────────────────────────────────────────────

@router.get("/reconciliation/reports")
def list_reconciliation_reports(
    limit: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    reports = (
        db.execute(
            select(ReconciliationReport)
            .order_by(desc(ReconciliationReport.run_at))
            .limit(min(limit, 100))
        )
        .scalars()
        .all()
    )
    return success_response([
        {
            "id": r.id,
            "run_at": r.run_at.isoformat(),
            "country_code": r.country_code,
            "matched_count": r.matched_count,
            "missing_count": r.missing_count,
            "inconsistent_count": r.inconsistent_count,
            "repaired_count": r.repaired_count,
        }
        for r in reports
    ])


@router.get("/reconciliation/reports/{report_id}")
def get_reconciliation_report(
    report_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    import json as _json
    report = db.get(ReconciliationReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report introuvable")
    return success_response({
        "id": report.id,
        "run_at": report.run_at.isoformat(),
        "country_code": report.country_code,
        "matched_count": report.matched_count,
        "missing_count": report.missing_count,
        "inconsistent_count": report.inconsistent_count,
        "repaired_count": report.repaired_count,
        "details": _json.loads(report.report_json) if report.report_json else {},
    })


@router.post("/ledger/reconcile")
def ledger_reconcile(
    user_id: str | None = None,
    currency: str | None = None,
    dry_run: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """
    Ledger reconciliation — compare wallet.balance vs ledger-computed balance.

    The ledger (Transaction table) is the single source of truth.
    wallet.balance is a denormalized cache; any drift is corrected here.

    Query params:
      user_id + currency  → reconcile one specific wallet
      (none)              → reconcile all wallets
      dry_run=true        → report only, do not write corrections (default)
      dry_run=false       → apply corrections to wallet.balance
    """
    from app.services.wallet_service import LedgerDriftError

    wallet_svc = WalletService(db)
    drift_report = []

    if user_id and currency:
        wallets = (
            db.execute(
                select(Wallet).where(
                    Wallet.user_id == user_id,
                    Wallet.currency == currency.upper(),
                )
            )
            .scalars()
            .all()
        )
    else:
        wallets = db.execute(select(Wallet)).scalars().all()

    for wallet in wallets:
        computed = wallet_svc.recompute_balance_from_ledger(wallet.user_id, wallet.currency)
        diff = wallet.balance - computed
        if abs(diff) > Decimal("0.000001"):
            drift_report.append({
                "user_id": wallet.user_id,
                "currency": wallet.currency,
                "wallet_balance": str(wallet.balance),
                "ledger_computed": str(computed),
                "drift": str(diff),
                "corrected": not dry_run,
            })
            if not dry_run:
                wallet.balance = computed

    if not dry_run and drift_report:
        db.commit()

    return success_response({
        "wallets_checked": len(wallets),
        "drifts_found": len(drift_report),
        "drifts_corrected": len(drift_report) if not dry_run else 0,
        "dry_run": dry_run,
        "drift_report": drift_report,
    })


_FX_RATE_REDIS_KEY = "config:fx_usd_to_xof"


@router.get("/fx/rate")
def get_fx_rate(_: str = Depends(require_admin)):
    """Return the currently active USD→XOF FX rate (Redis override or config default)."""
    raw = redis_sync.get(_FX_RATE_REDIS_KEY)
    source = "redis_override" if raw else "config_default"
    rate = get_live_fx_rate()
    return success_response({
        "fx_usd_to_xof": str(rate),
        "source": source,
        "config_default": str(settings.fx_usd_to_xof),
    })


class FxRatePayload(BaseModel):
    rate: str   # Decimal string, e.g. "655.957"


@router.put("/fx/rate")
def set_fx_rate(
    payload: FxRatePayload,
    _: str = Depends(require_admin),
):
    """Override the live USD→XOF rate in Redis. Takes effect immediately on all new operations."""
    try:
        rate = Decimal(payload.rate)
    except Exception:
        raise HTTPException(status_code=400, detail="rate must be a valid decimal number")
    if rate <= Decimal("0") or rate > Decimal("10000"):
        raise HTTPException(status_code=400, detail="rate must be between 0 and 10000")
    redis_sync.set(_FX_RATE_REDIS_KEY, str(rate))
    return success_response({"fx_usd_to_xof": str(rate), "source": "redis_override"})


@router.delete("/fx/rate")
def reset_fx_rate(_: str = Depends(require_admin)):
    """Remove the Redis FX rate override — reverts to config default."""
    redis_sync.delete(_FX_RATE_REDIS_KEY)
    return success_response({
        "fx_usd_to_xof": str(settings.fx_usd_to_xof),
        "source": "config_default",
    })


# ── FX exposure ───────────────────────────────────────────────────────────────

@router.get("/fx/exposure")
def get_fx_exposure(
    _: str = Depends(require_admin),
):
    limits = TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))
    return success_response({
        **limits.get_fx_exposure(),
        "limit_usd": str(settings.fx_exposure_limit_usd),
    })


@router.delete("/fx/exposure/{direction}")
def reset_fx_exposure(
    direction: str,
    _: str = Depends(require_admin),
):
    if direction not in {"to_xof", "from_xof"}:
        raise HTTPException(
            status_code=400, detail="direction must be 'to_xof' or 'from_xof'"
        )
    limits = TransactionLimits(fx_rate_usd_to_xof=Decimal(str(settings.fx_usd_to_xof)))
    limits.reset_fx_exposure(direction=direction)
    return success_response({"direction": direction, "reset": True})


# ── Financial audit logs ──────────────────────────────────────────────────────

@router.get("/audit-logs")
def list_audit_logs(
    user_id_filter: str | None = None,
    action_filter: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Return immutable financial audit trail (most recent first)."""
    from app.models.audit_log import FinancialAuditLog
    stmt = (
        select(FinancialAuditLog)
        .order_by(desc(FinancialAuditLog.created_at))
        .limit(min(limit, 500))
        .offset(offset)
    )
    if user_id_filter:
        stmt = stmt.where(FinancialAuditLog.user_id == user_id_filter)
    if action_filter:
        stmt = stmt.where(FinancialAuditLog.action == action_filter)
    logs = db.execute(stmt).scalars().all()
    return success_response([
        {
            "id": lg.id,
            "action": lg.action,
            "user_id": lg.user_id,
            "payment_id": lg.payment_id,
            "transaction_id": lg.transaction_id,
            "amount": str(lg.amount),
            "currency": lg.currency,
            "provider": lg.provider,
            "status": lg.status,
            "country_code": lg.country_code,
            "created_at": lg.created_at.isoformat(),
        }
        for lg in logs
    ])


# ── Admin user detail & management ───────────────────────────────────────────

def _user_display_name(u: User) -> str:
    if u.full_name:
        return u.full_name
    parts = " ".join(filter(None, [u.first_name, u.last_name])).strip()
    return parts or u.email or u.phone or u.id[:8]


def _serialize_user_full(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "phone": u.phone,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "full_name": u.full_name,
        "role": u.role,
        "is_verified": u.is_verified,
        "is_suspended": getattr(u, "is_suspended", False),
        "is_locked": getattr(u, "is_locked", False),
        "ban_reason": getattr(u, "ban_reason", None),
        "suspension_reason": getattr(u, "suspension_reason", None),
        "country_code": u.country_code,
        "created_at": u.created_at.isoformat(),
    }


@router.get("/users/lookup")
def lookup_user_by_phone(
    phone: str = Query(..., description="Phone number to look up"),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Find a user by phone number (exact match)."""
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable pour ce numéro")

    # Wallet info
    wallets = db.query(Wallet).filter(Wallet.user_id == user.id).all()
    wallet_info = [
        {"currency": w.currency, "balance": str(w.balance)}
        for w in wallets
    ]

    # Recent transactions (5 most recent)
    recent_txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(desc(Transaction.created_at))
        .limit(5)
        .all()
    ) if hasattr(Transaction, "user_id") else []

    # Active tasks
    active_tasks = (
        db.query(Task)
        .filter(
            (Task.created_by == user.id) | (Task.assigned_to == user.id),
            Task.status.in_(["OPEN", "ASSIGNED"]),
        )
        .limit(5)
        .all()
    )

    data = _serialize_user_full(user)
    data["wallets"] = wallet_info
    data["wallet"] = wallet_info[0] if wallet_info else None
    data["recent_transactions"] = [
        {
            "id": tx.id,
            "type": tx.type,
            "amount": str(tx.amount),
            "currency": getattr(tx, "currency", "XOF"),
            "status": tx.status,
            "provider": tx.provider,
            "created_at": tx.created_at.isoformat(),
        }
        for tx in recent_txs
    ]
    data["active_tasks"] = [
        {"id": t.id, "title": t.title, "status": t.status, "price": str(t.price), "currency": t.currency}
        for t in active_tasks
    ]
    return success_response(data)


@router.get("/users/{user_id}")
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    wallets = db.query(Wallet).filter(Wallet.user_id == user_id).all()
    wallet_info = [{"currency": w.currency, "balance": str(w.balance)} for w in wallets]

    # Build a single wallet summary (first wallet with locked escrow sum)
    wallet_summary = None
    if wallet_info:
        locked = (
            db.query(Escrow)
            .filter(Escrow.payer_id == user_id, Escrow.status == "funded")
            .all()
        )
        locked_balance = sum(e.amount for e in locked)
        wallet_summary = {
            **wallet_info[0],
            "locked_balance": str(locked_balance),
        }

    recent_txs = []
    if wallets:
        wallet_ids = [w.id for w in wallets]
        recent_txs = (
            db.query(Transaction)
            .filter(Transaction.wallet_id.in_(wallet_ids))
            .order_by(desc(Transaction.created_at))
            .limit(5)
            .all()
        )

    active_tasks = (
        db.query(Task)
        .filter(
            (Task.created_by == user_id) | (Task.assigned_to == user_id),
            Task.status.in_(["OPEN", "ASSIGNED"]),
        )
        .limit(5)
        .all()
    )

    # KYC status
    kyc = (
        db.query(KycSubmission)
        .filter(KycSubmission.user_id == user_id)
        .order_by(desc(KycSubmission.created_at))
        .first()
    )

    data = _serialize_user_full(user)
    data["kyc_status"] = kyc.status if kyc else "not_submitted"
    data["wallet"] = wallet_summary
    data["recent_transactions"] = [
        {
            "id": tx.id,
            "type": tx.type,
            "amount": str(tx.amount),
            "currency": getattr(tx, "currency", "XOF"),
            "status": tx.status,
            "provider": tx.provider,
            "created_at": tx.created_at.isoformat(),
        }
        for tx in recent_txs
    ]
    data["active_tasks"] = [
        {"id": t.id, "title": t.title, "status": t.status, "price": str(t.price), "currency": t.currency}
        for t in active_tasks
    ]
    return success_response(data)


class UserActionPayload(BaseModel):
    reason: str = ""


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_suspended = True
    user.suspension_reason = payload.reason or f"Suspendu par admin {admin_id}"
    db.commit()
    return success_response({"user_id": user_id, "is_suspended": True})


@router.post("/users/{user_id}/unsuspend")
def unsuspend_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_suspended = False
    user.suspension_reason = None
    db.commit()
    return success_response({"user_id": user_id, "is_suspended": False})


@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_suspended = True
    user.ban_reason = payload.reason or f"Banni par admin {admin_id}"
    db.commit()
    return success_response({"user_id": user_id, "banned": True})


@router.post("/users/{user_id}/verify")
def verify_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_verified = True
    db.commit()
    return success_response({"user_id": user_id, "is_verified": True})


@router.post("/users/{user_id}/lock")
def lock_user(
    user_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_locked = True
    user.suspension_reason = payload.reason or f"Verrouillé par admin {admin_id}"
    db.commit()
    return success_response({"user_id": user_id, "is_locked": True})


@router.post("/users/{user_id}/unlock")
def unlock_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_locked = False
    db.commit()
    return success_response({"user_id": user_id, "is_locked": False})


# ── Admin transactions ────────────────────────────────────────────────────────

@router.get("/transactions")
def list_transactions(
    user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    import json as _json

    stmt = (
        select(Transaction, Wallet, User)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .join(User, Wallet.user_id == User.id)
        .order_by(desc(Transaction.created_at))
        .limit(limit)
    )
    if user_id:
        stmt = stmt.where(Wallet.user_id == user_id)
    if status:
        stmt = stmt.where(Transaction.status == status)
    rows = db.execute(stmt).all()

    def _business_type(tx: Transaction) -> str:
        """Extract business type from metadata_json, fallback to raw type."""
        if tx.metadata_json:
            try:
                meta = _json.loads(tx.metadata_json)
                if isinstance(meta, dict) and "type" in meta:
                    return meta["type"]
            except Exception:
                pass
        # Map raw types: credit → deposit (incoming), debit → withdrawal
        return "deposit" if tx.type == "credit" else "withdrawal"

    result = [
        {
            "id": tx.id,
            "user_id": wallet.user_id,
            "user_name": _user_display_name(user),
            "user_phone": user.phone,
            "type": _business_type(tx),
            "amount": str(tx.amount),
            "currency": wallet.currency,
            "status": tx.status,
            "provider": tx.provider,
            "reference": tx.reference,
            "created_at": tx.created_at.isoformat(),
        }
        for tx, wallet, user in rows
    ]
    # Optional: filter by business type after extraction
    if type:
        result = [r for r in result if r["type"] == type]
    return success_response(result)


@router.post("/transactions/{tx_id}/retry")
def retry_transaction(
    tx_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Alias: find the payout linked to this transaction and queue a retry."""
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    payout = db.query(Payout).filter(Payout.transaction_id == tx_id).one_or_none()
    if payout is None:
        raise HTTPException(status_code=404, detail="Aucun payout lié à cette transaction")
    if payout.status == "completed":
        raise HTTPException(status_code=409, detail="Payout déjà complété")
    payout.retry_count = 0
    payout.status = "failed"
    db.commit()
    from app.workers.payout_worker import retry_payout
    result = retry_payout(payout.id)
    return success_response({"tx_id": tx_id, "payout_id": payout.id, "result": result})


# ── Admin escrows ─────────────────────────────────────────────────────────────

@router.get("/escrows")
def list_escrows(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(Escrow, Task)
        .join(Task, Escrow.task_id == Task.id, isouter=True)
        .order_by(desc(Escrow.created_at))
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Escrow.status == status)
    rows = db.execute(stmt).all()

    def _get_user_name(uid: str | None) -> str | None:
        if not uid:
            return None
        u = db.get(User, uid)
        return _user_display_name(u) if u else None

    return success_response([
        {
            "escrow_id": esc.id,
            "task_id": esc.task_id,
            "task_title": task.title if task else None,
            "client_id": esc.payer_id,
            "client_name": _get_user_name(esc.payer_id),
            "tasker_id": esc.payee_id,
            "tasker_name": _get_user_name(esc.payee_id),
            "amount": str(esc.amount),
            "currency": esc.currency,
            "status": esc.status,
            "created_at": esc.created_at.isoformat(),
        }
        for esc, task in rows
    ])


@router.post("/escrows/{escrow_id}/release")
def admin_release_escrow(
    escrow_id: str,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        escrow = svc.release_escrow(escrow_id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return success_response({"escrow_id": escrow.id, "status": escrow.status, "released_by_admin": admin_id})


@router.post("/escrows/{escrow_id}/refund")
def admin_refund_escrow(
    escrow_id: str,
    payload: UserActionPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        escrow = svc.refund_escrow(escrow_id)
        svc.finalize_transaction(escrow.id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return success_response({"escrow_id": escrow.id, "status": escrow.status, "refunded_by_admin": admin_id})


# ── Admin wallet adjust ───────────────────────────────────────────────────────

class WalletAdjustPayload(BaseModel):
    user_id: str
    amount: str
    currency: str
    reason: str


@router.post("/wallet/adjust")
def admin_wallet_adjust(
    payload: WalletAdjustPayload,
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    try:
        amount = Decimal(payload.amount)
        if amount == 0:
            raise HTTPException(status_code=400, detail="Le montant ne peut pas être zéro")
        reference = f"admin_adjust:{payload.user_id}:{payload.currency}:{int(amount*100)}"
        if amount > 0:
            tx = svc.credit_wallet(
                user_id=payload.user_id,
                currency=payload.currency.upper(),
                amount=amount,
                reference=reference,
                provider="admin",
                metadata={"type": "adjustment", "reason": payload.reason, "admin_id": admin_id},
            )
        else:
            tx = svc.debit_wallet(
                user_id=payload.user_id,
                currency=payload.currency.upper(),
                amount=abs(amount),
                reference=reference,
                provider="admin",
                metadata={"type": "adjustment", "reason": payload.reason, "admin_id": admin_id},
            )
        return success_response({"tx_id": tx.id, "amount": str(amount), "currency": payload.currency})
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Payment providers status ──────────────────────────────────────────────────

@router.get("/providers")
def list_payment_providers(
    _: str = Depends(require_admin),
):
    """Return static provider status derived from country configs."""
    providers = []
    seen: set[str] = set()
    for cfg in COUNTRY_CONFIGS.values():
        for provider_name in (cfg.payment_providers or []):
            if provider_name in seen:
                continue
            seen.add(provider_name)
            providers.append({
                "id": provider_name,
                "name": provider_name.replace("_", " ").title(),
                "type": "mobile_money" if provider_name not in {"stripe"} else "card",
                "countries": [
                    c.country_code
                    for c in COUNTRY_CONFIGS.values()
                    if provider_name in (c.payment_providers or [])
                ],
                "status": "operational",
                "success_rate": 98.5,
            })
    return success_response(providers)


# ── Support tickets ───────────────────────────────────────────────────────────

class SupportTicketCreatePayload(BaseModel):
    user_id: str
    category: str = "other"
    priority: str = "medium"
    subject: str
    description: str


class SupportTicketUpdatePayload(BaseModel):
    notes: str | None = None
    status: str | None = None
    priority: str | None = None


class SupportTicketResolvePayload(BaseModel):
    notes: str = ""


class SupportRefundPayload(BaseModel):
    user_id: str
    amount: str
    currency: str
    reason: str
    ticket_id: str | None = None


def _serialize_ticket(t: SupportTicket, db: Session) -> dict:
    user = db.get(User, t.user_id)
    now = datetime.now(timezone.utc)
    wait_minutes = int((now - t.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60) if t.status == "open" else 0
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_name": _user_display_name(user) if user else t.user_id,
        "user_phone": user.phone if user else None,
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "subject": t.subject,
        "description": t.description,
        "notes": t.notes,
        "agent_id": t.agent_id,
        "wait_minutes": wait_minutes,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


@router.get("/support")
def list_support_tickets(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.is_deleted.is_(False))
        .order_by(desc(SupportTicket.created_at))
        .limit(limit)
    )
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    tickets = db.execute(stmt).scalars().all()
    return success_response([_serialize_ticket(t, db) for t in tickets])


@router.post("/support")
def create_support_ticket(
    payload: SupportTicketCreatePayload,
    db: Session = Depends(get_db),
    agent_id: str = Depends(require_admin),
):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    ticket = SupportTicket(
        user_id=payload.user_id,
        agent_id=agent_id,
        category=payload.category,
        priority=payload.priority,
        subject=payload.subject,
        description=payload.description,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.patch("/support/{ticket_id}")
def update_support_ticket(
    ticket_id: str,
    payload: SupportTicketUpdatePayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if payload.notes is not None:
        ticket.notes = payload.notes
    if payload.status is not None:
        ticket.status = payload.status
    if payload.priority is not None:
        ticket.priority = payload.priority
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.post("/support/{ticket_id}/resolve")
def resolve_support_ticket(
    ticket_id: str,
    payload: SupportTicketResolvePayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    ticket.status = "resolved"
    if payload.notes:
        ticket.notes = payload.notes
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.post("/support/{ticket_id}/escalate")
def escalate_support_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    ticket.status = "escalated"
    ticket.priority = "urgent"
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return success_response(_serialize_ticket(ticket, db))


@router.post("/support/refund")
def support_refund(
    payload: SupportRefundPayload,
    admin_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
):
    """Trigger a manual refund from the support desk."""
    try:
        amount = Decimal(payload.amount)
        reference = f"support_refund:{payload.user_id}:{payload.ticket_id or 'manual'}"
        tx = svc.credit_wallet(
            user_id=payload.user_id,
            currency=payload.currency.upper(),
            amount=amount,
            reference=reference,
            provider="admin",
            metadata={
                "type": "refund",
                "reason": payload.reason,
                "admin_id": admin_id,
                "ticket_id": payload.ticket_id,
            },
        )
        # Link ticket to resolved if ticket_id given
        if payload.ticket_id:
            ticket = db.get(SupportTicket, payload.ticket_id)
            if ticket:
                ticket.notes = (ticket.notes or "") + f"\nRemboursement {amount} {payload.currency} effectué."
                ticket.updated_at = datetime.now(timezone.utc)
                db.commit()
        return success_response({"tx_id": tx.id, "reference": reference, "amount": str(amount)})
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationPayload(BaseModel):
    user_id: str
    message: str
    channel: str  # "sms" | "push"


@router.post("/notifications/send")
def send_notification(
    payload: NotificationPayload,
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    """Send an SMS or push notification to a user."""
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    sent = False
    if payload.channel == "sms" and user.phone:
        try:
            from app.core.sms import send_sms
            send_sms(phone=user.phone, message=payload.message)
            sent = True
        except Exception:
            pass
    elif payload.channel == "push":
        from app.services.push_service import get_push_service
        push_svc = get_push_service()
        if user.fcm_token:
            sent = push_svc.send(
                fcm_token=user.fcm_token,
                title="Message de l'équipe ZASKA",
                body=payload.message,
                data={"admin_id": admin_id},
            )
        else:
            from app.core.observability import logger
            logger.info(
                "admin:push_notification_no_token user=%s admin=%s message=%s",
                payload.user_id, admin_id, payload.message[:100],
            )
            sent = False

    return success_response({
        "user_id": payload.user_id,
        "channel": payload.channel,
        "sent": sent,
        "note": "SMS envoyé" if (sent and payload.channel == "sms")
        else ("Push envoyé" if sent else "Token FCM manquant ou FCM non configuré"),
    })


class AdminSubscriptionPlanPayload(BaseModel):
    code: str
    name: str
    description: str | None = None
    subscription_type: str
    service_category: str | None = None
    price_monthly: Decimal
    currency: str = "EUR"
    tasks_included_monthly: int | None = None
    overage_price: Decimal | None = None
    priority_enabled: bool = False
    diaspora_included: bool = False
    support_priority: bool = False
    is_active: bool = True
    is_public: bool = True


class AdminSubscriptionPlanUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    subscription_type: str | None = None
    service_category: str | None = None
    price_monthly: Decimal | None = None
    currency: str | None = None
    tasks_included_monthly: int | None = None
    overage_price: Decimal | None = None
    priority_enabled: bool | None = None
    diaspora_included: bool | None = None
    support_priority: bool | None = None
    is_active: bool | None = None
    is_public: bool | None = None


class AdminAssignSubscriptionPayload(BaseModel):
    user_id: str
    plan_code: str
    auto_renew: bool = True


@router.get("/subscriptions/plans")
def admin_list_subscription_plans(
    service: SubscriptionService = Depends(get_subscription_service),
    _: str = Depends(require_permission("admin.subscriptions.read")),
):
    return success_response(service.list_all_plans())


@router.post("/subscriptions/plans")
def admin_create_subscription_plan(
    payload: AdminSubscriptionPlanPayload,
    service: SubscriptionService = Depends(get_subscription_service),
    _: str = Depends(require_permission("admin.subscriptions.manage")),
):
    try:
        return success_response(service.create_plan(payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/subscriptions/plans/{plan_id}")
def admin_update_subscription_plan(
    plan_id: str,
    payload: AdminSubscriptionPlanUpdatePayload,
    service: SubscriptionService = Depends(get_subscription_service),
    _: str = Depends(require_permission("admin.subscriptions.manage")),
):
    try:
        return success_response(service.update_plan(plan_id, payload.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/subscriptions/users")
def admin_list_user_subscriptions(
    status: str | None = Query(default=None),
    country_code: str | None = Query(default=None),
    service: SubscriptionService = Depends(get_subscription_service),
    _: str = Depends(require_permission("admin.subscriptions.read")),
):
    return success_response(service.list_all_user_subscriptions(status=status, country_code=country_code))


@router.post("/subscriptions/assign")
def admin_assign_subscription(
    payload: AdminAssignSubscriptionPayload,
    db: Session = Depends(get_db),
    service: SubscriptionService = Depends(get_subscription_service),
    _: str = Depends(require_permission("admin.subscriptions.manage")),
):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    try:
        return success_response(
            service.subscribe_user(
                user_id=payload.user_id,
                plan_code=payload.plan_code,
                country_code=user.country_code,
                source="admin",
                auto_renew=payload.auto_renew,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


class AdminAmlReviewPayload(BaseModel):
    decision: str
    notes: str = ""
    assign_to_user_id: str | None = None


class AdminB2BUserPayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    country_code: str | None = None
    phone: str | None = None


class AdminB2BOrganizationPayload(BaseModel):
    name: str
    legal_name: str | None = None
    registration_number: str | None = None
    country_code: str | None = None
    continent_code: str | None = None
    billing_mode: str = "monthly_invoice"
    metadata: dict | None = None


class AdminB2BMembershipPayload(BaseModel):
    user_id: str
    member_role: str = "manager"
    is_primary: bool = False


class AdminB2BContractPayload(BaseModel):
    organization_id: str
    plan_name: str
    monthly_task_quota: int | None = None
    overage_price: Decimal | None = None
    currency: str = "EUR"
    status: str = "active"
    start_date: datetime | None = None
    end_date: datetime | None = None
    terms: dict | None = None


class AdminB2BTemplatePayload(BaseModel):
    organization_id: str
    title: str
    description: str
    service_category: str = "TASK"
    default_price: Decimal
    currency: str = "EUR"
    city: str | None = None
    country_code: str | None = None
    is_active: bool = True
    template: dict | None = None


class AdminB2BWorkOrderPayload(BaseModel):
    organization_id: str
    requested_by_user_id: str
    template_id: str | None = None
    beneficiary_name: str | None = None
    beneficiary_phone: str | None = None
    scheduled_at: datetime | None = None
    price: Decimal
    currency: str = "EUR"
    notes: str | None = None
    assigned_tasker_id: str | None = None
    linked_task_id: str | None = None
    status: str = "draft"


class AdminExportGeneratePayload(BaseModel):
    report_type: str
    export_format: str = "csv"
    country_code: str | None = None
    continent_code: str | None = None
    filters: dict | None = None


class MerchantUserCreatePayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    country_code: str
    phone: str | None = None


class AdminMerchantPayload(BaseModel):
    public_name: str
    country_code: str
    city_name: str
    currency: str
    owner_user_id: str | None = None
    service_zone_id: str | None = None
    legal_name: str | None = None
    description: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    email: str | None = None
    accepts_cash_on_delivery: bool = False
    is_active: bool = True
    accepting_orders: bool = True
    launch_status: str = "CONFIGURED"
    metadata: dict | None = None


class AdminMerchantStaffPayload(BaseModel):
    user_id: str
    staff_role: str = "manager"
    is_primary: bool = False


class AdminMerchantCatalogPayload(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True
    is_default: bool = False


class AdminMerchantItemPayload(BaseModel):
    name: str
    price: str
    currency: str
    description: str | None = None
    category: str | None = None
    sku: str | None = None
    stock_quantity: int | None = None
    track_inventory: bool = False
    is_available: bool = True
    is_sold_out: bool = False
    image_url: str | None = None
    attributes: dict | None = None


class AdminShopOrderLinePayload(BaseModel):
    catalog_item_id: str
    quantity: int = Field(ge=1)


class AdminShopOrderPayload(BaseModel):
    merchant_id: str
    customer_user_id: str
    items: list[AdminShopOrderLinePayload]
    beneficiary_name: str | None = None
    beneficiary_phone: str | None = None
    ordered_for_other: bool = False
    delivery_address: str | None = None
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    delivery_amount: str | None = None
    notes: str | None = None
    customer_note: str | None = None
    metadata: dict | None = None


class AdminShopOrderStatusPayload(BaseModel):
    status: str
    note: str | None = None


class DriverUserCreatePayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    country_code: str
    phone: str | None = None


class AdminVtcOperatorPayload(BaseModel):
    public_name: str
    country_code: str
    city_name: str
    currency: str
    owner_user_id: str | None = None
    service_zone_id: str | None = None
    legal_name: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    accepting_rides: bool = True
    launch_status: str = "CONFIGURED"
    metadata: dict | None = None


class AdminVtcDriverProfilePayload(BaseModel):
    user_id: str
    operator_id: str | None = None
    license_number: str | None = None
    license_country_code: str | None = None
    license_expires_at: datetime | None = None
    vehicle_ready: bool = False
    is_active: bool = True
    verification_status: str = "pending"
    metadata: dict | None = None


class AdminVtcVehiclePayload(BaseModel):
    make: str
    model: str
    plate_number: str
    seats_count: int
    operator_id: str | None = None
    driver_user_id: str | None = None
    color: str | None = None
    category: str = "standard"
    is_active: bool = True
    verification_status: str = "pending"
    metadata: dict | None = None


class AdminVtcRidePayload(BaseModel):
    customer_user_id: str
    pickup_address: str
    destination_address: str
    currency: str
    operator_id: str | None = None
    driver_user_id: str | None = None
    linked_task_id: str | None = None
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    scheduled_at: datetime | None = None
    estimated_distance_km: Decimal | None = None
    estimated_duration_minutes: int | None = None
    estimated_fare: Decimal | None = None
    passenger_name: str | None = None
    passenger_phone: str | None = None
    ride_type: str = "standard"
    metadata: dict | None = None


@router.get("/aml/cases")
def admin_list_aml_cases(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    country_code: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=200),
    service: AmlService = Depends(get_aml_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = service.list_cases(
            status=status,
            severity=severity,
            country_code=country_code,
            user_id=user_id,
            limit=limit,
        )
    items = filter_records_for_admin_scope(
        records=items,
        user_id=admin_user_id,
        db=db,
        module_key="AML",
    )
    return success_response(items)


@router.get("/aml/cases/{case_id}")
def admin_get_aml_case(
    case_id: str,
    service: AmlService = Depends(get_aml_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        payload = service.get_case_detail(case_id)
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="AML",
            country_code=payload.get("countryCode"),
            write=False,
        )
        return success_response(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/aml/cases/{case_id}/review")
def admin_review_aml_case(
    case_id: str,
    payload: AdminAmlReviewPayload,
    admin_user_id: str = Depends(require_admin),
    service: AmlService = Depends(get_aml_service),
    db: Session = Depends(get_db),
):
    try:
        current = service.get_case_detail(case_id)
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="AML",
            country_code=current.get("countryCode"),
            write=True,
        )
        return success_response(
            service.review_case(
                case_id=case_id,
                admin_user_id=admin_user_id,
                decision=payload.decision,
                notes=payload.notes,
                assign_to_user_id=payload.assign_to_user_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/b2b/users")
def admin_create_b2b_user(
    payload: AdminB2BUserPayload,
    admin_user_id: str = Depends(require_admin),
    service: B2BService = Depends(get_b2b_service),
    db: Session = Depends(get_db),
):
    try:
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
            country_code=payload.country_code,
            write=True,
        )
        return success_response(
            service.create_business_user(
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
                country_code=payload.country_code,
                phone=payload.phone,
                created_by_user_id=admin_user_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/b2b/organizations")
def admin_create_b2b_organization(
    payload: AdminB2BOrganizationPayload,
    admin_user_id: str = Depends(require_admin),
    service: B2BService = Depends(get_b2b_service),
    db: Session = Depends(get_db),
):
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="B2B",
        country_code=payload.country_code,
        continent_code=payload.continent_code,
        write=True,
    )
    return success_response(
        service.create_organization(
            name=payload.name,
            legal_name=payload.legal_name,
            registration_number=payload.registration_number,
            country_code=payload.country_code,
            continent_code=payload.continent_code,
            billing_mode=payload.billing_mode,
            created_by_user_id=admin_user_id,
            metadata=payload.metadata,
        )
    )


@router.get("/b2b/organizations")
def admin_list_b2b_organizations(
    country_code: str | None = Query(default=None),
    continent_code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = service.list_organizations(
            country_code=country_code,
            continent_code=continent_code,
            status=status,
        )
    items = filter_records_for_admin_scope(
        records=items,
        user_id=admin_user_id,
        db=db,
        module_key="B2B",
    )
    return success_response(items)


@router.post("/b2b/organizations/{organization_id}/members")
def admin_add_b2b_membership(
    organization_id: str,
    payload: AdminB2BMembershipPayload,
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        organization = next((item for item in service.list_organizations() if item["id"] == organization_id), None)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
            country_code=organization.get("countryCode"),
            continent_code=organization.get("continentCode"),
            write=True,
        )
        return success_response(
            service.add_membership(
                organization_id=organization_id,
                user_id=payload.user_id,
                member_role=payload.member_role,
                is_primary=payload.is_primary,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/b2b/contracts")
def admin_create_b2b_contract(
    payload: AdminB2BContractPayload,
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        organization = next((item for item in service.list_organizations() if item["id"] == payload.organization_id), None)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
            country_code=organization.get("countryCode"),
            continent_code=organization.get("continentCode"),
            write=True,
        )
        return success_response(
            service.create_contract(
                organization_id=payload.organization_id,
                plan_name=payload.plan_name,
                monthly_task_quota=payload.monthly_task_quota,
                overage_price=payload.overage_price,
                currency=payload.currency,
                status=payload.status,
                start_date=payload.start_date,
                end_date=payload.end_date,
                terms=payload.terms,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/b2b/contracts")
def admin_list_b2b_contracts(
    organization_id: str | None = Query(default=None),
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = service.list_contracts(organization_id)
    org_map = {item["id"]: item for item in service.list_organizations()}
    scoped = []
    for item in items:
        organization = org_map.get(item["organizationId"])
        if organization is None:
            continue
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": organization.get("countryCode"), "continentCode": organization.get("continentCode")}],
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/b2b/templates")
def admin_create_b2b_template(
    payload: AdminB2BTemplatePayload,
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        organization = next((item for item in service.list_organizations() if item["id"] == payload.organization_id), None)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
            country_code=organization.get("countryCode") or payload.country_code,
            continent_code=organization.get("continentCode"),
            write=True,
        )
        return success_response(
            service.create_template(
                organization_id=payload.organization_id,
                title=payload.title,
                description=payload.description,
                service_category=payload.service_category,
                default_price=payload.default_price,
                currency=payload.currency,
                city=payload.city,
                country_code=payload.country_code,
                is_active=payload.is_active,
                template=payload.template,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/b2b/templates")
def admin_list_b2b_templates(
    organization_id: str | None = Query(default=None),
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = service.list_templates(organization_id)
    org_map = {item["id"]: item for item in service.list_organizations()}
    scoped = []
    for item in items:
        organization = org_map.get(item["organizationId"])
        if organization is None:
            continue
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": organization.get("countryCode"), "continentCode": organization.get("continentCode")}],
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/b2b/orders")
def admin_create_b2b_order(
    payload: AdminB2BWorkOrderPayload,
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        organization = next((item for item in service.list_organizations() if item["id"] == payload.organization_id), None)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
            country_code=organization.get("countryCode"),
            continent_code=organization.get("continentCode"),
            write=True,
        )
        return success_response(
            service.create_work_order(
                organization_id=payload.organization_id,
                requested_by_user_id=payload.requested_by_user_id,
                template_id=payload.template_id,
                beneficiary_name=payload.beneficiary_name,
                beneficiary_phone=payload.beneficiary_phone,
                scheduled_at=payload.scheduled_at,
                price=payload.price,
                currency=payload.currency,
                notes=payload.notes,
                assigned_tasker_id=payload.assigned_tasker_id,
                linked_task_id=payload.linked_task_id,
                status=payload.status,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/b2b/orders")
def admin_list_b2b_orders(
    organization_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = service.list_work_orders(organization_id=organization_id, status=status)
    org_map = {item["id"]: item for item in service.list_organizations()}
    scoped = []
    for item in items:
        organization = org_map.get(item["organizationId"])
        if organization is None:
            continue
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": organization.get("countryCode"), "continentCode": organization.get("continentCode")}],
            user_id=admin_user_id,
            db=db,
            module_key="B2B",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/exports/generate")
def admin_generate_export(
    payload: AdminExportGeneratePayload,
    admin_user_id: str = Depends(require_admin),
    service: B2BService = Depends(get_b2b_service),
    db: Session = Depends(get_db),
):
    try:
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="EXPORTS",
            country_code=payload.country_code,
            continent_code=payload.continent_code,
            write=True,
        )
        return success_response(
            service.generate_export(
                requested_by_user_id=admin_user_id,
                report_type=payload.report_type,
                export_format=payload.export_format,
                country_code=payload.country_code,
                continent_code=payload.continent_code,
                filters=payload.filters,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/exports")
def admin_list_exports(
    report_type: str | None = Query(default=None),
    requested_by_user_id: str | None = Query(default=None),
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = service.list_export_jobs(report_type=report_type, requested_by_user_id=requested_by_user_id)
    items = filter_records_for_admin_scope(
        records=items,
        user_id=admin_user_id,
        db=db,
        module_key="EXPORTS",
    )
    return success_response(items)


@router.get("/exports/{export_job_id}")
def admin_get_export(
    export_job_id: str,
    service: B2BService = Depends(get_b2b_service),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        payload = service.get_export_job(export_job_id)
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="EXPORTS",
            country_code=payload.get("countryCode"),
            continent_code=payload.get("continentCode"),
            write=False,
        )
        return success_response(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/shop/merchant-users")
def admin_create_shop_merchant_user(
    payload: MerchantUserCreatePayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=payload.country_code,
        write=True,
    )
    try:
        return success_response(
            service.create_merchant_user(
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
                country_code=payload.country_code,
                phone=payload.phone,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/shop/merchants")
def admin_create_shop_merchant(
    payload: AdminMerchantPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=payload.country_code,
        write=True,
    )
    return success_response(
        service.create_merchant(
            public_name=payload.public_name,
            country_code=payload.country_code,
            city_name=payload.city_name,
            currency=payload.currency,
            owner_user_id=payload.owner_user_id,
            service_zone_id=payload.service_zone_id,
            legal_name=payload.legal_name,
            description=payload.description,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            phone=payload.phone,
            email=payload.email,
            accepts_cash_on_delivery=payload.accepts_cash_on_delivery,
            is_active=payload.is_active,
            accepting_orders=payload.accepting_orders,
            launch_status=payload.launch_status,
            metadata=payload.metadata,
        )
    )


@router.get("/shop/merchants")
def admin_list_shop_merchants(
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    items = service.list_merchants(
        country_code=country_code,
        city_name=city_name,
        active_only=active_only,
    )
    items = filter_records_for_admin_scope(
        records=items,
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
    )
    return success_response(items)


@router.post("/shop/merchants/{merchant_id}/staff")
def admin_add_shop_merchant_staff(
    merchant_id: str,
    payload: AdminMerchantStaffPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    merchant = next((item for item in service.list_merchants() if item["id"] == merchant_id), None)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Marchand introuvable")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode"),
        write=True,
    )
    try:
        return success_response(
            service.add_staff(
                merchant_id=merchant_id,
                user_id=payload.user_id,
                staff_role=payload.staff_role,
                is_primary=payload.is_primary,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/shop/merchants/{merchant_id}/catalogs")
def admin_create_shop_catalog(
    merchant_id: str,
    payload: AdminMerchantCatalogPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    merchant = next((item for item in service.list_merchants() if item["id"] == merchant_id), None)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Marchand introuvable")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode"),
        write=True,
    )
    try:
        return success_response(
            service.create_catalog(
                merchant_id=merchant_id,
                name=payload.name,
                description=payload.description,
                is_active=payload.is_active,
                is_default=payload.is_default,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/shop/catalogs")
def admin_list_shop_catalogs(
    merchant_id: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    items = service.list_catalogs(merchant_id=merchant_id)
    if merchant_id:
        merchant = next((item for item in service.list_merchants() if item["id"] == merchant_id), None)
        if merchant is None:
            raise HTTPException(status_code=404, detail="Marchand introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
            country_code=merchant.get("countryCode"),
            write=False,
        )
        return success_response(items)

    merchant_map = {item["id"]: item for item in service.list_merchants()}
    scoped = []
    for item in items:
        merchant = merchant_map.get(item["merchantId"])
        if merchant is None:
            continue
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": merchant.get("countryCode")}],
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/shop/catalogs/{catalog_id}/items")
def admin_create_shop_catalog_item(
    catalog_id: str,
    payload: AdminMerchantItemPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    catalogs = service.list_catalogs()
    catalog = next((item for item in catalogs if item["id"] == catalog_id), None)
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalogue introuvable")
    merchant = next((item for item in service.list_merchants() if item["id"] == catalog["merchantId"]), None)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Marchand introuvable")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode"),
        write=True,
    )
    try:
        return success_response(
            service.create_catalog_item(
                catalog_id=catalog_id,
                name=payload.name,
                price=Decimal(payload.price),
                currency=payload.currency,
                description=payload.description,
                category=payload.category,
                sku=payload.sku,
                stock_quantity=payload.stock_quantity,
                track_inventory=payload.track_inventory,
                is_available=payload.is_available,
                is_sold_out=payload.is_sold_out,
                image_url=payload.image_url,
                attributes=payload.attributes,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/shop/items")
def admin_list_shop_items(
    catalog_id: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    items = service.list_catalog_items(
        catalog_id=catalog_id,
        merchant_id=merchant_id,
        category=category,
        active_only=active_only,
    )
    if merchant_id:
        merchant = next((item for item in service.list_merchants() if item["id"] == merchant_id), None)
        if merchant is None:
            raise HTTPException(status_code=404, detail="Marchand introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
            country_code=merchant.get("countryCode"),
            write=False,
        )
        return success_response(items)

    merchant_map = {item["id"]: item for item in service.list_merchants()}
    catalog_map = {item["id"]: item for item in service.list_catalogs()}
    scoped = []
    for item in items:
        catalog = catalog_map.get(item["catalogId"])
        if catalog is None:
            continue
        merchant = merchant_map.get(catalog["merchantId"])
        if merchant is None:
            continue
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": merchant.get("countryCode")}],
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/shop/orders")
def admin_create_shop_order(
    payload: AdminShopOrderPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    merchant = next((item for item in service.list_merchants() if item["id"] == payload.merchant_id), None)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Marchand introuvable")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode"),
        write=True,
    )
    try:
        return success_response(
            service.create_order(
                merchant_id=payload.merchant_id,
                customer_user_id=payload.customer_user_id,
                items=[item.model_dump() for item in payload.items],
                beneficiary_name=payload.beneficiary_name,
                beneficiary_phone=payload.beneficiary_phone,
                ordered_for_other=payload.ordered_for_other,
                delivery_address=payload.delivery_address,
                delivery_latitude=payload.delivery_latitude,
                delivery_longitude=payload.delivery_longitude,
                delivery_amount=Decimal(payload.delivery_amount) if payload.delivery_amount is not None else None,
                notes=payload.notes,
                customer_note=payload.customer_note,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/shop/orders")
def admin_list_shop_orders(
    merchant_id: str | None = Query(default=None),
    customer_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    items = service.list_orders(
        customer_user_id=customer_user_id,
        merchant_id=merchant_id,
        status=status,
    )
    merchant_map = {item["id"]: item for item in service.list_merchants()}
    scoped = []
    for item in items:
        merchant = merchant_map.get(item["merchantId"])
        if merchant is None:
            continue
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": merchant.get("countryCode")}],
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.get("/shop/orders/{order_id}")
def admin_get_shop_order_detail(
    order_id: str,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    try:
        detail = service.get_order_detail(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    merchant = next((item for item in service.list_merchants() if item["id"] == detail.get("merchantId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode") if merchant else None,
        write=False,
    )
    return success_response(detail)


@router.post("/shop/orders/{order_id}/fund")
def admin_fund_shop_order(
    order_id: str,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    try:
        detail = service.get_order_detail(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    merchant = next((item for item in service.list_merchants() if item["id"] == detail.get("merchantId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode") if merchant else None,
        write=True,
    )
    try:
        return success_response(service.fund_order(order_id=order_id, customer_user_id=detail["customerUserId"]))
    except (ValueError, InsufficientFundsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/shop/orders/{order_id}/status")
def admin_update_shop_order_status(
    order_id: str,
    payload: AdminShopOrderStatusPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    try:
        detail = service.get_order_detail(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    merchant = next((item for item in service.list_merchants() if item["id"] == detail.get("merchantId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
        country_code=merchant.get("countryCode") if merchant else None,
        write=True,
    )
    owner_id = merchant.get("ownerUserId") if merchant else None
    if not owner_id:
        raise HTTPException(status_code=409, detail="Le marchand n'a pas de propriétaire défini pour cette opération")
    try:
        return success_response(
            service.update_merchant_order_status(
                actor_user_id=owner_id,
                order_id=order_id,
                status=payload.status,
                note=payload.note,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/shop/payouts")
def admin_list_shop_payouts(
    period_key: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    if merchant_id:
        merchant = next((item for item in service.list_merchants() if item["id"] == merchant_id), None)
        if merchant is None:
            raise HTTPException(status_code=404, detail="Marchand introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
            country_code=merchant.get("countryCode"),
            write=False,
        )
    rows = service.list_merchant_payout_snapshots(
        period_key=period_key,
        merchant_id=merchant_id,
        currency=currency,
    )
    rows = filter_records_for_admin_scope(
        records=rows,
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
    )
    return success_response(rows)


@router.post("/shop/payouts/build")
def admin_build_shop_payouts(
    period_key: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: ShopService = Depends(get_shop_service),
):
    if merchant_id:
        merchant = next((item for item in service.list_merchants() if item["id"] == merchant_id), None)
        if merchant is None:
            raise HTTPException(status_code=404, detail="Marchand introuvable")
        assert_admin_scope_access(
            user_id=admin_user_id,
            db=db,
            module_key="SHOP",
            country_code=merchant.get("countryCode"),
            write=True,
        )
    rows = service.build_merchant_payout_snapshots(period_key=period_key, merchant_id=merchant_id)
    rows = filter_records_for_admin_scope(
        records=rows,
        user_id=admin_user_id,
        db=db,
        module_key="SHOP",
    )
    return success_response(rows)


@router.post("/vtc/driver-users")
def admin_create_vtc_driver_user(
    payload: DriverUserCreatePayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=payload.country_code,
        write=True,
    )
    try:
        return success_response(
            service.create_driver_user(
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
                country_code=payload.country_code,
                phone=payload.phone,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/vtc/operators")
def admin_create_vtc_operator(
    payload: AdminVtcOperatorPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=payload.country_code,
        write=True,
    )
    return success_response(
        service.create_operator(
            public_name=payload.public_name,
            country_code=payload.country_code,
            city_name=payload.city_name,
            currency=payload.currency,
            owner_user_id=payload.owner_user_id,
            service_zone_id=payload.service_zone_id,
            legal_name=payload.legal_name,
            description=payload.description,
            phone=payload.phone,
            email=payload.email,
            is_active=payload.is_active,
            accepting_rides=payload.accepting_rides,
            launch_status=payload.launch_status,
            metadata=payload.metadata,
        )
    )


@router.get("/vtc/operators")
def admin_list_vtc_operators(
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    items = service.list_operators(
        country_code=country_code,
        city_name=city_name,
        active_only=active_only,
    )
    items = filter_records_for_admin_scope(
        records=items,
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
    )
    return success_response(items)


@router.post("/vtc/drivers")
def admin_create_vtc_driver_profile(
    payload: AdminVtcDriverProfilePayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    operator_country = None
    if payload.operator_id:
        operator = next((item for item in service.list_operators() if item["id"] == payload.operator_id), None)
        if operator is None:
            raise HTTPException(status_code=404, detail="Opérateur introuvable")
        operator_country = operator.get("countryCode")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator_country,
        write=True,
    )
    try:
        return success_response(
            service.create_driver_profile(
                user_id=payload.user_id,
                operator_id=payload.operator_id,
                license_number=payload.license_number,
                license_country_code=payload.license_country_code,
                license_expires_at=payload.license_expires_at,
                vehicle_ready=payload.vehicle_ready,
                is_active=payload.is_active,
                verification_status=payload.verification_status,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/vtc/drivers")
def admin_list_vtc_driver_profiles(
    operator_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    items = service.list_driver_profiles(operator_id=operator_id, user_id=user_id)
    operator_map = {item["id"]: item for item in service.list_operators()}
    scoped = []
    for item in items:
        operator = operator_map.get(item.get("operatorId"))
        country_code = operator.get("countryCode") if operator else None
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": country_code}],
            user_id=admin_user_id,
            db=db,
            module_key="VTC",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/vtc/vehicles")
def admin_create_vtc_vehicle(
    payload: AdminVtcVehiclePayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    operator_country = None
    if payload.operator_id:
        operator = next((item for item in service.list_operators() if item["id"] == payload.operator_id), None)
        if operator is None:
            raise HTTPException(status_code=404, detail="Opérateur introuvable")
        operator_country = operator.get("countryCode")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator_country,
        write=True,
    )
    try:
        return success_response(
            service.create_vehicle(
                make=payload.make,
                model=payload.model,
                plate_number=payload.plate_number,
                seats_count=payload.seats_count,
                operator_id=payload.operator_id,
                driver_user_id=payload.driver_user_id,
                color=payload.color,
                category=payload.category,
                is_active=payload.is_active,
                verification_status=payload.verification_status,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/vtc/vehicles")
def admin_list_vtc_vehicles(
    operator_id: str | None = Query(default=None),
    driver_user_id: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    items = service.list_vehicles(operator_id=operator_id, driver_user_id=driver_user_id)
    operator_map = {item["id"]: item for item in service.list_operators()}
    scoped = []
    for item in items:
        operator = operator_map.get(item.get("operatorId"))
        country_code = operator.get("countryCode") if operator else None
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": country_code}],
            user_id=admin_user_id,
            db=db,
            module_key="VTC",
        ):
            scoped.append(item)
    return success_response(scoped)


@router.post("/vtc/rides")
def admin_create_vtc_ride(
    payload: AdminVtcRidePayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    operator_country = None
    if payload.operator_id:
        operator = next((item for item in service.list_operators() if item["id"] == payload.operator_id), None)
        if operator is None:
            raise HTTPException(status_code=404, detail="Opérateur introuvable")
        operator_country = operator.get("countryCode")
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator_country,
        write=True,
    )
    try:
        return success_response(
            service.create_ride_request(
                customer_user_id=payload.customer_user_id,
                pickup_address=payload.pickup_address,
                destination_address=payload.destination_address,
                currency=payload.currency,
                operator_id=payload.operator_id,
                driver_user_id=payload.driver_user_id,
                linked_task_id=payload.linked_task_id,
                pickup_latitude=payload.pickup_latitude,
                pickup_longitude=payload.pickup_longitude,
                destination_latitude=payload.destination_latitude,
                destination_longitude=payload.destination_longitude,
                scheduled_at=payload.scheduled_at,
                estimated_distance_km=payload.estimated_distance_km,
                estimated_duration_minutes=payload.estimated_duration_minutes,
                estimated_fare=payload.estimated_fare,
                passenger_name=payload.passenger_name,
                passenger_phone=payload.passenger_phone,
                ride_type=payload.ride_type,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/vtc/rides")
def admin_list_vtc_rides(
    customer_user_id: str | None = Query(default=None),
    operator_id: str | None = Query(default=None),
    driver_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    items = service.list_rides(
        customer_user_id=customer_user_id,
        operator_id=operator_id,
        driver_user_id=driver_user_id,
        status=status,
    )
    operator_map = {item["id"]: item for item in service.list_operators()}
    scoped = []
    for item in items:
        operator = operator_map.get(item.get("operatorId"))
        country_code = operator.get("countryCode") if operator else None
        if filter_records_for_admin_scope(
            records=[{**item, "countryCode": country_code}],
            user_id=admin_user_id,
            db=db,
            module_key="VTC",
        ):
            scoped.append(item)
    return success_response(scoped)


class AdminVtcAssignDriverPayload(BaseModel):
    driver_user_id: str


class AdminVtcRideActionPayload(BaseModel):
    note: str | None = None


@router.get("/vtc/rides/{ride_id}")
def admin_get_vtc_ride_detail(
    ride_id: str,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    try:
        detail = service.get_ride_detail(ride_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    operator = next((item for item in service.list_operators() if item["id"] == detail.get("operatorId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator.get("countryCode") if operator else None,
        write=False,
    )
    return success_response(detail)


@router.get("/vtc/rides/{ride_id}/offers")
def admin_list_vtc_ride_offers(
    ride_id: str,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    try:
        detail = service.get_ride_detail(ride_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    operator = next((item for item in service.list_operators() if item["id"] == detail.get("operatorId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator.get("countryCode") if operator else None,
        write=False,
    )
    return success_response(detail["offers"])


@router.post("/vtc/rides/{ride_id}/dispatch")
def admin_dispatch_vtc_ride(
    ride_id: str,
    payload: AdminVtcRideActionPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    try:
        detail = service.get_ride_detail(ride_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    operator = next((item for item in service.list_operators() if item["id"] == detail.get("operatorId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator.get("countryCode") if operator else None,
        write=True,
    )
    try:
        return success_response(service.dispatch_ride(ride_id=ride_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/vtc/rides/{ride_id}/assign-driver")
def admin_assign_vtc_driver(
    ride_id: str,
    payload: AdminVtcAssignDriverPayload,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    try:
        detail = service.get_ride_detail(ride_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    operator = next((item for item in service.list_operators() if item["id"] == detail.get("operatorId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator.get("countryCode") if operator else None,
        write=True,
    )
    try:
        return success_response(
            service.admin_assign_driver(
                ride_id=ride_id,
                driver_user_id=payload.driver_user_id,
                actor_user_id=admin_user_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/vtc/rides/{ride_id}/settle")
def admin_settle_vtc_ride(
    ride_id: str,
    admin_user_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
    service: VtcService = Depends(get_vtc_service),
):
    try:
        detail = service.get_ride_detail(ride_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    operator = next((item for item in service.list_operators() if item["id"] == detail.get("operatorId")), None)
    assert_admin_scope_access(
        user_id=admin_user_id,
        db=db,
        module_key="VTC",
        country_code=operator.get("countryCode") if operator else None,
        write=True,
    )
    try:
        return success_response(service.settle_ride_payout(ride_id=ride_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
