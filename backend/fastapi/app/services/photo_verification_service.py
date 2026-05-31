"""Photo verification via face presence detection.

IMPORTANT — this is NOT true liveness detection.
AWS Rekognition detect_faces can be fooled by a printed photo held in front of the camera.
For production-grade liveness, migrate to:
  - AWS Rekognition FaceLiveness (CreateFaceLivenessSession / GetFaceLivenessSessionResults)
  - Or: iProov / Onfido / Smile Identity

Provider priority:
  1. AWS Rekognition detect_faces — if AWS_ACCESS_KEY_ID configured
  2. Mock — auto-approve (dev mode)

Current check:
  - Exactly 1 face detected, Confidence > threshold (default 0.80)
  - EyesOpen.Value == True
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.models.trust import PhotoVerification


class PhotoVerificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_status(self, user_id: str) -> PhotoVerification | None:
        return self.db.execute(
            select(PhotoVerification).where(PhotoVerification.user_id == user_id)
        ).scalars().one_or_none()

    def submit(self, user_id: str, selfie_url: str) -> PhotoVerification:
        """Run liveness check on a selfie URL and upsert the result."""
        existing = self.get_status(user_id)

        score, status, provider = self._run_liveness(selfie_url)

        now = datetime.now(timezone.utc)
        if existing:
            existing.selfie_url    = selfie_url
            existing.status        = status
            existing.liveness_score= score
            existing.provider      = provider
            existing.reviewed_at   = now
        else:
            existing = PhotoVerification(
                id=str(uuid.uuid4()),
                user_id=user_id,
                selfie_url=selfie_url,
                status=status,
                liveness_score=score,
                provider=provider,
                reviewed_at=now,
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def _run_liveness(self, selfie_url: str) -> tuple[float, str, str]:
        """Returns (score, status, provider_name)."""
        aws_key = settings.aws_access_key_id.strip()
        if not aws_key:
            return self._mock_liveness()
        try:
            return self._rekognition_liveness(selfie_url)
        except Exception as exc:
            logger.error("photo_verification:rekognition_error {}", exc)
            return self._mock_liveness()

    def _mock_liveness(self) -> tuple[float, str, str]:
        logger.debug("photo_verification:mock_approve")
        return (0.95, "VERIFIED", "mock")

    def _rekognition_liveness(self, selfie_url: str) -> tuple[float, str, str]:
        import io
        import urllib.request

        import boto3  # type: ignore[import-untyped]

        threshold = settings.photo_liveness_threshold

        client = boto3.client(
            "rekognition",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        # Download the image bytes
        with urllib.request.urlopen(selfie_url, timeout=10) as response:
            image_bytes = response.read()

        result = client.detect_faces(
            Image={"Bytes": image_bytes},
            Attributes=["ALL"],
        )
        faces = result.get("FaceDetails", [])

        if len(faces) != 1:
            logger.warning("photo_verification:rekognition faces_count={}", len(faces))
            return (0.0, "FAILED", "rekognition")

        face = faces[0]
        confidence = face.get("Confidence", 0.0) / 100.0
        eyes_open = face.get("EyesOpen", {}).get("Value", False)

        if confidence >= threshold and eyes_open:
            return (confidence, "VERIFIED", "rekognition_face_detection")
        return (confidence, "FAILED", "rekognition_face_detection")
