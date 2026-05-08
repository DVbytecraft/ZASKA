from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_chat_service, get_current_user_id, get_db
from app.core.responses import success_response
from app.models.task import Task
from app.models.user import User
from app.schemas.chat import ChatMessagePayload
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def _format_message(msg) -> dict:
    return {
        "id": msg.id,
        "taskId": msg.task_id,
        "senderId": msg.sender_id,
        "message": msg.message,
        "createdAt": msg.created_at.isoformat(),
    }


@router.get("/{task_id}")
def list_messages(task_id: str, service: ChatService = Depends(get_chat_service), user_id: str = Depends(get_current_user_id)):
    try:
        service.assert_participant(task_id, user_id)
        messages = service.list_messages(task_id)
        return success_response([_format_message(m) for m in messages])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to load messages") from exc


@router.post("")
def create_message(
    payload: ChatMessagePayload,
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        service.assert_participant(payload.task_id, user_id)
        msg = service.create_message(payload.task_id, user_id, payload.message)

        # Notify the other participant by email (best-effort)
        try:
            from app.core.email import send_message_notification_email
            task = db.get(Task, payload.task_id)
            if task:
                recipient_id = task.assigned_to if task.created_by == user_id else task.created_by
                if recipient_id:
                    recipient = db.get(User, recipient_id)
                    sender = db.get(User, user_id)
                    if recipient and recipient.email:
                        sender_name = " ".join(filter(None, [sender.first_name, sender.last_name])) if sender else "ZASKA"
                        send_message_notification_email(
                            to_email=recipient.email,
                            task_title=task.title,
                            sender_name=sender_name or "ZASKA",
                            message_preview=payload.message,
                        )
        except Exception:
            pass

        return success_response(_format_message(msg))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to send message") from exc
