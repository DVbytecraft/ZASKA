from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chat_service, get_current_user_id
from app.core.responses import success_response
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
    user_id: str = Depends(get_current_user_id),
):
    try:
        service.assert_participant(payload.task_id, user_id)
        msg = service.create_message(payload.task_id, user_id, payload.message)
        return success_response(_format_message(msg))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to send message") from exc
