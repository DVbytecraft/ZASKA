from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import logger
from app.models.kyc import KYC_VALIDITY_DAYS, KycSubmission


class KycService:
    def __init__(self, db: Session):
        self.db = db

    def create_submission(self, user_id: str, id_document_url: str, selfie_url: str) -> KycSubmission:
        logger.info("kyc_submission_created user_id={}", user_id)
        item = KycSubmission(
            user_id=user_id,
            id_document_url=id_document_url,
            selfie_url=selfie_url,
            status="pending",
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
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
        now = datetime.now(timezone.utc)
        sub.status = "approved"
        sub.reviewed_by = reviewer_id
        sub.reviewed_at = now
        sub.approved_at = now
        sub.expires_at = now + timedelta(days=KYC_VALIDITY_DAYS)
        sub.reviewer_note = note
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def reject(self, submission_id: str, reviewer_id: str, note: str | None = None) -> KycSubmission:
        sub = self._get_or_404(submission_id)
        sub.status = "rejected"
        sub.reviewed_by = reviewer_id
        sub.reviewed_at = datetime.utcnow()
        sub.reviewer_note = note
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def _get_or_404(self, submission_id: str) -> KycSubmission:
        sub = self.db.get(KycSubmission, submission_id)
        if sub is None:
            raise ValueError(f"KYC submission {submission_id} not found")
        return sub
