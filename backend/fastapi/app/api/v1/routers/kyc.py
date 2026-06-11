import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db, get_kyc_service, require_admin
from app.core.cloudinary_client import is_configured, upload_kyc_document
from app.core.config import settings
from app.core.rate_limit import endpoint_rate_limit
from app.core.responses import success_response
from app.models.user import User
from app.services.kyc_service import KycService

router = APIRouter(prefix="/kyc", tags=["kyc"])

# 3 photo verification attempts per hour per IP — prevents Rekognition cost abuse
_photo_verify_limit = endpoint_rate_limit("kyc:photo", max_requests=3, window_seconds=3600)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _serialize(kyc) -> dict:
    days_remaining = None
    if kyc.expires_at:
        delta = kyc.expires_at - datetime.now(timezone.utc)
        days_remaining = delta.days
    return {
        "id": kyc.id,
        "status": kyc.status,
        "submissionKind": getattr(kyc, "submission_kind", "full"),
        "idDocumentType": getattr(kyc, "id_document_type", None),
        "idDocumentNumberMasked": getattr(kyc, "id_document_number_masked", None),
        "documentCountryCode": getattr(kyc, "document_country_code", None),
        "biometricStatus": getattr(kyc, "biometric_status", None),
        "ocrStatus": getattr(kyc, "ocr_status", None),
        "criminalRecordStatus": getattr(kyc, "criminal_record_status", None),
        "criminalRecordRiskLevel": getattr(kyc, "criminal_record_risk_level", None),
        "criminalRecordIssuedAt": kyc.criminal_record_issued_at.isoformat() if getattr(kyc, "criminal_record_issued_at", None) else None,
        "criminalRecordExpiresAt": kyc.criminal_record_expires_at.isoformat() if getattr(kyc, "criminal_record_expires_at", None) else None,
        "reviewerNote": kyc.reviewer_note,
        "reviewedAt": kyc.reviewed_at.isoformat() if kyc.reviewed_at else None,
        "approvedAt": kyc.approved_at.isoformat() if kyc.approved_at else None,
        "expiresAt": kyc.expires_at.isoformat() if kyc.expires_at else None,
        "isExpired": kyc.is_expired,
        "daysRemaining": days_remaining,
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
    id_document_back: UploadFile = File(..., description="Back of ID card or passport support page (JPEG/PNG/WebP/PDF)"),
    selfie: UploadFile = File(..., description="Selfie holding the document (JPEG/PNG/WebP)"),
    criminal_record: UploadFile = File(..., description="Criminal record extract (JPEG/PNG/WebP/PDF)"),
    biometric_selfie: UploadFile | None = File(default=None, description="Live biometric selfie (JPEG/PNG/WebP)"),
    submission_kind: str = Form(default="full"),
    id_document_type: str | None = Form(default=None),
    id_document_number_masked: str | None = Form(default=None),
    document_country_code: str | None = Form(default=None),
    criminal_record_issued_at: str | None = Form(default=None),
    service: KycService = Depends(get_kyc_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        id_url = await _upload_file(id_document, "id_document")
        id_back_url = await _upload_file(id_document_back, "id_document_back")
        selfie_url = await _upload_file(selfie, "selfie")
        criminal_record_url = await _upload_file(criminal_record, "criminal_record")
        biometric_selfie_url = await _upload_file(biometric_selfie, "biometric_selfie") if biometric_selfie else None
        issued_at = datetime.fromisoformat(criminal_record_issued_at) if criminal_record_issued_at else None
        kyc = service.create_submission(
            user_id=user_id,
            id_document_url=id_url,
            id_document_back_url=id_back_url,
            selfie_url=selfie_url,
            biometric_selfie_url=biometric_selfie_url,
            criminal_record_url=criminal_record_url,
            submission_kind=submission_kind,
            id_document_type=id_document_type,
            id_document_number_masked=id_document_number_masked,
            document_country_code=document_country_code,
            criminal_record_issued_at=issued_at,
            metadata={
                "submittedAt": datetime.now(timezone.utc).isoformat(),
                "route": "advanced_submit",
            },
        )

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


@router.get("/renewal-prefill")
def get_renewal_prefill(
    service: KycService = Depends(get_kyc_service),
    user_id: str = Depends(get_current_user_id),
):
    return success_response(service.get_renewal_prefill(user_id))


class ReviewPayload(BaseModel):
    note: str | None = None


@router.post("/{submission_id}/approve")
def approve_kyc(
    submission_id: str,
    payload: ReviewPayload,
    service: KycService = Depends(get_kyc_service),
    user_id: str = Depends(require_admin),
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
    user_id: str = Depends(require_admin),
):
    try:
        kyc = service.reject(submission_id=submission_id, reviewer_id=user_id, note=payload.note)
        return success_response(_serialize(kyc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to reject KYC") from exc


# ── Photo Verification (selfie liveness) ──────────────────────────────────────

def _pv_serialize(pv) -> dict:
    return {
        "id": pv.id,
        "status": pv.status,
        "livenessScore": pv.liveness_score,
        "provider": pv.provider,
        "verificationCapability": "face_detection_only",
        "warning": (
            "Cette vérification détecte la présence d'un visage mais ne constitue pas "
            "une vérification de vivacité (liveness). Ne pas utiliser pour des opérations "
            "à risque élevé sans vérification supplémentaire."
        ),
        "reviewedAt": pv.reviewed_at.isoformat() if pv.reviewed_at else None,
        "createdAt": pv.created_at.isoformat(),
    }


@router.post("/photo-verification")
async def submit_photo_verification(
    selfie: UploadFile = File(..., description="Selfie photo (JPEG/PNG/WebP)"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(_photo_verify_limit),
):
    """Upload a selfie for face presence verification.

    Uses AWS Rekognition detect_faces if configured, mock otherwise.
    NOTE: This verifies face presence, not true liveness — upgrade to
    FaceLiveness API or a dedicated liveness provider for production.
    """
    SELFIE_TYPES = {"image/jpeg", "image/png", "image/webp"}
    if selfie.content_type not in SELFIE_TYPES:
        raise HTTPException(status_code=400, detail="Selfie must be JPEG, PNG or WebP")

    data = await selfie.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Selfie too large (max {settings.max_upload_bytes // 1_000_000} MB)",
        )

    if not is_configured():
        raise HTTPException(status_code=503, detail="Storage not configured — contact support")

    selfie_url = await upload_kyc_document(data, selfie.content_type, f"selfie-{uuid.uuid4()}")

    try:
        from app.services.photo_verification_service import PhotoVerificationService
        pv_svc = PhotoVerificationService(db)
        # Run blocking Rekognition/boto3 call in a thread so it doesn't starve the event loop
        pv = await asyncio.to_thread(pv_svc.submit, user_id, selfie_url)

        # Recompute trust score to award PHOTO_VERIFIED badge if applicable
        if pv.status == "VERIFIED":
            try:
                from app.services.trust_service import TrustService
                TrustService(db).compute_for_user(user_id)
            except Exception:
                pass

        return success_response(_pv_serialize(pv))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Photo verification failed") from exc


@router.get("/photo-verification/me")
def get_photo_verification_status(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    from app.services.photo_verification_service import PhotoVerificationService
    pv = PhotoVerificationService(db).get_status(user_id)
    if pv is None:
        return success_response({"status": "not_submitted"})
    return success_response(_pv_serialize(pv))
