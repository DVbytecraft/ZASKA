"""Notifications in-app — liste et marquage lu."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.responses import success_response
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "read": n.read,
        "created_at": n.created_at.isoformat(),
    }


@router.get("")
def list_notifications(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        notifs = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(50)
            .all()
        )
        return success_response([_serialize(n) for n in notifs])
    except (OperationalError, ProgrammingError):
        # Migration hasn't run yet — return empty list rather than crashing
        db.rollback()
        return success_response([])


@router.patch("/{notif_id}/read")
def mark_read(
    notif_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    notif = db.query(Notification).filter(
        Notification.id == notif_id, Notification.user_id == user_id
    ).one_or_none()
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    notif.read = True
    db.commit()
    return success_response(_serialize(notif))


@router.post("/mark-all-read")
def mark_all_read(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == user_id, Notification.read == False  # noqa: E712
    ).update({"read": True})
    db.commit()
    return success_response({"marked": True})
