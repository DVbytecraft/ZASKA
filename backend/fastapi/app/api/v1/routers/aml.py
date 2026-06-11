from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_aml_service, get_current_user_id
from app.core.responses import success_response
from app.services.aml_service import AmlService


router = APIRouter(prefix="/aml", tags=["aml"])


@router.get("/me")
def list_my_aml_cases(
    limit: int = Query(default=50, le=100),
    user_id: str = Depends(get_current_user_id),
    svc: AmlService = Depends(get_aml_service),
):
    return success_response(svc.list_my_cases(user_id=user_id, limit=limit))


@router.get("/me/{case_id}")
def get_my_aml_case(
    case_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: AmlService = Depends(get_aml_service),
):
    try:
        payload = svc.get_case_detail(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payload["userId"] != user_id and payload.get("counterpartyUserId") != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce cas AML")
    return success_response(payload)
