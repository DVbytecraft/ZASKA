"""Trust Score Engine.

Algorithm — 9 components totalling up to 130 points (capped at 100):
  identity        (25): phone_verified + email_set + kyc_approved
  financial       (20): has_transactions + no_recent_payout_failures + positive_balance
  profile         (15): avatar + bio + city + hourly_rate + skills
  age             (10): account age in days → tiered
  community       (20): rating_avg * 4 (capped) weighted by review count
  behavior        (10): not_suspended + no_recent_moderation_cases
  completion_rate (15): tasks completed / tasks assigned as tasker
  activity_recency(10): decays if user has been inactive > 30 days
  device_trust     (5): single-user device known for X days (X-Device-ID)

Total is min(100, sum_of_components). The extra 30 pts from new components let
active users compensate for weak areas while still being capped at 100.

Levels:  0-20 BRONZE | 21-40 SILVER | 41-60 GOLD | 61-80 PLATINUM | 81-100 DIAMOND

Cron: runs daily at 03:00 UTC (configured via TRUST_SCORE_RECALC_CRON).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.observability import logger
from app.models.kyc import KycSubmission
from app.models.trust import Badge, Skill, TrustScore, UserBadge, UserSkill
from app.models.user import User
from app.models.wallet import Transaction, Wallet

_BADGE_CATALOG: list[dict[str, str]] = [
    {"code": "VERIFIED_PHONE",  "label": "Téléphone vérifié", "description": "A validé son numéro de téléphone par OTP",     "icon": "phone"},
    {"code": "VERIFIED_EMAIL",  "label": "Email vérifié",     "description": "A fourni une adresse email",                   "icon": "mail"},
    {"code": "VERIFIED_KYC",    "label": "KYC approuvé",      "description": "Identité vérifiée par nos équipes",            "icon": "shield-check"},
    {"code": "PHOTO_VERIFIED",  "label": "Photo vérifiée",    "description": "Selfie liveness confirmé",                    "icon": "camera"},
    {"code": "CERTIFIED_ZASKA", "label": "Certifié Zaska",    "description": "Identité et casier vérifiés par Zaska",       "icon": "badge-check"},
    {"code": "PROTECTED_ZASKA", "label": "Protégé Zaska",     "description": "Ce Tasker bénéficie de la protection sociale Zaska", "icon": "heart-handshake"},
    {"code": "TASKER_SENIOR",   "label": "Tasker Senior",     "description": "Tasker expérimenté — pension garantie activée", "icon": "shield"},
    {"code": "FIRST_TASK",      "label": "Première mission",  "description": "A complété sa première tâche",                 "icon": "star"},
    {"code": "TOP_RATED",       "label": "Top Rated",         "description": "Note moyenne > 4.8 avec au moins 50 tâches complétées", "icon": "award"},
    {"code": "EARLY_ADOPTER",   "label": "Pionnier",          "description": "A rejoint la plateforme avant novembre 2026",  "icon": "zap"},
    {"code": "TRUSTED_MEMBER",  "label": "Membre de confiance","description": "A atteint le niveau GOLD ou supérieur",       "icon": "heart"},
]

_SKILL_CATALOG: list[dict[str, str]] = [
    # Domestic
    {"name": "Ménage",       "category": "domestic"},
    {"name": "Cuisine",      "category": "domestic"},
    {"name": "Jardinage",    "category": "domestic"},
    {"name": "Garde d'enfants", "category": "domestic"},
    # Logistics
    {"name": "Livraison",    "category": "logistics"},
    {"name": "Déménagement", "category": "logistics"},
    {"name": "Courses",      "category": "logistics"},
    # Technical
    {"name": "Plomberie",    "category": "technical"},
    {"name": "Électricité",  "category": "technical"},
    {"name": "Menuiserie",   "category": "technical"},
    {"name": "Informatique", "category": "technical"},
    {"name": "Réparation électronique", "category": "technical"},
    # Beauty
    {"name": "Coiffure",     "category": "beauty"},
    {"name": "Maquillage",   "category": "beauty"},
    {"name": "Massage",      "category": "beauty"},
    # Education
    {"name": "Cours particuliers", "category": "education"},
    {"name": "Langues",      "category": "education"},
    # Events
    {"name": "Photographie", "category": "events"},
    {"name": "Événementiel", "category": "events"},
    # Other
    {"name": "Sécurité",     "category": "other"},
]


def _level_for(score: float) -> str:
    if score >= 81:
        return "DIAMOND"
    if score >= 61:
        return "PLATINUM"
    if score >= 41:
        return "GOLD"
    if score >= 21:
        return "SILVER"
    return "BRONZE"


class TrustService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Seed ────────────────────────────────────────────────────────────────

    def seed_catalog(self) -> None:
        """Idempotently seed badge and skill catalogs (call at startup or migration)."""
        for b in _BADGE_CATALOG:
            existing = self.db.execute(
                select(Badge).where(Badge.code == b["code"])
            ).scalars().one_or_none()
            if not existing:
                self.db.add(Badge(id=str(uuid.uuid4()), **b))

        for s in _SKILL_CATALOG:
            existing = self.db.execute(
                select(Skill).where(Skill.name == s["name"])
            ).scalars().one_or_none()
            if not existing:
                self.db.add(Skill(id=str(uuid.uuid4()), **s))

        self.db.commit()

    # ─── Query helpers ────────────────────────────────────────────────────────

    def get_trust_score(self, user_id: str) -> TrustScore | None:
        return self.db.execute(
            select(TrustScore).where(TrustScore.user_id == user_id)
        ).scalars().one_or_none()

    def get_user_skills(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(UserSkill, Skill)
            .join(Skill, Skill.id == UserSkill.skill_id)
            .where(UserSkill.user_id == user_id)
        ).all()
        return [
            {"id": us.id, "skill_id": s.id, "name": s.name, "category": s.category, "level": us.level}
            for us, s in rows
        ]

    def get_user_badges(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(UserBadge, Badge)
            .join(Badge, Badge.code == UserBadge.badge_code)
            .where(UserBadge.user_id == user_id)
            .order_by(UserBadge.awarded_at.desc())
        ).all()
        return [
            {
                "code": b.code,
                "label": b.label,
                "description": b.description,
                "icon": b.icon,
                "awarded_at": ub.awarded_at.isoformat(),
            }
            for ub, b in rows
        ]

    def get_tasker_badge_overview(self, limit: int = 200) -> dict[str, Any]:
        from app.services.wallet_service import WalletService

        now = datetime.now(timezone.utc)
        wallet_service = WalletService(self.db)
        public_codes = {
            "CERTIFIED_ZASKA",
            "PROTECTED_ZASKA",
            "TASKER_SENIOR",
            "TOP_RATED",
        }

        badge_counts: dict[str, dict[str, Any]] = {}
        tasker_rows: list[dict[str, Any]] = []
        taskers = self.db.execute(
            select(User).where(User.role == "tasker").order_by(User.created_at.desc())
        ).scalars().all()

        for tasker in taskers:
            try:
                self.compute_for_user(tasker.id)
            except Exception:
                pass

            badges = [
                badge for badge in self.get_user_badges(tasker.id)
                if badge["code"] in public_codes
            ]
            for badge in badges:
                bucket = badge_counts.setdefault(
                    badge["code"],
                    {
                        "code": badge["code"],
                        "label": badge["label"],
                        "description": badge["description"],
                        "count": 0,
                    },
                )
                bucket["count"] += 1

            overview = wallet_service.get_social_protection_overview(tasker.id)
            rating_avg = round(tasker.rating_sum / tasker.rating_count, 2) if tasker.rating_count else None
            tasker_rows.append({
                "tasker_id": tasker.id,
                "tasker_name": " ".join(filter(None, [tasker.first_name, tasker.last_name])) or tasker.email or tasker.id,
                "country_code": tasker.country_code,
                "rating_avg": rating_avg,
                "rating_count": tasker.rating_count,
                "completed_tasks": overview.get("total_completed_tasks", 0),
                "active_months": overview.get("active_months", 0),
                "tasker_security_verified": tasker.tasker_security_verified,
                "criminal_record_status": tasker.criminal_record_status,
                "social_badge": overview.get("badge"),
                "public_badges": badges,
            })

        tasker_rows.sort(
            key=lambda row: (
                len(row["public_badges"]),
                row["completed_tasks"],
                row["active_months"],
            ),
            reverse=True,
        )

        return {
            "counts": sorted(badge_counts.values(), key=lambda item: item["count"], reverse=True),
            "taskers": tasker_rows[:limit],
            "generated_at": now.isoformat(),
        }

    def list_skills_catalog(self) -> list[dict[str, Any]]:
        rows = self.db.execute(select(Skill).order_by(Skill.category, Skill.name)).scalars().all()
        return [{"id": s.id, "name": s.name, "category": s.category} for s in rows]

    def add_skill(self, user_id: str, skill_id: str, level: str = "BEGINNER") -> dict[str, Any]:
        skill = self.db.get(Skill, skill_id)
        if skill is None:
            raise ValueError(f"Skill {skill_id} not found")
        if level not in ("BEGINNER", "INTERMEDIATE", "EXPERT"):
            raise ValueError("level must be BEGINNER, INTERMEDIATE or EXPERT")
        existing = self.db.execute(
            select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.skill_id == skill_id)
        ).scalars().one_or_none()
        if existing:
            existing.level = level
        else:
            existing = UserSkill(id=str(uuid.uuid4()), user_id=user_id, skill_id=skill_id, level=level)
            self.db.add(existing)
        self.db.commit()
        return {"id": existing.id, "skill_id": skill_id, "name": skill.name, "category": skill.category, "level": level}

    def remove_skill(self, user_id: str, user_skill_id: str) -> None:
        us = self.db.execute(
            select(UserSkill).where(UserSkill.id == user_skill_id, UserSkill.user_id == user_id)
        ).scalars().one_or_none()
        if us is None:
            raise ValueError("Skill not found")
        self.db.delete(us)
        self.db.commit()

    # ─── Computation ──────────────────────────────────────────────────────────

    def compute_for_user(self, user_id: str) -> TrustScore:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        identity         = self._identity(user)
        financial        = self._financial(user)
        profile          = self._profile(user)
        age              = self._age(user)
        community        = self._community(user)
        behavior         = self._behavior(user)
        completion_rate  = self._completion_rate(user)
        activity_recency = self._activity_recency(user)
        device_trust     = self._device_trust(user.id)

        total = round(
            identity + financial + profile + age + community + behavior
            + completion_rate + activity_recency + device_trust,
            1,
        )
        total = max(0.0, min(100.0, total))
        level = _level_for(total)

        ts = self.db.execute(
            select(TrustScore).where(TrustScore.user_id == user_id)
        ).scalars().one_or_none()

        now = datetime.now(timezone.utc)
        if ts:
            ts.total_score    = total
            ts.level          = level
            ts.identity_score = identity
            ts.financial_score= financial
            ts.profile_score  = profile
            ts.age_score      = age
            ts.community_score= community
            ts.behavior_score = behavior
            ts.computed_at    = now
        else:
            ts = TrustScore(
                id=str(uuid.uuid4()),
                user_id=user_id,
                total_score=total,
                level=level,
                identity_score=identity,
                financial_score=financial,
                profile_score=profile,
                age_score=age,
                community_score=community,
                behavior_score=behavior,
                computed_at=now,
            )
            self.db.add(ts)

        self.db.flush()
        self._award_badges(user, ts)
        self.db.commit()
        self.db.refresh(ts)
        return ts

    def _identity(self, user: User) -> float:
        score = 0.0
        if user.is_verified:
            score += 10.0
        if user.email:
            score += 5.0
        kyc = self.db.execute(
            select(KycSubmission)
            .where(KycSubmission.user_id == user.id, KycSubmission.status == "approved")
            .order_by(KycSubmission.created_at.desc())
        ).scalars().first()
        if kyc and not kyc.is_expired:
            score += 10.0
        return min(25.0, score)

    def _financial(self, user: User) -> float:
        score = 0.0
        tx_count = self.db.execute(
            select(func.count(Transaction.id))
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(Wallet.user_id == user.id, Transaction.status == "completed")
        ).scalar() or 0
        if tx_count > 0:
            score += 5.0

        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        from app.models.payout import Payout
        failed_payouts = self.db.execute(
            select(func.count())
            .select_from(Payout)
            .where(
                Payout.user_id == user.id,
                Payout.status == "failed",
                Payout.created_at >= thirty_days_ago,
            )
        ).scalar() or 0
        if failed_payouts == 0:
            score += 10.0

        positive_balance = self.db.execute(
            select(func.sum(Wallet.balance)).where(Wallet.user_id == user.id)
        ).scalar() or 0
        if float(positive_balance) > 0:
            score += 5.0

        return min(20.0, score)

    def _profile(self, user: User) -> float:
        score = 0.0
        if user.avatar_url:
            score += 3.0
        if getattr(user, "bio", None):
            score += 3.0
        if getattr(user, "city", None):
            score += 3.0
        if getattr(user, "hourly_rate", None):
            score += 3.0
        skill_count = self.db.execute(
            select(func.count(UserSkill.id)).where(UserSkill.user_id == user.id)
        ).scalar() or 0
        if skill_count >= 1:
            score += 3.0
        return min(15.0, score)

    def _age(self, user: User) -> float:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days >= 180:
            return 10.0
        if age_days >= 90:
            return 7.0
        if age_days >= 30:
            return 4.0
        return 0.0

    def _community(self, user: User) -> float:
        rating_sum = user.rating_sum
        rating_count = user.rating_count
        if user.role != "tasker" and getattr(user, "client_rating_count", 0) > 0:
            rating_sum = getattr(user, "client_rating_sum", 0.0) or 0.0
            rating_count = getattr(user, "client_rating_count", 0) or 0
        if rating_count < 3:
            # Penalize sparse ratings — only half credit until 3 reviews
            if rating_count == 0:
                return 0.0
            avg = rating_sum / rating_count
            return min(20.0, (avg / 5.0) * 20.0 * 0.5)
        avg = rating_sum / rating_count
        return min(20.0, (avg / 5.0) * 20.0)

    def _behavior(self, user: User) -> float:
        score = 0.0
        if not user.is_suspended:
            score += 5.0
        from app.models.trust import ModerationCase
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_cases = self.db.execute(
            select(func.count(ModerationCase.id)).where(
                ModerationCase.reported_user_id == user.id,
                ModerationCase.status.in_(["RESOLVED", "ESCALATED"]),
                ModerationCase.created_at >= thirty_days_ago,
            )
        ).scalar() or 0
        if recent_cases == 0:
            score += 5.0
        return min(10.0, score)

    def _completion_rate(self, user: User) -> float:
        """0-15 pts: ratio of completed tasks to all assigned tasks as tasker.

        Penalizes users who accept tasks then abandon them.
        """
        from app.models.task import Task
        assigned = self.db.execute(
            select(func.count(Task.id)).where(
                Task.assigned_to == user.id,
                Task.status.in_(["COMPLETED", "CANCELLED", "DISPUTE"]),
            )
        ).scalar() or 0
        if assigned == 0:
            return 0.0
        completed = self.db.execute(
            select(func.count(Task.id)).where(
                Task.assigned_to == user.id,
                Task.status == "COMPLETED",
            )
        ).scalar() or 0
        rate = completed / assigned
        return round(min(15.0, rate * 15.0), 1)

    def _activity_recency(self, user: User) -> float:
        """0-10 pts: decays if user has had no transactions or task activity in 30+ days.

        Full 10 pts if active in last 30 days, prorated decay down to 0 at 180 days.
        """
        from app.models.task import Task
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        one_eighty_days_ago = datetime.now(timezone.utc) - timedelta(days=180)

        # Check recent transaction activity
        recent_tx = self.db.execute(
            select(func.count(Transaction.id))
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Wallet.user_id == user.id,
                Transaction.created_at >= thirty_days_ago,
            )
        ).scalar() or 0
        if recent_tx > 0:
            return 10.0

        # Check recent task activity (as client or tasker)
        recent_task = self.db.execute(
            select(func.count(Task.id)).where(
                (Task.created_by == user.id) | (Task.assigned_to == user.id),
                Task.created_at >= thirty_days_ago,
            )
        ).scalar() or 0
        if recent_task > 0:
            return 10.0

        # Check if active within 180 days for partial credit
        somewhat_recent_tx = self.db.execute(
            select(func.count(Transaction.id))
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Wallet.user_id == user.id,
                Transaction.created_at >= one_eighty_days_ago,
            )
        ).scalar() or 0
        if somewhat_recent_tx > 0:
            return 5.0

        return 0.0

    def _device_trust(self, user_id: str) -> float:
        """0-5 pts: trusted single-user device = 5 pts, multi-account device = 0 pts.

        Reads device fingerprint data from Redis (populated by DeviceFingerprintMiddleware).
        Falls back to 0 if Redis unavailable or no device data.
        """
        try:
            from app.services.multi_account_service import MultiAccountService
            from app.core.redis_client import redis_sync
            # Find device IDs registered to this user (look for sets containing user_id)
            # Since we can't SCAN all device keys cheaply, we store a reverse index
            user_devices_key = f"user_devices:{user_id}"
            raw_devices = redis_sync.smembers(user_devices_key)
            if not raw_devices:
                return 0.0
            svc = MultiAccountService()
            best_score = 0.0
            for raw_dev in raw_devices:
                dev_id = raw_dev.decode() if isinstance(raw_dev, bytes) else raw_dev
                score = svc.get_device_trust_score(user_id, dev_id)
                if score > best_score:
                    best_score = score
            return best_score
        except Exception:
            return 0.0

    def _award_badges(self, user: User, ts: TrustScore) -> None:
        """Auto-award badges based on current state. Idempotent — won't re-award."""
        from app.models.task import Task
        from app.services.wallet_service import WalletService

        to_award: set[str] = set()
        revocable_codes = {
            "VERIFIED_PHONE",
            "VERIFIED_EMAIL",
            "VERIFIED_KYC",
            "PHOTO_VERIFIED",
            "CERTIFIED_ZASKA",
            "PROTECTED_ZASKA",
            "TASKER_SENIOR",
            "TOP_RATED",
            "TRUSTED_MEMBER",
        }

        if user.is_verified:
            to_award.add("VERIFIED_PHONE")
        if user.email:
            to_award.add("VERIFIED_EMAIL")

        latest_kyc = self.db.execute(
            select(KycSubmission)
            .where(KycSubmission.user_id == user.id)
            .order_by(KycSubmission.created_at.desc())
        ).scalars().first()
        has_active_kyc = bool(latest_kyc and latest_kyc.status == "approved" and not latest_kyc.is_expired)
        has_clear_record = (user.criminal_record_status or "pending") in {"clear", "approved"} or (
            latest_kyc is not None and getattr(latest_kyc, "criminal_record_status", "pending") in {"clear", "approved"}
        )

        if has_active_kyc and ts.identity_score >= 10.0:
            to_award.add("VERIFIED_KYC")

        pv = self.db.execute(
            text("SELECT status FROM photo_verifications WHERE user_id = :uid")
            .bindparams(uid=user.id)
        ).one_or_none()
        if pv and pv.status == "VERIFIED":
            to_award.add("PHOTO_VERIFIED")

        rating_avg = (user.rating_sum / user.rating_count) if user.rating_count > 0 else 0.0

        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        cutoff = datetime(2026, 11, 1, tzinfo=timezone.utc)
        if created < cutoff:
            to_award.add("EARLY_ADOPTER")

        if ts.level in ("GOLD", "PLATINUM", "DIAMOND"):
            to_award.add("TRUSTED_MEMBER")

        completed_count = self.db.execute(
            select(func.count(Task.id)).where(
                Task.assigned_to == user.id,
                Task.status == "COMPLETED",
            )
        ).scalar() or 0
        if completed_count >= 1:
            to_award.add("FIRST_TASK")

        if user.role == "tasker":
            overview = WalletService(self.db).get_social_protection_overview(user.id)
            active_months = int(overview.get("active_months", 0) or 0)
            currencies = overview.get("currencies", [])
            has_social_contributions = any(
                float(item["pension"]["total_contributed"]) > 0
                and float(item["health"]["total_paid_to_authorities"]) > 0
                for item in currencies
            )
            if user.tasker_security_verified and has_active_kyc and has_clear_record:
                to_award.add("CERTIFIED_ZASKA")
            if active_months >= 1 and has_social_contributions:
                to_award.add("PROTECTED_ZASKA")
            if rating_avg > 4.8 and completed_count >= 50:
                to_award.add("TOP_RATED")
            if active_months >= 60 and rating_avg > 4.5 and has_social_contributions:
                to_award.add("TASKER_SENIOR")

        now = datetime.now(timezone.utc)
        existing_badges = self.db.execute(
            select(UserBadge).where(UserBadge.user_id == user.id)
        ).scalars().all()
        existing_by_code = {badge.badge_code: badge for badge in existing_badges}
        for code in revocable_codes:
            if code not in to_award and code in existing_by_code:
                self.db.delete(existing_by_code[code])
        for code in to_award:
            existing = self.db.execute(
                select(UserBadge).where(
                    UserBadge.user_id == user.id,
                    UserBadge.badge_code == code,
                )
            ).scalars().one_or_none()
            if not existing:
                self.db.add(UserBadge(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    badge_code=code,
                    awarded_at=now,
                ))

    # ─── Batch recompute (cron) ───────────────────────────────────────────────

    def recompute_all(self) -> int:
        """Recompute trust scores for all verified users. Returns count processed."""
        user_ids = self.db.execute(
            select(User.id).where(User.is_verified == True)  # noqa: E712
        ).scalars().all()
        count = 0
        for uid in user_ids:
            try:
                self.compute_for_user(uid)
                count += 1
            except Exception as exc:
                logger.error("trust:recompute_error user_id={} error={}", uid, exc)
        logger.info("trust:recompute_done count={}", count)
        return count
