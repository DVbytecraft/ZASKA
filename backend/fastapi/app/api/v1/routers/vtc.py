from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import (
    get_current_user_id,
    get_vtc_service,
    require_module_enabled_for_current_user,
)
from app.core.responses import success_response
from app.services.vtc_service import VtcService


router = APIRouter(
    prefix="/vtc",
    tags=["vtc"],
    dependencies=[Depends(require_module_enabled_for_current_user("VTC"))],
)


class RideRequestPayload(BaseModel):
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
    customer_note: str | None = None
    metadata: dict | None = None


class RideQuotePayload(BaseModel):
    currency: str
    operator_id: str | None = None
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    estimated_distance_km: Decimal | None = None
    estimated_duration_minutes: int | None = None
    estimated_fare: Decimal | None = None
    ride_type: str = "standard"


class DriverPresencePayload(BaseModel):
    is_online: bool
    latitude: float | None = None
    longitude: float | None = None
    operator_id: str | None = None


class DriverLocationPayload(BaseModel):
    latitude: float
    longitude: float
    heading: float | None = None


class OfferResponsePayload(BaseModel):
    accept: bool


class DriverRideActionPayload(BaseModel):
    note: str | None = None
    final_fare: Decimal | None = None
    final_distance_km: Decimal | None = None
    final_duration_minutes: int | None = None


class RideCancellationPayload(BaseModel):
    reason: str | None = None


@router.get("/operators")
def list_vtc_operators(
    country_code: str | None = Query(default=None),
    city_name: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    service: VtcService = Depends(get_vtc_service),
    _: str = Depends(get_current_user_id),
):
    return success_response(
        service.list_operators(
            country_code=country_code,
            city_name=city_name,
            active_only=active_only,
            limit=limit,
        )
    )


@router.post("/rides")
def create_ride_request(
    payload: RideRequestPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.create_ride_request(
                customer_user_id=user_id,
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
                customer_note=payload.customer_note,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/quote")
def quote_vtc_ride(
    payload: RideQuotePayload,
    service: VtcService = Depends(get_vtc_service),
    _: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.quote_ride_request(
                operator_id=payload.operator_id,
                currency=payload.currency,
                ride_type=payload.ride_type,
                pickup_latitude=payload.pickup_latitude,
                pickup_longitude=payload.pickup_longitude,
                destination_latitude=payload.destination_latitude,
                destination_longitude=payload.destination_longitude,
                estimated_distance_km=payload.estimated_distance_km,
                estimated_duration_minutes=payload.estimated_duration_minutes,
                estimated_fare=payload.estimated_fare,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rides/me")
def list_my_vtc_rides(
    status: str | None = Query(default=None),
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.list_rides(customer_user_id=user_id, status=status))


@router.get("/rides/{ride_id}")
def get_my_vtc_ride_detail(
    ride_id: str,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        detail = service.get_ride_detail(ride_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if detail["customerUserId"] != user_id and detail.get("driverUserId") != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return success_response(detail)


@router.post("/rides/{ride_id}/cancel")
def cancel_my_vtc_ride(
    ride_id: str,
    payload: RideCancellationPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.cancel_ride_as_customer(user_id=user_id, ride_id=ride_id, reason=payload.reason))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/driver/presence")
def update_my_driver_presence(
    payload: DriverPresencePayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.update_driver_presence(
                user_id=user_id,
                is_online=payload.is_online,
                latitude=payload.latitude,
                longitude=payload.longitude,
                operator_id=payload.operator_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/driver/location")
def update_my_driver_location(
    payload: DriverLocationPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.update_driver_location(
                user_id=user_id,
                latitude=payload.latitude,
                longitude=payload.longitude,
                heading=payload.heading,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/driver/offers")
def list_my_driver_offers(
    include_expired: bool = Query(default=False),
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.list_driver_offers(user_id=user_id, include_expired=include_expired))


@router.post("/driver/offers/{offer_id}/respond")
def respond_to_driver_offer(
    offer_id: str,
    payload: OfferResponsePayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.respond_to_offer(user_id=user_id, offer_id=offer_id, accept=payload.accept))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/driver/rides")
def list_my_driver_rides(
    status: str | None = Query(default=None),
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.list_driver_rides(user_id=user_id, status=status))


@router.post("/driver/rides/{ride_id}/en-route")
def mark_driver_ride_en_route(
    ride_id: str,
    payload: DriverRideActionPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.update_ride_status_as_driver(user_id=user_id, ride_id=ride_id, action="en_route", note=payload.note))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/driver/rides/{ride_id}/arrived")
def mark_driver_ride_arrived(
    ride_id: str,
    payload: DriverRideActionPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.update_ride_status_as_driver(user_id=user_id, ride_id=ride_id, action="arrived", note=payload.note))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/driver/rides/{ride_id}/start")
def start_driver_ride(
    ride_id: str,
    payload: DriverRideActionPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.update_ride_status_as_driver(user_id=user_id, ride_id=ride_id, action="start", note=payload.note))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/driver/rides/{ride_id}/complete")
def complete_driver_ride(
    ride_id: str,
    payload: DriverRideActionPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(
            service.update_ride_status_as_driver(
                user_id=user_id,
                ride_id=ride_id,
                action="complete",
                note=payload.note,
                final_fare=payload.final_fare,
                final_distance_km=payload.final_distance_km,
                final_duration_minutes=payload.final_duration_minutes,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/driver/rides/{ride_id}/cancel")
def cancel_driver_ride(
    ride_id: str,
    payload: DriverRideActionPayload,
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return success_response(service.update_ride_status_as_driver(user_id=user_id, ride_id=ride_id, action="cancel", note=payload.note))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/driver/me")
def get_my_driver_dashboard(
    service: VtcService = Depends(get_vtc_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.get_driver_dashboard(user_id))
