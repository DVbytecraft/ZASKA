"""Moderation Service — AI-assisted content moderation queue.

Flow:
  1. User reports content → ModerationCase created with rule-based severity (fast)
  2. AI enrichment runs in background (BackgroundTasks) — updates severity + analysis
  3. Admin reviews → resolve / dismiss / escalate
  4. Auto-escalate cron: HIGH/CRITICAL cases unresolved after 4h → ESCALATED

AI provider: Anthropic Claude Haiku (if ANTHROPIC_API_KEY set), else rule-based fallback.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case as sql_case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.models.trust import ModerationCase
from app.models.user import User


_SEVERITY_KEYWORDS = {
    "CRITICAL": ["violence", "arnaque", "viol", "drogue", "criminel", "terroris", "pédophil", "trafic",
                 "murder", "rape", "drug", "criminal", "terrorist", "trafficking"],
    "HIGH":     ["harcèlement", "insulte grave", "menace", "escroquerie", "fraude", "agression",
                 "harassment", "threat", "fraud", "scam", "assault"],
    "MEDIUM":   ["spam", "faux profil", "discrimin", "racis", "sexis",
                 "fake profile", "discriminat", "racist", "sexist"],
    "LOW":      ["incorrect", "inexact", "inapproprié", "désagréable",
                 "incorrect", "inaccurate", "inappropriate"],
}

# Severity order for ORDER BY (CRITICAL=0 → LOW=3)
_SEV_ORDER = sql_case(
    (ModerationCase.severity == "CRITICAL", 0),
    (ModerationCase.severity == "HIGH", 1),
    (ModerationCase.severity == "MEDIUM", 2),
    else_=3,
)

# Delays (seconds) between AI retry attempts: 3 attempts total (2s + 5s gaps)
_RETRY_DELAYS = (2, 5, 10)

# Prompt injection patterns to strip from user-supplied text before AI calls
_INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?previous|disregard|system\s*:|assistant\s*:|"
    r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|#{4,}|prompt\s*:|<system>)",
    re.IGNORECASE,
)


def _sanitize_for_prompt(text: str) -> str:
    """Strip prompt injection patterns and control characters from user input."""
    text = text[:512]
    text = _INJECTION_RE.sub("[FILTERED]", text)
    return "".join(ch for ch in text if ch.isprintable() or ch in "\n\t").strip()


def _rule_based_severity(reason: str) -> str:
    lower = reason.lower()
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        for kw in _SEVERITY_KEYWORDS.get(level, []):
            if kw in lower:
                return level
    return "LOW"


def _ai_severity(reason: str, content_type: str) -> str:
    """Call Claude Haiku to classify severity. Falls back to rule-based on error.

    NOTE: reason must be sanitized before calling this function.
    """
    api_key = settings.anthropic_api_key.strip()
    if not api_key:
        return _rule_based_severity(reason)
    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "You are a content moderation assistant. Classify the severity of a user report.\n\n"
            f"Content type: {content_type}\n"
            f"Report reason: {reason}\n\n"
            "Reply with exactly one word — the severity level: LOW, MEDIUM, HIGH, or CRITICAL."
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
        logger.warning("moderation:ai_severity_fallback error={}", exc)
        return _rule_based_severity(reason)


def _ai_analysis(reason: str, content_type: str) -> str | None:
    """Get a brief AI analysis of the reported content. Returns None if AI unavailable.

    NOTE: reason must be sanitized before calling this function.
    """
    api_key = settings.anthropic_api_key.strip()
    if not api_key:
        return None
    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "You are a content moderation assistant. Analyze this user report and provide "
            "a concise 2-3 sentence summary for the human moderator covering:\n"
            "1. Likely nature of the issue\n"
            "2. Platform risk level\n"
            "3. Recommended action\n\n"
            f"Content type: {content_type}\n"
            f"Report reason: {reason}"
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

    def report_content_sync(
        self,
        reporter_id: str,
        content_type: str,
        reason: str,
        reported_user_id: str | None = None,
        content_id: str | None = None,
    ) -> ModerationCase:
        """Create case immediately with rule-based severity (fast, no blocking AI call).

        AI enrichment should be scheduled as a background task after this returns.
        """
        if content_type not in ("profile", "task", "chat", "review"):
            raise ValueError("content_type must be: profile, task, chat, review")

        severity = _rule_based_severity(reason)

        case = ModerationCase(
            id=str(uuid.uuid4()),
            reporter_id=reporter_id,
            reported_user_id=reported_user_id,
            content_type=content_type,
            content_id=content_id,
            reason=reason,
            ai_analysis=None,
            severity=severity,
            status="PENDING",
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        logger.info("moderation:case_created id={} severity={} (rule-based)", case.id, severity)
        return case

    @staticmethod
    def enrich_with_ai(case_id: str, reason: str, content_type: str) -> None:
        """Run AI severity + analysis and update the case. Uses its own DB session.

        Designed to run as a FastAPI BackgroundTask after report_content_sync().
        Blocking calls are acceptable here since this runs off the request thread.
        All exceptions are caught — a failed enrichment never crashes the worker.
        Retries up to 3 times with exponential backoff (2s, 5s gaps) on AI failures.
        """
        from app.db.session import SessionLocal

        safe_reason = _sanitize_for_prompt(reason)

        db = SessionLocal()
        try:
            severity: str | None = None
            analysis: str | None = None
            last_exc: Exception | None = None

            for attempt, delay in enumerate(_RETRY_DELAYS):
                try:
                    severity = _ai_severity(safe_reason, content_type)
                    analysis = _ai_analysis(safe_reason, content_type)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "moderation:ai_enrich_retry attempt={} id={} error={}",
                        attempt + 1, case_id, exc,
                    )
                    if attempt < len(_RETRY_DELAYS) - 1:
                        time.sleep(delay)

            if last_exc is not None:
                logger.error(
                    "moderation:ai_enrich_exhausted id={} error={}", case_id, last_exc
                )
                return  # leave case with rule-based severity intact

            case = db.get(ModerationCase, case_id)
            if case:
                case.severity = severity
                case.ai_analysis = analysis
                case.updated_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("moderation:ai_enriched id={} severity={}", case_id, severity)
        except Exception as exc:
            logger.error("moderation:ai_enrich_failed id={} error={}", case_id, exc)
        finally:
            db.close()

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

        total = self.db.execute(
            select(func.count()).select_from(q.subquery())
        ).scalar() or 0

        cases = self.db.execute(
            q.order_by(_SEV_ORDER, ModerationCase.created_at.desc())
            .offset(offset)
            .limit(limit)
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
        case.status      = "DISMISSED"
        case.resolution  = reason
        case.resolver_id = resolver_id
        case.resolved_at = now
        case.updated_at  = now
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
