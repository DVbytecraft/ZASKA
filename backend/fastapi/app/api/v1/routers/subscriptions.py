from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import (
    get_current_user_id,
    get_subscription_service,
    require_country_live_access,
    require_module_enabled_for_current_user,
)
from app.core.responses import success_response
from app.services.subscription_service import SubscriptionService

router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
    dependencies=[Depends(require_module_enabled_for_current_user("SUBSCRIPTIONS"))],
)


class SubscribePayload(BaseModel):
    plan_code: str
    auto_renew: bool = True


class PreviewPayload(BaseModel):
    service_category: str
    estimated_amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=8)


@router.get("/plans")
def list_subscription_plans(
    service: SubscriptionService = Depends(get_subscription_service),
):
    return success_response(service.list_public_plans())


@router.get("/me")
def get_my_subscriptions(
    user_id: str = Depends(require_country_live_access),
    service: SubscriptionService = Depends(get_subscription_service),
):
    return success_response(service.get_user_summary(user_id))


@router.post("/me/subscribe")
def subscribe_me(
    payload: SubscribePayload,
    user_id: str = Depends(require_country_live_access),
    service: SubscriptionService = Depends(get_subscription_service),
):
    try:
        result = service.subscribe_user(
            user_id=user_id,
            plan_code=payload.plan_code,
            source="self_service",
            auto_renew=payload.auto_renew,
        )
        return success_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/me/preview")
def preview_subscription_benefit(
    payload: PreviewPayload,
    user_id: str = Depends(require_country_live_access),
    service: SubscriptionService = Depends(get_subscription_service),
):
    return success_response(
        service.preview_for_service(
            user_id=user_id,
            service_category=payload.service_category,
            estimated_amount=payload.estimated_amount,
            currency=payload.currency,
        )
    )


@router.post("/me/{subscription_id}/pause")
def pause_my_subscription(
    subscription_id: str,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    try:
        return success_response(service.pause_subscription(user_id, subscription_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/me/{subscription_id}/resume")
def resume_my_subscription(
    subscription_id: str,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    try:
        return success_response(service.resume_subscription(user_id, subscription_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/me/{subscription_id}/cancel")
def cancel_my_subscription(
    subscription_id: str,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    try:
        return success_response(service.cancel_subscription(user_id, subscription_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
