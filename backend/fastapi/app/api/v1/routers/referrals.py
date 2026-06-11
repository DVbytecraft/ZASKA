from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user_id, get_referral_service, require_permission
from app.core.responses import success_response
from app.services.referral_service import ReferralService

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ReferralProgramUpdatePayload(BaseModel):
    reward_kind: str | None = None
    reward_amount: float | None = None
    reward_currency: str | None = None
    qualification_threshold: int | None = None
    description: str | None = None
    is_active: bool | None = None


@router.get("/me")
def get_my_referrals(
    user_id: str = Depends(get_current_user_id),
    service: ReferralService = Depends(get_referral_service),
):
    try:
        return success_response(service.get_user_referral_dashboard(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/admin/programs")
def admin_list_referral_programs(
    service: ReferralService = Depends(get_referral_service),
    _: str = Depends(require_permission("admin.referrals.read")),
):
    return success_response(service.list_programs())


@router.patch("/admin/programs/{program_id}")
def admin_update_referral_program(
    program_id: str,
    payload: ReferralProgramUpdatePayload,
    service: ReferralService = Depends(get_referral_service),
    _: str = Depends(require_permission("admin.referrals.manage")),
):
    try:
        return success_response(service.update_program(program_id, payload.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/admin/events")
def admin_list_referral_events(
    status: str | None = Query(default=None),
    referral_type: str | None = Query(default=None),
    service: ReferralService = Depends(get_referral_service),
    _: str = Depends(require_permission("admin.referrals.read")),
):
    return success_response(service.list_events(status=status, referral_type=referral_type))


@router.get("/admin/rewards")
def admin_list_referral_rewards(
    status: str | None = Query(default=None),
    service: ReferralService = Depends(get_referral_service),
    _: str = Depends(require_permission("admin.referrals.read")),
):
    return success_response(service.list_rewards(status=status))
