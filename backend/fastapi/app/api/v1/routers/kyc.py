import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user_id, get_kyc_service
from app.core.config import settings
from app.core.responses import success_response
from app.services.kyc_service import KycService

router = APIRouter(prefix="/kyc", tags=["kyc"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _serialize(kyc) -> dict:
    return {
        "id": kyc.id,
        "status": kyc.status,
        "reviewerNote": kyc.reviewer_note,
        "reviewedAt": kyc.reviewed_at.isoformat() if kyc.reviewed_at else None,
        "createdAt": kyc.created_at.isoformat(),
    }


async def _save_upload(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type (JPEG, PNG or WebP only)")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail=f"File too large (max {settings.max_upload_bytes // 1_000_000} MB)")
    upload_dir = os.path.join("backend", "fastapi", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}-{file.filename}"
    path = os.path.join(upload_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path


@router.post("/submit")
async def submit_kyc(
    id_document: UploadFile = File(..., description="ID card or passport (JPEG/PNG/WebP)"),
    selfie: UploadFile = File(..., description="Selfie holding the document (JPEG/PNG/WebP)"),
    service: KycService = Depends(get_kyc_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        id_path = await _save_upload(id_document)
        selfie_path = await _save_upload(selfie)
        kyc = service.create_submission(user_id=user_id, id_document_url=id_path, selfie_url=selfie_path)
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
