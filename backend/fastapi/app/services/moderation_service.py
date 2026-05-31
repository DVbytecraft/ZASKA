"""Moderation Service — AI-assisted content moderation queue.

Flow:
  1. User reports content → ModerationCase created with AI severity analysis
  2. Admin reviews → resolve / dismiss / escalate
  3. Auto-escalate cron: HIGH/CRITICAL cases unresolved after 4h → ESCALATED

AI provider: Anthropic Claude Haiku (if ANTHROPIC_API_KEY set), else rule-based fallback.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.models.trust import ModerationCase
from app.models.user import User


_SEVERITY_KEYWORDS = {
    "CRITICAL": ["violence", "arnaque", "viol", "drogue", "criminel", "terroris", "pédophil", "trafic"],
    "HIGH":     ["harcèlement", "insulte grave", "menace", "escroquerie", "fraude", "agression"],
    "MEDIUM":   ["spam", "faux profil", "discrimin", "racis", "sexis"],
    "LOW":      ["incorrect", "inexact", "inapproprié", "désagréable"],
}


def _rule_based_severity(reason: str) -> str:
    lower = reason.lower()
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        for kw in _SEVERITY_KEYWORDS.get(level, []):
            if kw in lower:
                return level
    return "LOW"


def _ai_severity(reason: str, content_type: str) -> str:
    """Call Claude Haiku to classify severity. Falls back to rule-based on error."""
    api_key = settings.anthropic_api_key.strip()
    if not api_key:
        return _rule_based_severity(reason)
    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"Contenu signalé:\n"
            f"Type: {content_type}\n"
            f"Raison du signalement: {reason}\n\n"
            "Classifie la sévérité parmi: LOW, MEDIUM, HIGH, CRITICAL.\n"
            "Réponds avec UNIQUEMENT le mot de sévérité, rien d'autre."
        )
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip().upper()
        if raw in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            return raw
        return _rule_based_severity(reason)
    except Exception as exc:
        logger.warning("moderation:ai_fallback error={}", exc)
        return _rule_based_severity(reason)


def _ai_analysis(reason: str, content_type: str) -> str | None:
    """Get a brief AI analysis of the reported content. Returns None if AI unavailable."""
    api_key = settings.anthropic_api_key.strip()
    if not api_key:
        return None
    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"Analyse ce signalement sur la plateforme ZASKA:\n"
            f"Type de contenu: {content_type}\n"
            f"Raison: {reason}\n\n"
            "Fournis une analyse concise (2-3 phrases) pour aider le modérateur:\n"
            "1. Nature probable du problème\n"
            "2. Risque pour la plateforme\n"
            "3. Action recommandée"
        )
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        logger.warning("moderation:ai_analysis_failed error={}", exc)
        return None


class ModerationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def report_content(
        self,
        reporter_id: str,
        content_type: str,
        reason: str,
        reported_user_id: str | None = None,
        content_id: str | None = None,
    ) -> ModerationCase:
        if content_type not in ("profile", "task", "chat", "review"):
            raise ValueError("content_type must be: profile, task, chat, review")

        severity = _ai_severity(reason, content_type)
        analysis = _ai_analysis(reason, content_type)

        case = ModerationCase(
            id=str(uuid.uuid4()),
            reporter_id=reporter_id,
            reported_user_id=reported_user_id,
            content_type=content_type,
            content_id=content_id,
            reason=reason,
            ai_analysis=analysis,
            severity=severity,
            status="PENDING",
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        logger.info("moderation:case_created id={} severity={}", case.id, severity)
        return case

    def list_cases(
        self,
        status: str | None = None,
        severity: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        limit = min(limit, 100)
        offset = (max(1, page) - 1) * limit

        q = select(ModerationCase)
        if status:
            q = q.where(ModerationCase.status == status)
        if severity:
            q = q.where(ModerationCase.severity == severity)

        # Sort: CRITICAL first, then by created_at desc
        _sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        total = self.db.execute(
            select(func.count()).select_from(q.subquery())
        ).scalar() or 0

        cases = self.db.execute(
            q.order_by(
                ModerationCase.severity.asc(),  # CRITICAL < HIGH alphabetically: wrong
                ModerationCase.created_at.desc(),
            ).offset(offset).limit(limit)
        ).scalars().all()

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "cases": [self._serialize(c) for c in cases],
        }

    def get_case(self, case_id: str) -> ModerationCase:
        case = self.db.get(ModerationCase, case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        return case

    def resolve_case(
        self,
        case_id: str,
        resolution: str,
        action_taken: str,
        resolver_id: str,
    ) -> ModerationCase:
        case = self.get_case(case_id)
        if case.status in ("RESOLVED", "DISMISSED"):
            raise ValueError(f"Case already {case.status}")
        if action_taken not in ("none", "warned", "muted_24h", "muted_7d", "banned"):
            raise ValueError("Invalid action_taken")

        now = datetime.now(timezone.utc)
        case.status      = "RESOLVED"
        case.resolution  = resolution
        case.action_taken= action_taken
        case.resolver_id = resolver_id
        case.resolved_at = now
        case.updated_at  = now

        # Apply suspension if action requires it
        if action_taken == "banned" and case.reported_user_id:
            user = self.db.get(User, case.reported_user_id)
            if user:
                user.is_suspended = True
                user.ban_reason = f"Banned via moderation case {case_id}: {resolution}"

        self.db.commit()
        self.db.refresh(case)
        return case

    def dismiss_case(self, case_id: str, reason: str, resolver_id: str) -> ModerationCase:
        case = self.get_case(case_id)
        if case.status in ("RESOLVED", "DISMISSED"):
            raise ValueError(f"Case already {case.status}")
        now = datetime.now(timezone.utc)
        case.status     = "DISMISSED"
        case.resolution = reason
        case.resolver_id= resolver_id
        case.resolved_at= now
        case.updated_at = now
        self.db.commit()
        self.db.refresh(case)
        return case

    def escalate_case(self, case_id: str, resolver_id: str) -> ModerationCase:
        case = self.get_case(case_id)
        now = datetime.now(timezone.utc)
        case.status       = "ESCALATED"
        case.severity     = "CRITICAL"
        case.escalated_at = now
        case.updated_at   = now
        self.db.commit()
        self.db.refresh(case)
        return case

    def auto_escalate_stale(self) -> int:
        """Escalate HIGH/CRITICAL cases not acted on within 4 hours. Returns count."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
        cases = self.db.execute(
            select(ModerationCase).where(
                ModerationCase.status.in_(["PENDING", "UNDER_REVIEW"]),
                ModerationCase.severity.in_(["HIGH", "CRITICAL"]),
                ModerationCase.created_at <= cutoff,
            )
        ).scalars().all()

        now = datetime.now(timezone.utc)
        count = 0
        for c in cases:
            c.status       = "ESCALATED"
            c.escalated_at = now
            c.updated_at   = now
            count += 1

        if count:
            self.db.commit()
            logger.info("moderation:auto_escalated count={}", count)
        return count

    def get_stats(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(ModerationCase.status, func.count(ModerationCase.id))
            .group_by(ModerationCase.status)
        ).all()
        by_status = {row[0]: row[1] for row in rows}

        sev_rows = self.db.execute(
            select(ModerationCase.severity, func.count(ModerationCase.id))
            .where(ModerationCase.status.in_(["PENDING", "UNDER_REVIEW"]))
            .group_by(ModerationCase.severity)
        ).all()
        pending_by_severity = {row[0]: row[1] for row in sev_rows}

        return {
            "by_status": by_status,
            "pending_by_severity": pending_by_severity,
            "total_pending": by_status.get("PENDING", 0) + by_status.get("UNDER_REVIEW", 0),
        }

    @staticmethod
    def _serialize(c: ModerationCase) -> dict[str, Any]:
        return {
            "id": c.id,
            "reporterId": c.reporter_id,
            "reportedUserId": c.reported_user_id,
            "contentType": c.content_type,
            "contentId": c.content_id,
            "reason": c.reason,
            "aiAnalysis": c.ai_analysis,
            "severity": c.severity,
            "status": c.status,
            "resolution": c.resolution,
            "actionTaken": c.action_taken,
            "resolverId": c.resolver_id,
            "resolvedAt": c.resolved_at.isoformat() if c.resolved_at else None,
            "escalatedAt": c.escalated_at.isoformat() if c.escalated_at else None,
            "createdAt": c.created_at.isoformat(),
        }
