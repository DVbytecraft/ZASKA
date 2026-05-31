from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.responses import success_response
from app.models.user import User
from app.schemas.user import UpdateProfilePayload, UserProfileResponse

router = APIRouter(prefix="/users", tags=["users"])


class UpdateEnrichedProfilePayload(BaseModel):
    bio: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=64)
    availability: str | None = Field(default=None, pattern="^(full_time|part_time|weekends|evenings|on_demand)?$")
    hourly_rate: float | None = Field(default=None, ge=0, le=10000)
    response_time: str | None = Field(default=None, pattern="^(within_1h|within_4h|within_24h|within_48h)?$")


def _user_response(user: User) -> dict:
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        country_code=user.country_code,
        is_verified=user.is_verified,
    ).model_dump()


@router.get("/me")
def get_me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalars().one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = _user_response(user)
    # Enrich with trust score, skills and badges
    try:
        from app.services.trust_service import TrustService
        svc = TrustService(db)
        ts = svc.get_trust_score(user_id)
        if ts:
            data["trustScore"] = {
                "totalScore": ts.total_score,
                "level": ts.level,
                "computedAt": ts.computed_at.isoformat(),
            }
        data["skills"] = svc.get_user_skills(user_id)
        data["badges"] = svc.get_user_badges(user_id)
    except Exception:
        pass
    # Enriched profile fields
    data["bio"]          = getattr(user, "bio", None)
    data["city"]         = getattr(user, "city", None)
    data["availability"] = getattr(user, "availability", None)
    data["hourlyRate"]   = getattr(user, "hourly_rate", None)
    data["responseTime"] = getattr(user, "response_time", None)
    return success_response(data)


@router.get("/{user_id}/history")
def get_user_history(
    user_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return paginated list of completed tasks for a user (as tasker).

    Shows public task history — title, completion date, and rating received.
    """
    from app.models.task import Task
    user = db.execute(select(User).where(User.id == user_id)).scalars().one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    offset = (page - 1) * limit
    tasks = db.execute(
        select(Task)
        .where(Task.assigned_to == user_id, Task.status == "COMPLETED")
        .order_by(Task.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    total = db.execute(
        select(__import__("sqlalchemy").func.count(Task.id))
        .where(Task.assigned_to == user_id, Task.status == "COMPLETED")
    ).scalar() or 0

    return success_response({
        "user_id": user_id,
        "total": total,
        "page": page,
        "limit": limit,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "city": t.city,
                "country": t.country,
                "currency": t.currency,
                "price": float(t.price),
                "completed_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
    })


@router.get("/{user_id}")
def get_user_public(
    user_id: str,
    _: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return enriched public profile: name, avatar, trust score, skills, badges, bio."""
    user = db.execute(select(User).where(User.id == user_id)).scalars().one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    data: dict = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "bio": getattr(user, "bio", None),
        "city": getattr(user, "city", None),
        "availability": getattr(user, "availability", None),
        "hourly_rate": getattr(user, "hourly_rate", None),
        "response_time": getattr(user, "response_time", None),
        "rating_avg": round(user.rating_sum / user.rating_count, 2) if user.rating_count > 0 else None,
        "rating_count": user.rating_count,
        "member_since": user.created_at.isoformat(),
    }

    try:
        from app.services.trust_service import TrustService
        svc = TrustService(db)
        ts = svc.get_trust_score(user_id)
        if ts:
            data["trustScore"] = {
                "totalScore": ts.total_score,
                "level": ts.level,
                "computedAt": ts.computed_at.isoformat(),
            }
        data["skills"] = svc.get_user_skills(user_id)
        data["badges"] = svc.get_user_badges(user_id)
    except Exception:
        data["skills"] = []
        data["badges"] = []

    return success_response(data)


@router.patch("/me/profile")
def update_enriched_profile(
    payload: UpdateEnrichedProfilePayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update enriched profile fields: bio, city, availability, hourly_rate, response_time."""
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalars().one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.bio is not None:
        user.bio = payload.bio.strip() or None
    if payload.city is not None:
        user.city = payload.city.strip() or None
    if payload.availability is not None:
        user.availability = payload.availability or None
    if payload.hourly_rate is not None:
        user.hourly_rate = payload.hourly_rate
    if payload.response_time is not None:
        user.response_time = payload.response_time or None

    db.commit()
    db.refresh(user)

    return success_response({
        "id": user.id,
        "bio": user.bio,
        "city": user.city,
        "availability": user.availability,
        "hourlyRate": user.hourly_rate,
        "responseTime": user.response_time,
    })


@router.patch("/me")
def update_me(
    payload: UpdateProfilePayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # FOR UPDATE: prevents two concurrent PATCH /users/me requests (multi-device)
    # from reading the same user state and both writing conflicting values.
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalars().one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.first_name is not None:
        user.first_name = payload.first_name.strip() or None
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip() or None
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    elif payload.first_name is not None or payload.last_name is not None:
        fn = (user.first_name or "").strip()
        ln = (user.last_name or "").strip()
        user.full_name = f"{fn} {ln}".strip() or None
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    db.commit()
    db.refresh(user)
    return success_response(_user_response(user))
