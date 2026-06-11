from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import (
    get_current_user_id,
    get_shop_service,
    require_module_enabled_for_current_user,
)
from app.core.responses import success_response
from app.services.shop_service import ShopService
from app.services.wallet_service import InsufficientFundsError


router = APIRouter(
    prefix="/shop",
    tags=["shop"],
    dependencies=[Depends(require_module_enabled_for_current_user("SHOP"))],
)


class ShopOrderLinePayload(BaseModel):
    catalog_item_id: str
    quantity: int


class ShopOrderPayload(BaseModel):
    merchant_id: str
    items: list[ShopOrderLinePayload]
    beneficiary_name: str | None = None
    beneficiary_phone: str | None = None
    ordered_for_other: bool = False
    delivery_address: str | None = None
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    delivery_amount: Decimal | None = None
    notes: str | None = None
    customer_note: str | None = None
    metadata: dict | None = None


class ShopQuotePayload(BaseModel):
    merchant_id: str
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    delivery_amount: Decimal | None = None


class MerchantOrderStatusPayload(BaseModel):
    status: str
    note: str | None = None


@router.get("/merchants")
def list_shop_merchants(
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    reference_latitude: float | None = Query(default=None),
    reference_longitude: float | None = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    service: ShopService = Depends(get_shop_service),
    _: str = Depends(get_current_user_id),
):
    return success_response(
        service.list_merchants(
            country_code=country_code,
            city_name=city_name,
            active_only=active_only,
            reference_latitude=reference_latitude,
            reference_longitude=reference_longitude,
            limit=limit,
        )
    )


@router.get("/catalogs")
def list_shop_catalogs(
    merchant_id: str | None = Query(default=None),
    service: ShopService = Depends(get_shop_service),
    _: str = Depends(get_current_user_id),
):
    return success_response(service.list_catalogs(merchant_id=merchant_id))


@router.get("/items")
def list_shop_items(
    catalog_id: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    service: ShopService = Depends(get_shop_service),
    _: str = Depends(get_current_user_id),
):
    return success_response(
        service.list_catalog_items(
            catalog_id=catalog_id,
            merchant_id=merchant_id,
            category=category,
            active_only=active_only,
        )
    )


@router.post("/orders")
def create_shop_order(
    payload: ShopOrderPayload,
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.create_order(
                merchant_id=payload.merchant_id,
                customer_user_id=user_id,
                items=[item.model_dump() for item in payload.items],
                beneficiary_name=payload.beneficiary_name,
                beneficiary_phone=payload.beneficiary_phone,
                ordered_for_other=payload.ordered_for_other,
                delivery_address=payload.delivery_address,
                delivery_latitude=payload.delivery_latitude,
                delivery_longitude=payload.delivery_longitude,
                delivery_amount=payload.delivery_amount,
                notes=payload.notes,
                customer_note=payload.customer_note,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/quote")
def quote_shop_delivery(
    payload: ShopQuotePayload,
    service: ShopService = Depends(get_shop_service),
    _: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.quote_delivery(
                merchant_id=payload.merchant_id,
                delivery_latitude=payload.delivery_latitude,
                delivery_longitude=payload.delivery_longitude,
                requested_delivery_fee=payload.delivery_amount,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/fund")
def fund_shop_order(
    order_id: str,
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.fund_order(order_id=order_id, customer_user_id=user_id))
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/me")
def list_my_shop_orders(
    status: str | None = Query(default=None),
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.list_orders(customer_user_id=user_id, status=status))


@router.get("/orders/{order_id}")
def get_shop_order(
    order_id: str,
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        payload = service.get_order_detail(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payload["customerUserId"] != user_id:
        dashboard = service.get_merchant_dashboard(user_id)
        merchant_ids = {item["id"] for item in dashboard["merchants"]}
        if payload["merchantId"] not in merchant_ids:
            raise HTTPException(status_code=403, detail="Accès non autorisé à cette commande")
    return success_response(payload)


@router.get("/merchant/orders")
def list_my_merchant_orders(
    status: str | None = Query(default=None),
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.list_merchant_orders(user_id, status=status))


@router.post("/merchant/orders/{order_id}/status")
def update_my_merchant_order_status(
    order_id: str,
    payload: MerchantOrderStatusPayload,
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.update_merchant_order_status(
                actor_user_id=user_id,
                order_id=order_id,
                status=payload.status,
                note=payload.note,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/merchant/payouts")
def list_my_merchant_payouts(
    period_key: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(
        service.list_merchant_payout_snapshots(
            period_key=period_key,
            merchant_id=merchant_id,
            currency=currency,
            actor_user_id=user_id,
        )
    )


@router.get("/me")
def get_my_shop_dashboard(
    service: ShopService = Depends(get_shop_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.get_merchant_dashboard(user_id))
