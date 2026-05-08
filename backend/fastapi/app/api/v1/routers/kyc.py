import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user_id, get_db, get_kyc_service
from app.core.cloudinary_client import is_configured, upload_kyc_document
from app.core.config import settings
from app.core.responses import success_response
from app.models.user import User
from app.services.kyc_service import KycService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/kyc", tags=["kyc"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _serialize(kyc) -> dict:
    return {
        "id": kyc.id,
        "status": kyc.status,
        "reviewerNote": kyc.reviewer_note,
        "reviewedAt": kyc.reviewed_at.isoformat() if kyc.reviewed_at else None,
        "createdAt": kyc.created_at.isoformat(),
    }


async def _upload_file(file: UploadFile, label: str) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"{label}: unsupported file type (JPEG, PNG, WebP or PDF only)",
        )
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"{label}: file too large (max {settings.max_upload_bytes // 1_000_000} MB)",
        )
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Document storage not configured — contact support",
        )
    public_id = f"{label}-{uuid.uuid4()}"
    return await upload_kyc_document(data, file.content_type, public_id)


@router.post("/submit")
async def submit_kyc(
    id_document: UploadFile = File(..., description="ID card or passport (JPEG/PNG/WebP/PDF)"),
    selfie: UploadFile = File(..., description="Selfie holding the document (JPEG/PNG/WebP)"),
    service: KycService = Depends(get_kyc_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        id_url = await _upload_file(id_document, "id_document")
        selfie_url = await _upload_file(selfie, "selfie")
        kyc = service.create_submission(user_id=user_id, id_document_url=id_url, selfie_url=selfie_url)

        # Alert all configured admins
        try:
            from app.core.email import send_kyc_review_email
            user_obj = db.get(User, user_id)
            display_name = " ".join(filter(None, [user_obj.first_name, user_obj.last_name])) if user_obj else user_id
            for admin_email in settings.admin_email_list:
                send_kyc_review_email(
                    admin_email=admin_email,
                    user_display_name=display_name or user_id,
                    user_email=user_obj.email if user_obj else None,
                    user_id=user_id,
                )
        except Exception:
            pass

        return success_response(_serialize(kyc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to submit KYC") from exc


@router.get("/status")
def get_kyc_status(
    service: KycService = Depends(get_kyc_service),
    user_id: str = Depends(get_current_user_id),
):
    kyc = service.get_status(user_id)
    if kyc is None:
        return success_response({"status": "not_submitted"})
    return success_response(_serialize(kyc))


class ReviewPayload(BaseModel):
    note: str | None = None


@router.post("/{submission_id}/approve")
def approve_kyc(
    submission_id: str,
    payload: ReviewPayload,
    service: KycService = Depends(get_kyc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        kyc = service.approve(submission_id=submission_id, reviewer_id=user_id, note=payload.note)
        return success_response(_serialize(kyc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to approve KYC") from exc


@router.post("/{submission_id}/reject")
def reject_kyc(
    submission_id: str,
    payload: ReviewPayload,
    service: KycService = Depends(get_kyc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        kyc = service.reject(submission_id=submission_id, reviewer_id=user_id, note=payload.note)
        return success_response(_serialize(kyc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to reject KYC") from exc
