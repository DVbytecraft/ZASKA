from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.responses import success_response
from app.models.user import User
from app.schemas.user import UpdateProfilePayload, UserProfileResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success_response(UserProfileResponse(
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
    ).model_dump())


@router.patch("/me")
def update_me(
    payload: UpdateProfilePayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).one_or_none()
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
    return success_response(UserProfileResponse(
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
    ).model_dump())
