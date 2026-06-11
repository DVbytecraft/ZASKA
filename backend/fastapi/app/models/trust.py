"""Trust & Safety models — TrustScore, Skills, Badges, PhotoVerification, ModerationCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TrustScore(Base):
    """Computed trust score for a user — one row per user, upserted on recompute."""

    __tablename__ = "trust_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # BRONZE | SILVER | GOLD | PLATINUM | DIAMOND
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="BRONZE")
    identity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)   # max 25
    financial_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # max 20
    profile_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)    # max 15
    age_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)        # max 10
    community_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0) # max 20
    behavior_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # max 10
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Skill(Base):
    """Skill catalog — seeded at startup, shared across all users."""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class UserSkill(Base):
    """A skill claimed by a user at a given level."""

    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False)
    # BEGINNER | INTERMEDIATE | EXPERT
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="BEGINNER")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Badge(Base):
    """Badge definitions — seeded at startup."""

    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str] = mapped_column(String(64), nullable=False, default="medal")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class UserBadge(Base):
    """Badge awarded to a user — auto-awarded by trust score cron."""

    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_code", name="uq_user_badge"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    badge_code: Mapped[str] = mapped_column(String(32), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class PhotoVerification(Base):
    """Selfie liveness verification result — one row per user (upserted)."""

    __tablename__ = "photo_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    selfie_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # PENDING | VERIFIED | FAILED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # mock | rekognition
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class ModerationCase(Base):
    """Content moderation case — reported by a user, reviewed by admins."""

    __tablename__ = "moderation_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reporter_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    reported_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    # profile | task | chat | review
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LOW | MEDIUM | HIGH | CRITICAL
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW")
    # PENDING | UNDER_REVIEW | RESOLVED | DISMISSED | ESCALATED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    resolution: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # none | warned | muted_24h | muted_7d | banned
    action_taken: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    resolver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserReview(Base):
    """Immutable review event for a completed task."""

    __tablename__ = "user_reviews"
    __table_args__ = (
        UniqueConstraint("task_id", "review_type", name="uq_user_review_task_type"),
        UniqueConstraint("task_id", "reviewer_id", name="uq_user_review_task_reviewer"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    reviewee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    review_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    punctuality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    communication_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    standards_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instructions_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    behavior_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
