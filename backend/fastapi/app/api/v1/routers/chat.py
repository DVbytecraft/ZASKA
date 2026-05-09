from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_chat_service, get_current_user_id, get_db
from app.core.cloudinary_client import (
    ALLOWED_CHAT_TYPES,
    chat_size_limit,
    is_configured,
    upload_chat_media,
)
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
        "mediaUrl": getattr(msg, "media_url", None),
        "mediaType": getattr(msg, "media_type", None),
        "createdAt": msg.created_at.isoformat(),
    }


@router.get("/{task_id}")
def list_messages(
    task_id: str,
    service: ChatService = Depends(get_chat_service),
    user_id: str = Depends(get_current_user_id),
):
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


@router.post("/upload")
async def upload_media(
    task_id: str = Form(...),
    file: UploadFile = File(...),
    service: ChatService = Depends(get_chat_service),
    user_id: str = Depends(get_current_user_id),
):
    """
    Upload a media file (image / video / document) for use in chat.
    Returns { secure_url, media_type } to be included in the next POST /chat call.
    Cloudinary must be configured; otherwise returns 503.
    """
    if not is_configured():
        raise HTTPException(status_code=503, detail="Media upload not available — Cloudinary not configured")

    # Verify sender is a participant
    try:
        service.assert_participant(task_id, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_CHAT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{content_type}' not allowed. Allowed: {', '.join(sorted(ALLOWED_CHAT_TYPES))}",
        )

    data = await file.read()
    size_limit = chat_size_limit(content_type)
    if len(data) > size_limit:
        limit_mb = size_limit // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File too large. Limit: {limit_mb} MB for {content_type}")

    try:
        result = await upload_chat_media(data, content_type, task_id, user_id)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upload failed: {exc}") from exc


@router.post("")
def create_message(
    payload: ChatMessagePayload,
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # Require at least a text message OR a media attachment
    if not payload.message.strip() and not payload.media_url:
        raise HTTPException(status_code=422, detail="Message or media attachment required")

    try:
        service.assert_participant(payload.task_id, user_id)
        msg = service.create_message(
            payload.task_id,
            user_id,
            payload.message,
            media_url=payload.media_url,
            media_type=payload.media_type,
        )

        # In-app notification to the other participant (best-effort)
        try:
            from app.models.notification import Notification
            task = db.get(Task, payload.task_id)
            if task:
                recipient_id = task.assigned_to if task.created_by == user_id else task.created_by
                if recipient_id:
                    sender = db.get(User, user_id)
                    sender_name = " ".join(filter(None, [sender.first_name, sender.last_name])) if sender else "ZASKA"
                    if payload.media_url:
                        preview = f"[{payload.media_type or 'fichier'}] {payload.message[:60]}".strip()
                    else:
                        preview = payload.message[:80] + ("…" if len(payload.message) > 80 else "")
                    notif = Notification(
                        user_id=recipient_id,
                        type="info",
                        title=f"Message de {sender_name or 'ZASKA'}",
                        body=f"{task.title} — {preview}",
                        task_id=payload.task_id,
                    )
                    db.add(notif)
                    db.flush()
        except Exception:
            pass

        return success_response(_format_message(msg))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to send message") from exc
