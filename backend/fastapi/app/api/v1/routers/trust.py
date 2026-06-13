"""Trust & Safety router — skills, scores, badges, content reporting."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db, require_verified_user
from app.core.rate_limit import endpoint_rate_limit
from app.core.responses import success_response
from app.services.rating_service import RatingService
from app.services.trust_service import TrustService

router = APIRouter(prefix="/trust", tags=["trust"])

# Strict limits on endpoints that trigger AI/DB writes
_report_limit = endpoint_rate_limit("trust:report", max_requests=5, window_seconds=300)
_skill_write_limit = endpoint_rate_limit("trust:skill_write", max_requests=20, window_seconds=300)


def _ts_response(ts) -> dict:
    return {
        "userId": ts.user_id,
        "totalScore": ts.total_score,
        "level": ts.level,
        "components": {
            "identity":  ts.identity_score,
            "financial": ts.financial_score,
            "profile":   ts.profile_score,
            "age":       ts.age_score,
            "community": ts.community_score,
            "behavior":  ts.behavior_score,
        },
        "computedAt": ts.computed_at.isoformat(),
    }


@router.get("/score/me")
def get_my_score(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc = TrustService(db)
    ts = svc.get_trust_score(user_id)
    if ts is None:
        try:
            ts = svc.compute_for_user(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    return success_response(_ts_response(ts))


@router.get("/score/{user_id}")
def get_user_score(
    user_id: str,
    _: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ts = TrustService(db).get_trust_score(user_id)
    if ts is None:
        return success_response({"userId": user_id, "level": "BRONZE", "totalScore": 0})
    return success_response({
        "userId": ts.user_id,
        "totalScore": ts.total_score,
        "level": ts.level,
        "computedAt": ts.computed_at.isoformat(),
    })


@router.get("/badges/catalog")
def badges_catalog(_: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.models.trust import Badge
    rows = db.execute(select(Badge).order_by(Badge.code)).scalars().all()
    return success_response([
        {"code": b.code, "label": b.label, "description": b.description, "icon": b.icon}
        for b in rows
    ])


@router.get("/badges/me")
def get_my_badges(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return success_response(TrustService(db).get_user_badges(user_id))


@router.get("/skills")
def list_skills(_: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return success_response(TrustService(db).list_skills_catalog())


@router.get("/skills/me")
def get_my_skills(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return success_response(TrustService(db).get_user_skills(user_id))


@router.get("/reviews/me")
def get_my_reviews(
    review_type: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return success_response({
        "summary": RatingService(db).get_public_rating_summary(user_id),
        "reviews": RatingService(db).list_user_reviews(user_id, review_type=review_type, limit=50),
    })


@router.get("/reviews/{user_id}")
def get_user_reviews(
    user_id: str,
    review_type: str | None = None,
    _: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rating_service = RatingService(db)
    return success_response({
        "summary": rating_service.get_public_rating_summary(user_id),
        "reviews": rating_service.list_user_reviews(user_id, review_type=review_type, limit=50),
    })


class AddSkillPayload(BaseModel):
    skill_id: str
    level: str = Field(default="BEGINNER", pattern="^(BEGINNER|INTERMEDIATE|EXPERT)$")


@router.post("/skills/me")
def add_my_skill(
    payload: AddSkillPayload,
    user_id: str = Depends(require_verified_user),
    db: Session = Depends(get_db),
    _: None = Depends(_skill_write_limit),
):
    try:
        result = TrustService(db).add_skill(user_id, payload.skill_id, payload.level)
        return success_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/skills/me/{user_skill_id}")
def remove_my_skill(
    user_skill_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        TrustService(db).remove_skill(user_id, user_skill_id)
        return success_response({"removed": True})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class ReportContentPayload(BaseModel):
    content_type: str = Field(pattern="^(profile|task|chat|review)$")
    reason: str = Field(min_length=10, max_length=512)
    reported_user_id: str | None = None
    content_id: str | None = None


@router.post("/report")
def report_content(
    payload: ReportContentPayload,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_verified_user),
    db: Session = Depends(get_db),
    _: None = Depends(_report_limit),
):
    """Report content for moderation.

    Returns immediately with rule-based severity. AI enrichment runs in background
    and updates the case within seconds without blocking the HTTP response.
    """
    from app.services.moderation_service import ModerationService
    try:
        svc = ModerationService(db)
        case = svc.report_content_sync(
            reporter_id=user_id,
            content_type=payload.content_type,
            reason=payload.reason,
            reported_user_id=payload.reported_user_id,
            content_id=payload.content_id,
        )
        background_tasks.add_task(
            ModerationService.enrich_with_ai,
            case.id,
            payload.reason,
            payload.content_type,
        )
        return success_response({"caseId": case.id, "severity": case.severity})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Signalement échoué") from exc
