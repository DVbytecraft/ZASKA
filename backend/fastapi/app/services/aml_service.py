from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.aml import AmlCase, AmlEvent
from app.models.location_config import Country
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow


class AmlService:
    def __init__(self, db: Session):
        self.db = db

    def screen_task_creation(self, task_id: str, actor_user_id: str) -> dict | None:
        task = self.db.get(Task, task_id)
        if task is None:
            raise ValueError("Tâche introuvable")
        user = self.db.get(User, actor_user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable")

        amount_eur = self._to_eur(task.price, task.currency)
        country = self._get_country(user.country_code or None)
        reporting_threshold = Decimal(str(country.aml_reporting_threshold)) if country and country.aml_reporting_threshold else Decimal(str(settings.aml_single_tx_threshold_eur))

        repeated_count = self._count_repeated_amounts(actor_user_id, task.price, task.currency)
        monthly_total_eur = self._monthly_total_eur(actor_user_id)

        triggered_rules: list[dict[str, object]] = []
        blocking = False

        if amount_eur >= Decimal(str(settings.aml_single_tx_threshold_eur)):
            triggered_rules.append(
                {
                    "code": "TX_THRESHOLD",
                    "severity": "high",
                    "blocking": True,
                    "detail": f"Montant {amount_eur} EUR >= seuil transactionnel {settings.aml_single_tx_threshold_eur} EUR",
                }
            )
            blocking = True

        if monthly_total_eur >= Decimal(str(settings.aml_monthly_threshold_eur)):
            triggered_rules.append(
                {
                    "code": "MONTHLY_THRESHOLD",
                    "severity": "high",
                    "blocking": False,
                    "detail": f"Volume mensuel {monthly_total_eur} EUR >= seuil mensuel {settings.aml_monthly_threshold_eur} EUR",
                }
            )

        if repeated_count >= settings.aml_repeated_amount_count:
            triggered_rules.append(
                {
                    "code": "REPEATED_AMOUNT",
                    "severity": "medium",
                    "blocking": True,
                    "detail": (
                        f"Montant exact répété {repeated_count} fois en {settings.aml_repeated_amount_days} jours"
                    ),
                }
            )
            blocking = True

        if not triggered_rules:
            task.aml_status = "clear"
            user.aml_status = "clear" if not user.aml_review_required else user.aml_status
            return None

        case = self._open_case(
            user_id=actor_user_id,
            counterparty_user_id=task.assigned_to,
            task_id=task.id,
            case_type=triggered_rules[0]["code"],
            severity=self._highest_severity(triggered_rules),
            amount=task.price,
            currency=task.currency,
            amount_eur=amount_eur,
            summary="Alerte AML déclenchée à la création de la tâche.",
            authority_name=country.aml_authority_name if country else None,
            evidence={
                "taskId": task.id,
                "taskTitle": task.title,
                "reportingThreshold": str(reporting_threshold),
                "monthlyTotalEur": str(monthly_total_eur),
                "repeatedAmountCount": repeated_count,
                "triggeredRules": triggered_rules,
            },
            assigned_admin_user_id=None,
        )

        user.aml_review_required = True
        user.aml_status = "pending_review"
        user.aml_review_reason = triggered_rules[0]["detail"]
        user.aml_last_case_at = datetime.now(timezone.utc)

        if blocking:
            task.aml_status = "pending_review"
            task.aml_case_id = case.id
            task.aml_hold_reason = triggered_rules[0]["detail"]
            task.aml_flagged_at = datetime.now(timezone.utc)

        self.db.flush()
        return self._serialize_case(case)

    def screen_task_before_release(self, task_id: str, actor_user_id: str) -> dict | None:
        task = self.db.execute(select(Task).where(Task.id == task_id).with_for_update()).scalars().one_or_none()
        if task is None:
            raise ValueError("Tâche introuvable")

        client = self.db.get(User, task.created_by)
        tasker = self.db.get(User, task.assigned_to) if task.assigned_to else None
        if client is None:
            raise ValueError("Client introuvable")

        if task.aml_status in {"pending_review", "under_review", "reported"}:
            raise ValueError(task.aml_hold_reason or "Cette tâche est en revue AML. La libération des fonds attend une décision admin.")

        if client.aml_review_required and client.aml_status in {"pending_review", "under_review", "reported"}:
            raise ValueError("Le compte du client est en revue AML. La libération des fonds est temporairement bloquée.")

        triggered_rules: list[dict[str, object]] = []

        age_seconds = (datetime.now(timezone.utc) - task.created_at).total_seconds() if task.created_at else None
        if age_seconds is not None and age_seconds < settings.aml_rapid_validation_minutes * 60:
            triggered_rules.append(
                {
                    "code": "RAPID_VALIDATION",
                    "severity": "high",
                    "detail": (
                        f"Validation en moins de {settings.aml_rapid_validation_minutes} minutes après création de la tâche"
                    ),
                }
            )

        if tasker and client.country_code and tasker.country_code and client.country_code != tasker.country_code:
            pair_count = self._count_same_pair_diaspora(client.id, tasker.id)
            if pair_count >= settings.aml_same_pair_count:
                triggered_rules.append(
                    {
                        "code": "SAME_DIASPORA_PAIR",
                        "severity": "high",
                        "detail": (
                            f"Même binôme diaspora client/tasker détecté {pair_count} fois sur {settings.aml_same_pair_days} jours"
                        ),
                    }
                )

        if not triggered_rules:
            return None

        escrow = self._get_escrow_for_task(task.id)
        country = self._get_country(client.country_code or tasker.country_code if tasker else client.country_code)
        amount = escrow.amount if escrow else task.price
        currency = escrow.currency if escrow else task.currency
        amount_eur = self._to_eur(amount, currency)

        case = self._open_case(
            user_id=client.id,
            counterparty_user_id=tasker.id if tasker else None,
            task_id=task.id,
            escrow_id=escrow.id if escrow else None,
            case_type=triggered_rules[0]["code"],
            severity=self._highest_severity(triggered_rules),
            amount=amount,
            currency=currency,
            amount_eur=amount_eur,
            summary="Alerte AML déclenchée avant libération des fonds.",
            authority_name=country.aml_authority_name if country else None,
            evidence={
                "taskId": task.id,
                "taskStatus": task.status,
                "actorUserId": actor_user_id,
                "triggeredRules": triggered_rules,
            },
            assigned_admin_user_id=None,
        )

        task.aml_status = "pending_review"
        task.aml_case_id = case.id
        task.aml_hold_reason = triggered_rules[0]["detail"]
        task.aml_flagged_at = datetime.now(timezone.utc)
        client.aml_review_required = True
        client.aml_status = "pending_review"
        client.aml_review_reason = triggered_rules[0]["detail"]
        client.aml_last_case_at = datetime.now(timezone.utc)
        self.db.flush()
        raise ValueError(task.aml_hold_reason)

    def list_cases(
        self,
        status: str | None = None,
        severity: str | None = None,
        country_code: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        stmt = select(AmlCase).order_by(desc(AmlCase.created_at)).limit(min(limit, 200))
        if status:
            stmt = stmt.where(AmlCase.status == status)
        if severity:
            stmt = stmt.where(AmlCase.severity == severity)
        if country_code:
            stmt = stmt.where(AmlCase.country_code == country_code.upper())
        if user_id:
            stmt = stmt.where(AmlCase.user_id == user_id)
        cases = self.db.execute(stmt).scalars().all()
        return [self._serialize_case(item) for item in cases]

    def get_case_detail(self, case_id: str) -> dict:
        case = self.db.get(AmlCase, case_id)
        if case is None:
            raise ValueError("Cas AML introuvable")
        payload = self._serialize_case(case)
        payload["events"] = [self._serialize_event(event) for event in self._list_events(case.id)]
        return payload

    def review_case(
        self,
        case_id: str,
        admin_user_id: str,
        decision: str,
        notes: str = "",
        assign_to_user_id: str | None = None,
    ) -> dict:
        case = self.db.get(AmlCase, case_id)
        if case is None:
            raise ValueError("Cas AML introuvable")

        decision_normalized = decision.strip().lower()
        if decision_normalized not in {"under_review", "clear", "reported", "rejected"}:
            raise ValueError("Décision AML invalide")

        case.assigned_admin_user_id = assign_to_user_id or admin_user_id
        case.review_notes = notes or case.review_notes
        case.updated_at = datetime.now(timezone.utc)

        linked_user = self.db.get(User, case.user_id)
        linked_task = self.db.get(Task, case.task_id) if case.task_id else None

        if decision_normalized == "under_review":
            case.status = "under_review"
        elif decision_normalized == "clear":
            case.status = "cleared"
            case.resolved_at = datetime.now(timezone.utc)
            if linked_user:
                linked_user.aml_status = "clear"
                linked_user.aml_review_required = False
                linked_user.aml_review_reason = None
            if linked_task:
                linked_task.aml_status = "clear"
                linked_task.aml_hold_reason = None
        elif decision_normalized == "reported":
            case.status = "reported"
            case.reported_at = datetime.now(timezone.utc)
            case.resolved_at = datetime.now(timezone.utc)
            if linked_user:
                linked_user.aml_status = "reported"
                linked_user.aml_review_required = True
                linked_user.aml_review_reason = notes or "Signalement AML transmis"
            if linked_task:
                linked_task.aml_status = "reported"
                linked_task.aml_hold_reason = notes or linked_task.aml_hold_reason
        elif decision_normalized == "rejected":
            case.status = "rejected"
            case.resolved_at = datetime.now(timezone.utc)
            if linked_user:
                linked_user.aml_status = "blocked"
                linked_user.aml_review_required = True
                linked_user.aml_review_reason = notes or "Cas AML rejeté / bloqué"
            if linked_task:
                linked_task.aml_status = "rejected"
                linked_task.aml_hold_reason = notes or linked_task.aml_hold_reason

        self._add_event(
            case_id=case.id,
            actor_user_id=admin_user_id,
            event_type=f"ADMIN_{decision_normalized.upper()}",
            message=notes or f"Décision admin AML: {decision_normalized}",
            payload={"assignedAdminUserId": case.assigned_admin_user_id},
        )
        self.db.flush()
        return self.get_case_detail(case.id)

    def list_my_cases(self, user_id: str, limit: int = 50) -> list[dict]:
        return self.list_cases(user_id=user_id, limit=limit)

    def _open_case(
        self,
        user_id: str,
        case_type: str,
        severity: str,
        summary: str,
        amount: Decimal | None,
        currency: str | None,
        amount_eur: Decimal | None,
        evidence: dict,
        authority_name: str | None,
        counterparty_user_id: str | None = None,
        task_id: str | None = None,
        escrow_id: str | None = None,
        assigned_admin_user_id: str | None = None,
    ) -> AmlCase:
        existing = None
        if task_id:
            existing = self.db.execute(
                select(AmlCase).where(
                    AmlCase.task_id == task_id,
                    AmlCase.status.in_(["open", "under_review"]),
                )
            ).scalars().first()
        else:
            existing = self.db.execute(
                select(AmlCase).where(
                    AmlCase.user_id == user_id,
                    AmlCase.case_type == case_type,
                    AmlCase.status.in_(["open", "under_review"]),
                )
            ).scalars().first()
        if existing is not None:
            return existing

        user = self.db.get(User, user_id)
        case = AmlCase(
            user_id=user_id,
            counterparty_user_id=counterparty_user_id,
            task_id=task_id,
            escrow_id=escrow_id,
            case_type=case_type,
            severity=severity,
            status="open",
            country_code=user.country_code if user else None,
            amount=amount,
            currency=currency,
            amount_eur=amount_eur,
            summary=summary,
            authority_name=authority_name,
            evidence_json=json.dumps(evidence),
            assigned_admin_user_id=assigned_admin_user_id,
        )
        self.db.add(case)
        self.db.flush()
        self._add_event(
            case_id=case.id,
            actor_user_id=user_id,
            event_type="OPENED",
            message=summary,
            payload=evidence,
        )
        return case

    def _add_event(
        self,
        case_id: str,
        actor_user_id: str | None,
        event_type: str,
        message: str | None = None,
        payload: dict | None = None,
    ) -> None:
        event = AmlEvent(
            aml_case_id=case_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            message=message,
            payload_json=json.dumps(payload) if payload is not None else None,
        )
        self.db.add(event)
        self.db.flush()

    def _list_events(self, case_id: str) -> list[AmlEvent]:
        return self.db.execute(
            select(AmlEvent).where(AmlEvent.aml_case_id == case_id).order_by(AmlEvent.created_at.asc())
        ).scalars().all()

    def _serialize_case(self, case: AmlCase) -> dict:
        return {
            "id": case.id,
            "userId": case.user_id,
            "counterpartyUserId": case.counterparty_user_id,
            "taskId": case.task_id,
            "escrowId": case.escrow_id,
            "caseType": case.case_type,
            "severity": case.severity,
            "status": case.status,
            "countryCode": case.country_code,
            "amount": str(case.amount) if case.amount is not None else None,
            "currency": case.currency,
            "amountEur": str(case.amount_eur) if case.amount_eur is not None else None,
            "summary": case.summary,
            "authorityName": case.authority_name,
            "evidence": json.loads(case.evidence_json) if case.evidence_json else None,
            "reviewNotes": case.review_notes,
            "assignedAdminUserId": case.assigned_admin_user_id,
            "reportedAt": case.reported_at.isoformat() if case.reported_at else None,
            "resolvedAt": case.resolved_at.isoformat() if case.resolved_at else None,
            "createdAt": case.created_at.isoformat() if case.created_at else None,
            "updatedAt": case.updated_at.isoformat() if case.updated_at else None,
        }

    def _serialize_event(self, event: AmlEvent) -> dict:
        return {
            "id": event.id,
            "amlCaseId": event.aml_case_id,
            "actorUserId": event.actor_user_id,
            "eventType": event.event_type,
            "message": event.message,
            "payload": json.loads(event.payload_json) if event.payload_json else None,
            "createdAt": event.created_at.isoformat() if event.created_at else None,
        }

    def _get_country(self, country_code: str | None) -> Country | None:
        if not country_code:
            return None
        return self.db.execute(
            select(Country).where(Country.iso_code == country_code.upper())
        ).scalars().one_or_none()

    def _count_repeated_amounts(self, user_id: str, amount: Decimal, currency: str) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=settings.aml_repeated_amount_days)
        tasks = self.db.execute(
            select(Task).where(
                Task.created_by == user_id,
                Task.currency == currency.upper(),
                Task.price == amount,
                Task.created_at >= since,
            )
        ).scalars().all()
        return len(tasks)

    def _monthly_total_eur(self, user_id: str) -> Decimal:
        since = datetime.now(timezone.utc) - timedelta(days=30)
        tasks = self.db.execute(
            select(Task).where(
                Task.created_by == user_id,
                Task.created_at >= since,
                Task.status != "CANCELLED",
            )
        ).scalars().all()
        total = Decimal("0")
        for task in tasks:
            total += self._to_eur(task.price, task.currency)
        return total

    def _count_same_pair_diaspora(self, client_user_id: str, tasker_user_id: str) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=settings.aml_same_pair_days)
        tasks = self.db.execute(
            select(Task).where(
                Task.created_by == client_user_id,
                Task.assigned_to == tasker_user_id,
                Task.created_at >= since,
            )
        ).scalars().all()
        return len(tasks)

    def _get_escrow_for_task(self, task_id: str) -> Escrow | None:
        return self.db.execute(select(Escrow).where(Escrow.task_id == task_id)).scalars().first()

    def _highest_severity(self, triggered_rules: list[dict[str, object]]) -> str:
        order = {"low": 0, "medium": 1, "high": 2, "urgent": 3}
        best = "low"
        for rule in triggered_rules:
            severity = str(rule.get("severity", "low")).lower()
            if order.get(severity, 0) > order.get(best, 0):
                best = severity
        return best

    def _to_eur(self, amount: Decimal, currency: str | None) -> Decimal:
        if currency is None:
            return Decimal("0")
        code = currency.upper()
        amount_dec = Decimal(str(amount))
        usd_to_eur = Decimal(str(settings.fx_usd_to_eur))
        if code == "EUR":
            return amount_dec
        if code == "USD":
            return amount_dec * usd_to_eur

        per_usd = {
            "XOF": Decimal(str(settings.fx_usd_to_xof)),
            "XAF": Decimal(str(settings.fx_usd_to_xaf)),
            "GHS": Decimal(str(settings.fx_usd_to_ghs)),
            "NGN": Decimal(str(settings.fx_usd_to_ngn)),
            "KES": Decimal(str(settings.fx_usd_to_kes)),
            "GBP": Decimal(str(settings.fx_usd_to_gbp)),
            "CAD": Decimal(str(settings.fx_usd_to_cad)),
        }.get(code)

        if per_usd is None or per_usd == 0:
            return amount_dec

        usd_amount = amount_dec / per_usd
        return usd_amount * usd_to_eur
