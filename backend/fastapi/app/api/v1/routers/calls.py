from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.api.websocket import user_call_notification_manager
from app.core.responses import success_response
from app.core.ws_ticket import create_ws_ticket
from app.models.call_session import CallSession
from app.models.task import Task
from app.models.user import User
from app.schemas.call import InitiateCallRequest, WsTicketResponse

router = APIRouter(prefix="/calls", tags=["calls"])


def _get_callee(task: Task, caller_id: str) -> str:
    if task.created_by == caller_id:
        if not task.assigned_to:
            raise HTTPException(status_code=409, detail="No tasker assigned to this task yet")
        return task.assigned_to
    if task.assigned_to == caller_id:
        return task.created_by
    raise HTTPException(status_code=403, detail="You are not a participant of this task")


# ── IMPORTANT: fixed-path routes must come BEFORE parameterised routes ─────────

@router.post("/user/ws-ticket")
def get_user_notification_ws_ticket(
    user_id: str = Depends(get_current_user_id),
):
    """One-time ticket for the user call-notification WebSocket."""
    ticket = create_ws_ticket(user_id, task_id=user_id)
    return success_response(WsTicketResponse(ticket=ticket).model_dump())


# ── Parameterised routes below ────────────────────────────────────────────────

@router.post("")
async def initiate_call(
    body: InitiateCallRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    task = db.get(Task, body.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    callee_id = _get_callee(task, user_id)

    session = CallSession(
        task_id=body.task_id,
        caller_id=user_id,
        callee_id=callee_id,
        media_type=body.media_type,
        status="pending",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    caller = db.get(User, user_id)
    caller_name = (
        " ".join(filter(None, [caller.first_name, caller.last_name])) if caller else "ZASKA"
    )
    caller_avatar: str | None = getattr(caller, "avatar_url", None)

    callee_online = await user_call_notification_manager.notify(
        callee_id,
        {
            "type": "incoming_call",
            "call_id": session.id,
            "caller_name": caller_name,
            "caller_avatar": caller_avatar,
            "media_type": body.media_type,
            "task_id": body.task_id,
        },
    )

    if not callee_online:
        # Callee is not connected — mark the session as missed immediately
        # so the caller can display a "user offline" message instead of
        # an infinite ringing screen.
        session.status = "missed"
        db.commit()

    return success_response({
        "call_id": session.id,
        "callee_id": callee_id,
        "callee_online": callee_online,
    })


@router.post("/{call_id}/answer")
def answer_call(
    call_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = db.get(CallSession, call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Call not found")
    if session.callee_id != user_id:
        raise HTTPException(status_code=403, detail="Not the callee")
    if session.status != "pending":
        raise HTTPException(status_code=409, detail=f"Call already {session.status}")
    session.status = "active"
    session.answered_at = datetime.now(timezone.utc)
    db.commit()
    return success_response({"call_id": call_id, "status": "active"})


@router.post("/{call_id}/end")
def end_call(
    call_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = db.get(CallSession, call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Call not found")
    if user_id not in (session.caller_id, session.callee_id):
        raise HTTPException(status_code=403, detail="Not a call participant")
    new_status = "rejected" if session.status == "pending" else "ended"
    session.status = new_status
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    return success_response({"call_id": call_id, "status": new_status})


@router.post("/{call_id}/ws-ticket")
def get_call_ws_ticket(
    call_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """One-time ticket for the call signaling WebSocket."""
    session = db.get(CallSession, call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Call not found")
    if user_id not in (session.caller_id, session.callee_id):
        raise HTTPException(status_code=403, detail="Not a call participant")
    ticket = create_ws_ticket(user_id, task_id=call_id)
    return success_response(WsTicketResponse(ticket=ticket).model_dump())
