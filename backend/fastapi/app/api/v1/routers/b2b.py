from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_b2b_service, get_current_user_id, get_db
from app.core.responses import success_response
from app.services.api_key_service import ApiKeyError, ApiKeyService
from app.services.b2b_service import B2BService
from sqlalchemy.orm import Session


router = APIRouter(prefix="/b2b", tags=["b2b"])


class ApiKeyCreatePayload(BaseModel):
    organization_id: str
    name: str
    scopes: list[str] = []
    is_sandbox: bool = False
    rate_limit_per_minute: int = 60
    expires_at: datetime | None = None


class B2BWorkOrderPayload(BaseModel):
    organization_id: str
    template_id: str | None = None
    beneficiary_name: str | None = None
    beneficiary_phone: str | None = None
    scheduled_at: datetime | None = None
    price: Decimal
    currency: str
    notes: str | None = None
    assigned_tasker_id: str | None = None
    linked_task_id: str | None = None
    status: str = "draft"


@router.get("/me")
def get_my_b2b_dashboard(
    user_id: str = Depends(get_current_user_id),
    service: B2BService = Depends(get_b2b_service),
):
    return success_response(service.get_my_dashboard(user_id))


@router.get("/orders")
def list_my_b2b_orders(
    organization_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    service: B2BService = Depends(get_b2b_service),
):
    dashboard = service.get_my_dashboard(user_id)
    org_ids = {item["id"] for item in dashboard["organizations"]}
    if organization_id and organization_id not in org_ids:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette organisation")
    orders = service.list_work_orders(
        organization_id=organization_id,
        status=status,
        requested_by_user_id=None if organization_id else user_id,
    )
    if not organization_id:
        orders = [item for item in orders if item["organizationId"] in org_ids]
    return success_response(orders)


@router.post("/orders")
def create_b2b_work_order(
    payload: B2BWorkOrderPayload,
    user_id: str = Depends(get_current_user_id),
    service: B2BService = Depends(get_b2b_service),
):
    dashboard = service.get_my_dashboard(user_id)
    org_ids = {item["id"] for item in dashboard["organizations"]}
    if payload.organization_id not in org_ids:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette organisation")
    try:
        return success_response(
            service.create_work_order(
                organization_id=payload.organization_id,
                requested_by_user_id=user_id,
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


def _assert_member_of(organization_id: str, user_id: str, b2b_service: B2BService) -> None:
    dashboard = b2b_service.get_my_dashboard(user_id)
    org_ids = {item["id"] for item in dashboard["organizations"]}
    if organization_id not in org_ids:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette organisation")


@router.get("/api-keys")
def list_api_keys(
    organization_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    b2b_service: B2BService = Depends(get_b2b_service),
    db: Session = Depends(get_db),
):
    _assert_member_of(organization_id, user_id, b2b_service)
    return success_response(ApiKeyService(db).list_api_keys(organization_id))


@router.post("/api-keys")
def create_api_key(
    payload: ApiKeyCreatePayload,
    user_id: str = Depends(get_current_user_id),
    b2b_service: B2BService = Depends(get_b2b_service),
    db: Session = Depends(get_db),
):
    _assert_member_of(payload.organization_id, user_id, b2b_service)
    try:
        return success_response(
            ApiKeyService(db).create_api_key(
                organization_id=payload.organization_id,
                name=payload.name,
                scopes=payload.scopes,
                is_sandbox=payload.is_sandbox,
                rate_limit_per_minute=payload.rate_limit_per_minute,
                expires_at=payload.expires_at,
                created_by_user_id=user_id,
            )
        )
    except ApiKeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api-keys/{api_key_id}")
def revoke_api_key(
    api_key_id: str,
    organization_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    b2b_service: B2BService = Depends(get_b2b_service),
    db: Session = Depends(get_db),
):
    _assert_member_of(organization_id, user_id, b2b_service)
    try:
        return success_response(ApiKeyService(db).revoke_api_key(api_key_id, organization_id))
    except ApiKeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
