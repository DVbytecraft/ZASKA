from __future__ import annotations

from decimal import Decimal
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import (
    get_current_user_id,
    get_food_service,
    require_country_live_access,
    require_module_enabled_for_current_user,
)
from app.core.responses import success_response
from app.models.food import FoodOrder, FoodOrderItem, RestaurantMenu, RestaurantMenuItem, RestaurantPartner
from app.services.food_service import FoodService
from app.services.wallet_service import InsufficientFundsError

router = APIRouter(
    prefix="/food",
    tags=["food"],
    dependencies=[
        Depends(require_country_live_access),
        Depends(require_module_enabled_for_current_user("FOOD")),
    ],
)


class FoodOrderItemPayload(BaseModel):
    menu_item_id: str | None = None
    combo_offer_id: str | None = None
    quantity: int = Field(default=1, ge=1, le=100)
    modifier_option_ids: list[str] = []


class FoodOrderCreatePayload(BaseModel):
    restaurant_id: str
    items: list[FoodOrderItemPayload]
    delivery_address: str
    delivery_fee: Decimal | None = Field(default=None, ge=0)
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    notes: str | None = None
    ordered_for_other: bool = False
    beneficiary_name: str | None = None
    beneficiary_phone: str | None = None


class FoodQuotePayload(BaseModel):
    restaurant_id: str
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    delivery_fee: Decimal | None = Field(default=None, ge=0)


class FoodOrderStatusPayload(BaseModel):
    status: str
    estimated_prep_minutes: int | None = Field(default=None, ge=1, le=240)


class DispatchCandidatesPayload(BaseModel):
    latitude: float
    longitude: float
    country_code: str | None = None
    city_name: str | None = None
    limit: int = Field(default=25, ge=1, le=100)


def _serialize_restaurant(restaurant: RestaurantPartner) -> dict[str, object]:
    return {
        "id": restaurant.id,
        "ownerUserId": restaurant.owner_user_id,
        "publicName": restaurant.public_name,
        "legalName": restaurant.legal_name,
        "description": restaurant.description,
        "countryCode": restaurant.country_code,
        "cityName": restaurant.city_name,
        "address": restaurant.address,
        "latitude": restaurant.latitude,
        "longitude": restaurant.longitude,
        "currency": restaurant.currency,
        "phone": restaurant.phone,
        "email": restaurant.email,
        "acceptsCashOnDelivery": bool(restaurant.accepts_cash_on_delivery),
        "isActive": bool(restaurant.is_active),
        "acceptingOrders": bool(restaurant.accepting_orders),
        "isTemporarilyClosed": bool(restaurant.is_temporarily_closed),
        "prepBufferMinutes": restaurant.prep_buffer_minutes,
        "serviceZoneId": restaurant.service_zone_id,
        "openingHours": json.loads(restaurant.opening_hours_json) if restaurant.opening_hours_json else None,
        "launchStatus": restaurant.launch_status,
        "createdAt": restaurant.created_at.isoformat() if restaurant.created_at else None,
    }


def _serialize_restaurant_discovery(entry: dict[str, object]) -> dict[str, object]:
    restaurant = entry["restaurant"]
    payload = _serialize_restaurant(restaurant)
    payload["distanceKm"] = entry.get("distance_km")
    payload["supportsTargetLocation"] = bool(entry.get("supports_target_location", True))
    return payload


def _serialize_menu(menu: RestaurantMenu) -> dict[str, object]:
    return {
        "id": menu.id,
        "restaurantId": menu.restaurant_id,
        "name": menu.name,
        "description": menu.description,
        "isActive": bool(menu.is_active),
        "isDefault": bool(menu.is_default),
        "createdAt": menu.created_at.isoformat() if menu.created_at else None,
    }


def _serialize_menu_item(item: RestaurantMenuItem) -> dict[str, object]:
    return {
        "id": item.id,
        "menuId": item.menu_id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "price": str(item.price),
        "currency": item.currency,
        "isAvailable": bool(item.is_available),
        "isSoldOut": bool(item.is_sold_out),
        "trackInventory": bool(item.track_inventory),
        "stockQuantity": item.stock_quantity,
        "prepMinutes": item.prep_minutes,
        "availableFromHour": item.available_from_hour,
        "availableToHour": item.available_to_hour,
        "imageUrl": item.image_url,
        "createdAt": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_modifier_group(group, options: list[object]) -> dict[str, object]:
    return {
        "id": group.id,
        "menuItemId": group.menu_item_id,
        "name": group.name,
        "isRequired": bool(group.is_required),
        "minSelect": group.min_select,
        "maxSelect": group.max_select,
        "isActive": bool(group.is_active),
        "options": [
            {
                "id": option.id,
                "modifierGroupId": option.modifier_group_id,
                "name": option.name,
                "priceDelta": str(option.price_delta),
                "currency": option.currency,
                "isDefault": bool(option.is_default),
                "isActive": bool(option.is_active),
            }
            for option in options
        ],
    }


def _serialize_combo_offer(combo, combo_items: list[object]) -> dict[str, object]:
    return {
        "id": combo.id,
        "restaurantId": combo.restaurant_id,
        "name": combo.name,
        "description": combo.description,
        "price": str(combo.price),
        "currency": combo.currency,
        "isActive": bool(combo.is_active),
        "availableFromHour": combo.available_from_hour,
        "availableToHour": combo.available_to_hour,
        "items": [
            {
                "id": item.id,
                "menuItemId": item.menu_item_id,
                "quantity": item.quantity,
            }
            for item in combo_items
        ],
    }


def _serialize_order_item(item: FoodOrderItem) -> dict[str, object]:
    return {
        "id": item.id,
        "foodOrderId": item.food_order_id,
        "menuItemId": item.menu_item_id,
        "itemName": item.item_name,
        "quantity": item.quantity,
        "unitPrice": str(item.unit_price),
        "modifierTotal": str(item.modifier_total),
        "lineTotal": str(item.line_total),
    }


def _serialize_order(order: FoodOrder, items: list[FoodOrderItem] | None = None) -> dict[str, object]:
    metadata = json.loads(order.metadata_json) if order.metadata_json else {}
    return {
        "id": order.id,
        "customerUserId": order.customer_user_id,
        "restaurantId": order.restaurant_id,
        "deliveryTaskId": order.delivery_task_id,
        "mealHoldId": order.meal_hold_id,
        "deliveryEscrowId": order.delivery_escrow_id,
        "status": order.status,
        "paymentStatus": order.payment_status,
        "dispatchStatus": order.dispatch_status,
        "countryCode": order.country_code,
        "cityName": order.city_name,
        "currency": order.currency,
        "subtotal": str(order.subtotal),
        "deliveryFee": str(order.delivery_fee),
        "totalAmount": str(order.total_amount),
        "restaurantAmount": str(order.restaurant_amount),
        "deliveryAmount": str(order.delivery_amount),
        "orderedForOther": bool(order.ordered_for_other),
        "beneficiaryName": order.beneficiary_name,
        "beneficiaryPhone": order.beneficiary_phone,
        "deliveryAddress": order.delivery_address,
        "deliveryLatitude": order.delivery_latitude,
        "deliveryLongitude": order.delivery_longitude,
        "notes": order.notes,
        "estimatedPrepMinutes": order.estimated_prep_minutes,
        "pricingBreakdown": metadata.get("pricingBreakdown") if isinstance(metadata, dict) else None,
        "restaurantConfirmedAt": order.restaurant_confirmed_at.isoformat() if order.restaurant_confirmed_at else None,
        "deliveredAt": order.delivered_at.isoformat() if order.delivered_at else None,
        "createdAt": order.created_at.isoformat() if order.created_at else None,
        "items": [_serialize_order_item(item) for item in items] if items is not None else None,
    }


@router.get("/restaurants")
def list_food_restaurants(
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    reference_latitude: float | None = Query(default=None),
    reference_longitude: float | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    service: FoodService = Depends(get_food_service),
    _: str = Depends(get_current_user_id),
):
    restaurants = service.discover_restaurants(
        country_code=country_code,
        city_name=city_name,
        reference_latitude=reference_latitude,
        reference_longitude=reference_longitude,
        limit=limit,
    )
    return success_response([_serialize_restaurant_discovery(entry) for entry in restaurants])


@router.get("/restaurants/{restaurant_id}")
def get_food_restaurant(
    restaurant_id: str,
    service: FoodService = Depends(get_food_service),
    _: str = Depends(get_current_user_id),
):
    restaurant = service.get_restaurant(restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    menus = service.list_menus(restaurant_id)
    menu_items = service.list_menu_items(restaurant_id=restaurant_id)
    combos = service.list_combo_offers(restaurant_id=restaurant_id)
    modifier_groups_payload: dict[str, list[dict[str, object]]] = {}
    for item in menu_items:
        groups = service.list_modifier_groups(menu_item_id=item.id)
        modifier_groups_payload[item.id] = [
            _serialize_modifier_group(group, service.list_modifier_options(modifier_group_id=group.id))
            for group in groups
        ]
    return success_response(
        {
            **_serialize_restaurant(restaurant),
            "menus": [_serialize_menu(menu) for menu in menus],
            "menuItems": [_serialize_menu_item(item) for item in menu_items],
            "comboOffers": [
                _serialize_combo_offer(combo, service.list_combo_items(combo_offer_id=combo.id))
                for combo in combos
            ],
            "modifiersByItem": modifier_groups_payload,
        }
    )


@router.post("/orders")
def create_food_order(
    payload: FoodOrderCreatePayload,
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        order = service.create_food_order(
            customer_user_id=user_id,
            restaurant_id=payload.restaurant_id,
            items=[item.model_dump() for item in payload.items],
            delivery_address=payload.delivery_address,
            delivery_fee=payload.delivery_fee,
            delivery_latitude=payload.delivery_latitude,
            delivery_longitude=payload.delivery_longitude,
            notes=payload.notes,
            ordered_for_other=payload.ordered_for_other,
            beneficiary_name=payload.beneficiary_name,
            beneficiary_phone=payload.beneficiary_phone,
        )
        return success_response(_serialize_order(order, service.list_order_items(order.id)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/quote")
def quote_food_delivery(
    payload: FoodQuotePayload,
    service: FoodService = Depends(get_food_service),
    _: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.quote_delivery(
                restaurant_id=payload.restaurant_id,
                delivery_latitude=payload.delivery_latitude,
                delivery_longitude=payload.delivery_longitude,
                requested_delivery_fee=payload.delivery_fee,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/fund")
def fund_food_order(
    order_id: str,
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        order = service.fund_order(order_id=order_id, customer_user_id=user_id)
        return success_response(_serialize_order(order, service.list_order_items(order.id)))
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/restaurant")
def list_restaurant_food_orders(
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    orders = service.list_restaurant_orders(user_id)
    return success_response([_serialize_order(order) for order in orders])


@router.get("/orders/{order_id}")
def get_food_order(
    order_id: str,
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    order = service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    restaurant_orders = {row.id for row in service.list_restaurant_orders(user_id)}
    if order.customer_user_id != user_id and order.id not in restaurant_orders:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return success_response(_serialize_order(order, service.list_order_items(order.id)))


@router.post("/orders/{order_id}/restaurant-status")
def update_food_order_status_as_restaurant(
    order_id: str,
    payload: FoodOrderStatusPayload,
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        order = service.update_order_status_as_restaurant(
            order_id=order_id,
            actor_user_id=user_id,
            status=payload.status,
            estimated_prep_minutes=payload.estimated_prep_minutes,
        )
        return success_response(_serialize_order(order, service.list_order_items(order.id)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/dispatch/candidates")
def get_food_dispatch_candidates(
    payload: DispatchCandidatesPayload,
    service: FoodService = Depends(get_food_service),
    _: str = Depends(get_current_user_id),
):
    return success_response(
        service.get_dispatch_candidates(
            tasker_latitude=payload.latitude,
            tasker_longitude=payload.longitude,
            country_code=payload.country_code,
            city_name=payload.city_name,
            limit=payload.limit,
        )
    )


@router.get("/orders/me")
def list_my_food_orders(
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    orders = service.list_customer_orders(user_id)
    return success_response(
        [
            _serialize_order(order, service.list_order_items(order.id))
            for order in orders
        ]
    )


@router.get("/restaurant/orders")
def list_my_restaurant_orders(
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    orders = service.list_restaurant_orders(user_id)
    return success_response(
        [
            _serialize_order(order, service.list_order_items(order.id))
            for order in orders
        ]
    )


@router.get("/restaurant/payouts")
def list_my_restaurant_payouts(
    period_key: str | None = Query(default=None),
    restaurant_id: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    rows = service.list_restaurant_payout_snapshots(
        period_key=period_key,
        restaurant_id=restaurant_id,
        currency=currency,
    )
    visible_restaurant_ids = {order.restaurant_id for order in service.list_restaurant_orders(user_id)}
    scoped = [row for row in rows if row.get("restaurant_id") in visible_restaurant_ids]
    return success_response(scoped)


@router.post("/restaurant/payouts/sync")
def sync_my_restaurant_payouts(
    period_key: str | None = Query(default=None),
    restaurant_id: str | None = Query(default=None),
    service: FoodService = Depends(get_food_service),
    user_id: str = Depends(get_current_user_id),
):
    visible_restaurant_ids = {order.restaurant_id for order in service.list_restaurant_orders(user_id)}
    if restaurant_id is not None and restaurant_id not in visible_restaurant_ids:
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce restaurant")
    return success_response(
        service.sync_payout_snapshots_to_accounting(
            period_key=period_key,
            restaurant_id=restaurant_id,
        )
    )
