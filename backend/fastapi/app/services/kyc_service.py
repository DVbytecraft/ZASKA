import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.email import send_kyc_expired_email, send_kyc_expiry_warning_email
from app.core.observability import logger
from app.models.kyc import KYC_VALIDITY_DAYS, KycSubmission
from app.models.notification import Notification
from app.models.user import User


class KycService:
    def __init__(self, db: Session):
        self.db = db

    def create_submission(
        self,
        user_id: str,
        id_document_url: str,
        selfie_url: str,
        *,
        id_document_back_url: str | None = None,
        biometric_selfie_url: str | None = None,
        criminal_record_url: str | None = None,
        submission_kind: str = "full",
        id_document_type: str | None = None,
        id_document_number_masked: str | None = None,
        document_country_code: str | None = None,
        criminal_record_issued_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> KycSubmission:
        logger.info("kyc_submission_created user_id={}", user_id)
        previous = self.get_status(user_id)
        normalized_kind = submission_kind if submission_kind in {"full", "renewal"} else "full"
        now = datetime.now(timezone.utc)
        item = KycSubmission(
            user_id=user_id,
            id_document_url=id_document_url,
            id_document_back_url=id_document_back_url,
            selfie_url=selfie_url,
            submission_kind=normalized_kind,
            id_document_type=id_document_type,
            id_document_number_masked=id_document_number_masked,
            document_country_code=document_country_code,
            biometric_selfie_url=biometric_selfie_url,
            biometric_status="pending" if biometric_selfie_url else "missing",
            ocr_status="pending",
            criminal_record_url=criminal_record_url,
            criminal_record_status="pending" if criminal_record_url else "missing",
            criminal_record_issued_at=criminal_record_issued_at,
            criminal_record_expires_at=(criminal_record_issued_at + timedelta(days=KYC_VALIDITY_DAYS)) if criminal_record_issued_at else None,
            criminal_record_risk_level="pending",
            renewal_of_submission_id=(previous.id if previous and normalized_kind == "renewal" else None),
            metadata_json=json.dumps(metadata) if metadata is not None else None,
            status="pending",
        )
        self._apply_simulated_analysis(item)
        if normalized_kind == "renewal":
            self._prefill_from_previous(item, previous)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        user = self.db.get(User, user_id)
        if user is not None:
            user.tasker_security_verified = False
            self.db.commit()
        return item

    def get_status(self, user_id: str) -> KycSubmission | None:
        return (
            self.db.execute(
                select(KycSubmission)
                .where(KycSubmission.user_id == user_id)
                .order_by(KycSubmission.created_at.desc())
            )
            .scalars()
            .first()
        )

    def approve(self, submission_id: str, reviewer_id: str, note: str | None = None) -> KycSubmission:
        sub = self._get_or_404(submission_id)
        self._ensure_submission_complete(sub)
        now = datetime.now(timezone.utc)
        if sub.criminal_record_risk_level == "high":
            raise ValueError("Le casier judiciaire présente un niveau de risque élevé et ne peut pas être approuvé.")
        sub.status = "approved"
        sub.reviewed_by = reviewer_id
        sub.reviewed_at = now
        sub.approved_at = now
        sub.expires_at = now + timedelta(days=KYC_VALIDITY_DAYS)
        sub.reviewer_note = note
        sub.ocr_status = "reviewed"
        if sub.biometric_selfie_url and sub.biometric_status in {"pending", "missing"}:
            sub.biometric_status = "approved"
        if sub.criminal_record_url and sub.criminal_record_status in {"pending", "missing"}:
            sub.criminal_record_status = "approved"
        if sub.criminal_record_risk_level == "pending":
            sub.criminal_record_risk_level = "low"
        user = self.db.get(User, sub.user_id)
        if user is not None:
            user.is_suspended = False
            user.suspension_reason = None
            user.criminal_record_status = "approved"
            user.biometric_enabled = bool(user.biometric_enabled or sub.biometric_selfie_url)
            user.tasker_security_verified = bool(
                sub.status == "approved"
                and user.criminal_record_status in {"approved", "clear"}
                and user.biometric_enabled
            )
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def reject(self, submission_id: str, reviewer_id: str, note: str | None = None) -> KycSubmission:
        sub = self._get_or_404(submission_id)
        sub.status = "rejected"
        sub.reviewed_by = reviewer_id
        sub.reviewed_at = datetime.now(timezone.utc)
        sub.reviewer_note = note
        user = self.db.get(User, sub.user_id)
        if user is not None:
            user.tasker_security_verified = False
            user.criminal_record_status = "rejected" if sub.criminal_record_url else user.criminal_record_status
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def get_renewal_prefill(self, user_id: str) -> dict:
        current = self.get_status(user_id)
        if current is None:
            return {"status": "not_submitted"}
        return {
            "status": current.status,
            "submissionKind": "renewal",
            "idDocumentType": current.id_document_type,
            "idDocumentNumberMasked": current.id_document_number_masked,
            "documentCountryCode": current.document_country_code,
            "criminalRecordStatus": current.criminal_record_status,
            "biometricStatus": current.biometric_status,
            "expiresAt": current.expires_at.isoformat() if current.expires_at else None,
            "metadata": current.metadata_payload,
        }

    def process_lifecycle(self, reference_date: datetime | None = None) -> dict[str, int]:
        now = reference_date or datetime.now(timezone.utc)
        result = {
            "reminders_30d": 0,
            "reminders_7d": 0,
            "expired": 0,
            "reactivated": 0,
        }
        submissions = (
            self.db.execute(
                select(KycSubmission).where(
                    KycSubmission.status == "approved",
                    KycSubmission.expires_at.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        for sub in submissions:
            user = self.db.get(User, sub.user_id)
            if user is None or sub.expires_at is None:
                continue
            days_remaining = (sub.expires_at.date() - now.date()).days
            if days_remaining == 30:
                if self._notify_once_per_day(user.id, "warning", "KYC à renouveler", now):
                    self._create_notification(
                        user_id=user.id,
                        notif_type="warning",
                        title="KYC à renouveler",
                        body="Votre KYC expire dans 30 jours. Renouvelez-le pour continuer à accepter des tâches.",
                    )
                    if user.email:
                        send_kyc_expiry_warning_email(user.email, days_remaining=30)
                    result["reminders_30d"] += 1
            elif 0 < days_remaining <= 7:
                if self._notify_once_per_day(user.id, "warning", "Rappel KYC", now):
                    self._create_notification(
                        user_id=user.id,
                        notif_type="warning",
                        title="Rappel KYC",
                        body=f"Votre KYC expire dans {days_remaining} jour(s). Renouvelez-le dès maintenant.",
                    )
                    if user.email:
                        send_kyc_expiry_warning_email(user.email, days_remaining=days_remaining)
                    result["reminders_7d"] += 1
            elif days_remaining < 0:
                changed = False
                if not sub.is_expired:
                    continue
                if user.role == "tasker" and not user.is_suspended:
                    user.is_suspended = True
                    user.suspension_reason = "KYC expiré — renouvellement requis"
                    user.tasker_security_verified = False
                    changed = True
                if self._notify_once_per_day(user.id, "error", "KYC expiré", now):
                    self._create_notification(
                        user_id=user.id,
                        notif_type="error",
                        title="KYC expiré",
                        body="Votre KYC a expiré. Renouvelez-le pour réactiver votre accès aux tâches.",
                    )
                    if user.email:
                        send_kyc_expired_email(user.email)
                    changed = True
                if changed:
                    self.db.commit()
                    result["expired"] += 1
            elif user.role == "tasker" and user.is_suspended and not sub.is_expired:
                user.is_suspended = False
                user.suspension_reason = None
                user.tasker_security_verified = bool(
                    sub.status == "approved"
                    and getattr(sub, "biometric_status", "pending") in {"approved", "clear"}
                    and getattr(sub, "criminal_record_status", "pending") in {"approved", "clear"}
                )
                self.db.commit()
                result["reactivated"] += 1
        return result

    def _get_or_404(self, submission_id: str) -> KycSubmission:
        sub = self.db.get(KycSubmission, submission_id)
        if sub is None:
            raise ValueError(f"KYC submission {submission_id} not found")
        return sub

    def _notify_once_per_day(self, user_id: str, notif_type: str, title: str, now: datetime) -> bool:
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        existing = (
            self.db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.type == notif_type,
                    Notification.title == title,
                    Notification.created_at >= start_of_day,
                )
            )
            .scalars()
            .first()
        )
        return existing is None

    def _create_notification(self, user_id: str, notif_type: str, title: str, body: str) -> None:
        self.db.add(Notification(user_id=user_id, type=notif_type, title=title, body=body))
        self.db.commit()

    def _ensure_submission_complete(self, sub: KycSubmission) -> None:
        missing: list[str] = []
        if not sub.id_document_url:
            missing.append("document d'identité recto")
        if not sub.id_document_back_url:
            missing.append("document d'identité verso")
        if not sub.selfie_url:
            missing.append("selfie")
        if not sub.criminal_record_url:
            missing.append("casier judiciaire")
        if missing:
            raise ValueError("Dossier KYC incomplet: " + ", ".join(missing))

    def _prefill_from_previous(self, item: KycSubmission, previous: KycSubmission | None) -> None:
        if previous is None:
            return
        if item.id_document_type is None:
            item.id_document_type = previous.id_document_type
        if item.id_document_number_masked is None:
            item.id_document_number_masked = previous.id_document_number_masked
        if item.document_country_code is None:
            item.document_country_code = previous.document_country_code
        if item.metadata_json is None:
            item.metadata_json = previous.metadata_json

    def _apply_simulated_analysis(self, item: KycSubmission) -> None:
        if item.criminal_record_url:
            item.criminal_record_status = "pending_review"
            item.criminal_record_risk_level = "pending"
            item.criminal_record_analysis_json = json.dumps(
                {
                    "provider": "simulated",
                    "status": "pending_review",
                    "notes": "Analyse OCR/NLP à brancher sur un provider dédié.",
                }
            )
        if item.biometric_selfie_url:
            item.biometric_status = "pending_review"
        item.ocr_status = "pending_review"
        item.ocr_payload_json = json.dumps(
            {
                "provider": "simulated",
                "status": "pending_review",
                "extracted": {
                    "idDocumentType": item.id_document_type,
                    "idDocumentNumberMasked": item.id_document_number_masked,
                    "documentCountryCode": item.document_country_code,
                },
            }
        )
