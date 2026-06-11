from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user_id, get_dispute_service
from app.core.responses import success_response
from app.services.dispute_service import DisputeService

router = APIRouter(prefix="/disputes", tags=["disputes"])


@router.get("/me")
def list_my_disputes(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    service: DisputeService = Depends(get_dispute_service),
):
    return success_response(
        service.list_disputes(
            viewer_user_id=user_id,
            admin_view=False,
            status=status,
            priority=priority,
            limit=limit,
        )
    )


@router.get("/{dispute_id}")
def get_my_dispute(
    dispute_id: str,
    user_id: str = Depends(get_current_user_id),
    service: DisputeService = Depends(get_dispute_service),
):
    try:
        return success_response(service.get_dispute_detail(dispute_id, viewer_user_id=user_id, admin_view=False))
    except ValueError as exc:
        message = str(exc)
        if "autorisé" in message:
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=404, detail=message)
