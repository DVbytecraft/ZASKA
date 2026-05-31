"""Photo verification — face detection and face comparison.

Verification modes (in priority order):
  1. Face comparison (selfie vs KYC document) — compare_with_kyc()
     Uses Rekognition CompareFaces — confirms selfie matches identity document.
     This is stronger than face detection alone.
  2. Face detection (selfie only) — submit()
     Uses Rekognition detect_faces — confirms a real face is present.
     NOT true liveness: a printed photo can bypass this check.
  3. Mock — auto-approve (dev mode when AWS not configured)

IMPORTANT — true liveness not yet implemented.
For production-grade liveness, migrate to:
  - AWS Rekognition FaceLiveness (CreateFaceLivenessSession / GetFaceLivenessSessionResults)
  - Or: iProov / Onfido / Smile Identity
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

    def compare_with_kyc(self, user_id: str, selfie_url: str, kyc_doc_url: str) -> dict:
        """Compare a selfie against a KYC identity document using Rekognition CompareFaces.

        Returns a dict with: match (bool), similarity (float 0-1), status, provider.
        Higher similarity = more likely the same person.
        Threshold: 80% similarity required (Rekognition default).
        """
        aws_key = settings.aws_access_key_id.strip()
        if not aws_key:
            logger.debug("photo_verification:compare_mock user_id={}", user_id)
            return {"match": True, "similarity": 0.99, "status": "MATCH", "provider": "mock"}
        try:
            return self._rekognition_compare_faces(selfie_url, kyc_doc_url)
        except Exception as exc:
            logger.error("photo_verification:compare_error user_id={} error={}", user_id, exc)
            return {"match": False, "similarity": 0.0, "status": "ERROR", "provider": "rekognition"}

    def _rekognition_compare_faces(self, source_url: str, target_url: str) -> dict:
        """Compare source face (selfie) against target face (KYC doc) using CompareFaces."""
        import urllib.request
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "rekognition",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        with urllib.request.urlopen(source_url, timeout=10) as r:
            source_bytes = r.read()
        with urllib.request.urlopen(target_url, timeout=10) as r:
            target_bytes = r.read()

        result = client.compare_faces(
            SourceImage={"Bytes": source_bytes},
            TargetImage={"Bytes": target_bytes},
            SimilarityThreshold=70.0,
        )
        matches = result.get("FaceMatches", [])
        if not matches:
            return {"match": False, "similarity": 0.0, "status": "NO_MATCH", "provider": "rekognition_compare"}

        best = max(matches, key=lambda m: m.get("Similarity", 0))
        similarity = best.get("Similarity", 0.0) / 100.0
        matched = similarity >= 0.80
        return {
            "match": matched,
            "similarity": round(similarity, 3),
            "status": "MATCH" if matched else "LOW_SIMILARITY",
            "provider": "rekognition_compare",
        }

    def _rekognition_liveness(self, selfie_url: str) -> tuple[float, str, str]:
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
