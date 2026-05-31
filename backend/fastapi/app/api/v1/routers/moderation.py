"""Admin moderation queue — requires admin role."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.responses import success_response
from app.services.moderation_service import ModerationService

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/stats")
def get_stats(
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return success_response(ModerationService(db).get_stats())


@router.get("/cases")
def list_cases(
    status: str | None = None,
    severity: str | None = None,
    page: int = 1,
    limit: int = 20,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return success_response(ModerationService(db).list_cases(status, severity, page, limit))


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        case = ModerationService(db).get_case(case_id)
        return success_response(ModerationService._serialize(case))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class ResolvePayload(BaseModel):
    resolution: str = Field(min_length=5, max_length=512)
    action_taken: str = Field(pattern="^(none|warned|muted_24h|muted_7d|banned)$")


@router.post("/cases/{case_id}/resolve")
def resolve_case(
    case_id: str,
    payload: ResolvePayload,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        case = ModerationService(db).resolve_case(
            case_id=case_id,
            resolution=payload.resolution,
            action_taken=payload.action_taken,
            resolver_id=admin_id,
        )
        return success_response(ModerationService._serialize(case))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class DismissPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=512)


@router.post("/cases/{case_id}/dismiss")
def dismiss_case(
    case_id: str,
    payload: DismissPayload,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        case = ModerationService(db).dismiss_case(
            case_id=case_id,
            reason=payload.reason,
            resolver_id=admin_id,
        )
        return success_response(ModerationService._serialize(case))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/cases/{case_id}/escalate")
def escalate_case(
    case_id: str,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        case = ModerationService(db).escalate_case(case_id=case_id, resolver_id=admin_id)
        return success_response(ModerationService._serialize(case))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
