from __future__ import annotations

import uuid
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.observability import logger
from app.models.notification import Notification
from app.models.task import Task
from app.models.trust import UserReview
from app.models.user import User


CLIENT_TO_TASKER = "TASKER_BY_CLIENT"
TASKER_TO_CLIENT = "CLIENT_BY_TASKER"


class RatingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_client_review(
        self,
        task_id: str,
        client_user_id: str,
        punctuality_score: int,
        quality_score: int,
        communication_score: int,
        standards_score: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        scores = {
            "punctuality_score": punctuality_score,
            "quality_score": quality_score,
            "communication_score": communication_score,
            "standards_score": standards_score,
        }
        task, reviewee = self._lock_client_to_tasker_context(task_id, client_user_id)
        overall = self._calculate_overall(list(scores.values()))
        review = UserReview(
            id=str(uuid.uuid4()),
            task_id=task.id,
            reviewer_id=client_user_id,
            reviewee_id=reviewee.id,
            review_type=CLIENT_TO_TASKER,
            overall_score=overall,
            comment=self._clean_comment(comment),
            **scores,
        )
        self.db.add(review)
        task.creator_rated = True
        self._refresh_review_aggregates(reviewee, CLIENT_TO_TASKER)
        self._enforce_tasker_threshold(reviewee)
        self._refresh_trust_score(reviewee.id)
        self.db.commit()
        self.db.refresh(review)
        return self._serialize_review(review)

    def submit_tasker_review(
        self,
        task_id: str,
        tasker_user_id: str,
        instructions_score: int,
        behavior_score: int,
        payment_score: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        scores = {
            "instructions_score": instructions_score,
            "behavior_score": behavior_score,
            "payment_score": payment_score,
        }
        task, reviewee = self._lock_tasker_to_client_context(task_id, tasker_user_id)
        overall = self._calculate_overall(list(scores.values()))
        review = UserReview(
            id=str(uuid.uuid4()),
            task_id=task.id,
            reviewer_id=tasker_user_id,
            reviewee_id=reviewee.id,
            review_type=TASKER_TO_CLIENT,
            overall_score=overall,
            comment=self._clean_comment(comment),
            **scores,
        )
        self.db.add(review)
        task.tasker_rated = True
        self._refresh_review_aggregates(reviewee, TASKER_TO_CLIENT)
        self._enforce_client_threshold(reviewee)
        self._refresh_trust_score(reviewee.id)
        self.db.commit()
        self.db.refresh(review)
        return self._serialize_review(review)

    def get_public_rating_summary(self, user_id: str) -> dict[str, Any]:
        tasker_summary = self._build_summary(user_id, CLIENT_TO_TASKER)
        client_summary = self._build_summary(user_id, TASKER_TO_CLIENT)
        return {
            "asTasker": tasker_summary,
            "asClient": client_summary,
        }

    def list_user_reviews(
        self,
        user_id: str,
        review_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        stmt = select(UserReview).where(
            UserReview.reviewee_id == user_id,
            UserReview.is_public == True,  # noqa: E712
        )
        if review_type:
            stmt = stmt.where(UserReview.review_type == review_type)
        rows = self.db.execute(
            stmt.order_by(UserReview.created_at.desc()).limit(limit)
        ).scalars().all()
        return [self._serialize_review(row) for row in rows]

    def _lock_client_to_tasker_context(self, task_id: str, client_user_id: str) -> tuple[Task, User]:
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one()
        if task.status != "COMPLETED":
            raise ValueError("Impossible de noter une tâche non terminée")
        if task.created_by != client_user_id:
            raise ValueError("Seul le client de la tâche peut noter le tasker")
        if task.creator_rated:
            raise ValueError("Le tasker a déjà été noté pour cette tâche")
        if not task.assigned_to:
            raise ValueError("Aucun tasker assigné à noter")
        reviewee = self.db.execute(
            select(User).where(User.id == task.assigned_to).with_for_update()
        ).scalars().one()
        return task, reviewee

    def _lock_tasker_to_client_context(self, task_id: str, tasker_user_id: str) -> tuple[Task, User]:
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one()
        if task.status != "COMPLETED":
            raise ValueError("Impossible de noter une tâche non terminée")
        if task.assigned_to != tasker_user_id:
            raise ValueError("Seul le tasker assigné peut noter le client")
        if task.tasker_rated:
            raise ValueError("Le client a déjà été noté pour cette tâche")
        reviewee = self.db.execute(
            select(User).where(User.id == task.created_by).with_for_update()
        ).scalars().one()
        return task, reviewee

    def _refresh_review_aggregates(self, user: User, review_type: str) -> None:
        avg_score = self.db.execute(
            select(func.avg(UserReview.overall_score)).where(
                UserReview.reviewee_id == user.id,
                UserReview.review_type == review_type,
            )
        ).scalar()
        count_score = self.db.execute(
            select(func.count(UserReview.id)).where(
                UserReview.reviewee_id == user.id,
                UserReview.review_type == review_type,
            )
        ).scalar() or 0
        if review_type == CLIENT_TO_TASKER:
            user.rating_sum = float(avg_score or 0.0) * int(count_score)
            user.rating_count = int(count_score)
        else:
            user.client_rating_sum = float(avg_score or 0.0) * int(count_score)
            user.client_rating_count = int(count_score)

    def _enforce_tasker_threshold(self, user: User) -> None:
        average = self._safe_average(user.rating_sum, user.rating_count)
        if user.role == "tasker" and user.rating_count >= 10 and average < 3.5 and not user.is_suspended:
            user.is_suspended = True
            user.suspension_reason = "Suspension automatique : note tasker inférieure à 3.5/5 après 10 tâches."
            self._notify_admins(
                title="Suspension automatique Tasker",
                body=f"Le tasker {self._display_name(user)} a été suspendu automatiquement pour note moyenne insuffisante ({average:.2f}/5).",
            )
            self._notify_user(
                user_id=user.id,
                title="Compte temporairement suspendu",
                body="Votre compte tasker a été suspendu automatiquement car votre note moyenne est passée sous 3.5/5 après 10 tâches terminées.",
                type_="warning",
            )

    def _enforce_client_threshold(self, user: User) -> None:
        average = self._safe_average(user.client_rating_sum, user.client_rating_count)
        if user.client_rating_count >= 5 and average < 3.0:
            newly_restricted = not user.premium_access_restricted
            user.premium_access_restricted = True
            user.premium_access_restricted_reason = "Restriction automatique : note client inférieure à 3/5 après 5 tâches."
            user.premium_access_restricted_at = datetime.now(timezone.utc)
            if newly_restricted:
                self._notify_admins(
                    title="Restriction client premium",
                    body=f"Le client {self._display_name(user)} a été restreint des taskers premium pour note moyenne insuffisante ({average:.2f}/5).",
                )
                self._notify_user(
                    user_id=user.id,
                    title="Accès premium restreint",
                    body="Votre accès aux taskers premium a été restreint automatiquement à cause de votre note moyenne client.",
                    type_="warning",
                )
        elif user.premium_access_restricted and average >= 3.0:
            user.premium_access_restricted = False
            user.premium_access_restricted_reason = None
            user.premium_access_restricted_at = None

    def _build_summary(self, user_id: str, review_type: str) -> dict[str, Any]:
        rows = self.db.execute(
            select(UserReview).where(
                UserReview.reviewee_id == user_id,
                UserReview.review_type == review_type,
            )
        ).scalars().all()
        if not rows:
            return {
                "reviewType": review_type,
                "average": None,
                "count": 0,
                "dimensions": {},
            }
        dimensions: dict[str, list[int]] = {
            "punctuality": [],
            "quality": [],
            "communication": [],
            "standards": [],
            "instructions": [],
            "behavior": [],
            "payment": [],
        }
        for row in rows:
            self._maybe_append(dimensions["punctuality"], row.punctuality_score)
            self._maybe_append(dimensions["quality"], row.quality_score)
            self._maybe_append(dimensions["communication"], row.communication_score)
            self._maybe_append(dimensions["standards"], row.standards_score)
            self._maybe_append(dimensions["instructions"], row.instructions_score)
            self._maybe_append(dimensions["behavior"], row.behavior_score)
            self._maybe_append(dimensions["payment"], row.payment_score)
        averages = {
            key: round(mean(values), 2)
            for key, values in dimensions.items()
            if values
        }
        overall_average = round(mean([float(row.overall_score) for row in rows]), 2)
        return {
            "reviewType": review_type,
            "average": overall_average,
            "count": len(rows),
            "dimensions": averages,
        }

    def _refresh_trust_score(self, user_id: str) -> None:
        try:
            from app.services.trust_service import TrustService

            TrustService(self.db).compute_for_user(user_id)
        except Exception as exc:
            logger.error("rating:trust_refresh_failed user_id={} error={}", user_id, exc)
            self.db.rollback()
            raise

    def _notify_admins(self, title: str, body: str) -> None:
        admin_ids = self.db.execute(
            select(User.id).where(User.role == "admin", User.is_locked == False)  # noqa: E712
        ).scalars().all()
        for admin_id in admin_ids:
            self.db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=admin_id,
                type="warning",
                title=title,
                body=body,
            ))

    def _notify_user(self, user_id: str, title: str, body: str, type_: str = "info") -> None:
        self.db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=type_,
            title=title,
            body=body,
        ))

    @staticmethod
    def _calculate_overall(scores: list[int]) -> float:
        for score in scores:
            if not 1 <= int(score) <= 5:
                raise ValueError("Chaque critère de note doit être compris entre 1 et 5")
        return round(sum(scores) / len(scores), 2)

    @staticmethod
    def _safe_average(total: float, count: int) -> float:
        if count <= 0:
            return 0.0
        return float(total) / float(count)

    @staticmethod
    def _clean_comment(comment: str | None) -> str | None:
        if comment is None:
            return None
        cleaned = comment.strip()
        return cleaned or None

    @staticmethod
    def _maybe_append(bucket: list[int], value: int | None) -> None:
        if value is not None:
            bucket.append(int(value))

    @staticmethod
    def _display_name(user: User) -> str:
        return " ".join(filter(None, [user.first_name, user.last_name])) or user.email or user.id

    @staticmethod
    def _serialize_review(review: UserReview) -> dict[str, Any]:
        return {
            "id": review.id,
            "taskId": review.task_id,
            "reviewerId": review.reviewer_id,
            "revieweeId": review.reviewee_id,
            "reviewType": review.review_type,
            "overallScore": review.overall_score,
            "punctualityScore": review.punctuality_score,
            "qualityScore": review.quality_score,
            "communicationScore": review.communication_score,
            "standardsScore": review.standards_score,
            "instructionsScore": review.instructions_score,
            "behaviorScore": review.behavior_score,
            "paymentScore": review.payment_score,
            "comment": review.comment,
            "createdAt": review.created_at.isoformat() if review.created_at else None,
        }
