from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.models.kyc import KycSubmission
from app.models.notification import Notification
from app.models.social_protection import SocialProtectionEvent
from app.models.user import User
from app.models.wallet import Transaction, Wallet
from app.services.trust_service import TrustService
from app.services.wallet_service import (
    SOCIAL_SPLIT_LINES,
    InsufficientFundsError,
    WalletService,
)

HEALTH_ACTIVITY_ALERT = "HEALTH_ACTIVITY_ALERT"
PENSION_PROGRESS_ALERT = "PENSION_PROGRESS_ALERT"
SMOOTHING_INTERVENTION = "SMOOTHING_INTERVENTION"
SMOOTHING_REIMBURSEMENT = "SMOOTHING_REIMBURSEMENT"


def _month_start(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _previous_month_keys(period_key: str, count: int) -> list[str]:
    year, month = [int(part) for part in period_key.split("-")]
    keys: list[str] = []
    current_year = year
    current_month = month
    for _ in range(count):
        current_year, current_month = _month_start(current_year, current_month)
        keys.append(f"{current_year:04d}-{current_month:02d}")
    return keys


class SocialProtectionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallet_service = WalletService(db)

    def run_periodic_cycle(self, reference_date: datetime | None = None) -> dict[str, int]:
        now = reference_date or datetime.now(timezone.utc)
        results = {
            "taskers_scanned": 0,
            "health_alerts_sent": 0,
            "pension_alerts_sent": 0,
            "smoothing_interventions": 0,
            "smoothing_reimbursements": 0,
        }

        taskers = (
            self.db.execute(
                select(User).where(
                    User.role == "tasker",
                    User.is_suspended == False,  # noqa: E712
                    User.is_locked == False,  # noqa: E712
                )
            )
            .scalars()
            .all()
        )

        for tasker in taskers:
            results["taskers_scanned"] += 1
            try:
                summary = self._build_tasker_monthly_summary(tasker.id)
                for currency, monthly in summary.items():
                    results["health_alerts_sent"] += self._maybe_send_health_activity_alert(
                        tasker=tasker,
                        currency=currency,
                        monthly=monthly,
                        now=now,
                    )
                    results["smoothing_interventions"] += self._maybe_apply_smoothing_intervention(
                        tasker=tasker,
                        currency=currency,
                        monthly=monthly,
                        now=now,
                    )
                    results["smoothing_reimbursements"] += self._maybe_apply_smoothing_reimbursement(
                        tasker=tasker,
                        currency=currency,
                        monthly=monthly,
                        now=now,
                    )
                    results["pension_alerts_sent"] += self._maybe_send_pension_progress_alert(
                        tasker=tasker,
                        currency=currency,
                        monthly=monthly,
                        now=now,
                    )
            except Exception as exc:
                logger.error("social_protection_cycle_failed tasker={} error={}", tasker.id, exc)
                self.db.rollback()

        return results

    def get_admin_overview(self) -> dict[str, object]:
        taskers = (
            self.db.execute(select(User).where(User.role == "tasker"))
            .scalars()
            .all()
        )
        users = self.db.execute(select(User)).scalars().all()
        currencies: dict[str, dict[str, object]] = {}
        totals = {
            "countries_active": len({user.country_code for user in users if user.country_code}),
            "registered_users": len(users),
            "taskers": len(taskers),
            "taskers_protected": 0,
            "kyc_due_soon": 0,
        }

        by_country: dict[str, dict[str, int | str]] = defaultdict(lambda: {
            "country_code": "XX",
            "users": 0,
            "taskers": 0,
            "protected_taskers": 0,
        })

        now = datetime.now(timezone.utc)
        for user in users:
            country_code = user.country_code or "UNSPECIFIED"
            bucket = by_country[country_code]
            bucket["country_code"] = country_code
            bucket["users"] += 1
            if user.role == "tasker":
                bucket["taskers"] += 1

        tasker_rows: list[dict[str, object]] = []
        for tasker in taskers:
            overview = self.wallet_service.get_social_protection_overview(tasker.id)
            badge = overview.get("badge", {})
            if badge.get("code") == "PROTECTED_TASKER":
                totals["taskers_protected"] += 1
                country_code = tasker.country_code or "UNSPECIFIED"
                by_country[country_code]["protected_taskers"] += 1

            latest_kyc = (
                self.db.execute(
                    select(KycSubmission)
                    .where(KycSubmission.user_id == tasker.id)
                    .order_by(KycSubmission.created_at.desc())
                )
                .scalars()
                .first()
            )
            if latest_kyc and latest_kyc.expires_at:
                days_remaining = (latest_kyc.expires_at.date() - now.date()).days
                if 0 < days_remaining <= 30:
                    totals["kyc_due_soon"] += 1

            currencies_summary = []
            for item in overview.get("currencies", []):
                currency = item["currency"]
                currency_bucket = currencies.setdefault(currency, {
                    "currency": currency,
                    "pension_balance_total": Decimal("0"),
                    "health_balance_total": Decimal("0"),
                    "smoothing_balance_total": Decimal("0"),
                    "pension_contributions_total": Decimal("0"),
                    "health_contributions_total": Decimal("0"),
                    "smoothing_contributions_total": Decimal("0"),
                    "smoothing_interventions_month": 0,
                    "smoothing_outstanding_total": Decimal("0"),
                    "simulated_interest_month": Decimal("0"),
                })
                currency_bucket["pension_contributions_total"] += Decimal(item["pension"]["total_contributed"])
                currency_bucket["health_contributions_total"] += Decimal(item["health"]["total_paid_to_authorities"])
                currency_bucket["smoothing_contributions_total"] += Decimal(item["smoothing"]["total_contributed"])
                currency_bucket["smoothing_outstanding_total"] += Decimal(item["smoothing"].get("outstanding_reconstitution", "0"))
                currency_bucket["smoothing_interventions_month"] += len([
                    event for event in item["smoothing"]["interventions"]
                    if str(event.get("period_key", "")).startswith(now.strftime("%Y-%m"))
                ])
                interest_month = (
                    Decimal(item["pension"]["total_contributed"]) * Decimal("0.06") / Decimal("12")
                    + Decimal(item["smoothing"]["total_contributed"]) * Decimal("0.04") / Decimal("12")
                ).quantize(Decimal("0.000001"))
                currency_bucket["simulated_interest_month"] += interest_month
                currencies_summary.append({
                    "currency": currency,
                    "badge": badge.get("label"),
                    "pension_total": item["pension"]["total_contributed"],
                    "health_status": item["health"]["status"],
                    "smoothing_outstanding": item["smoothing"].get("outstanding_reconstitution", "0"),
                })

            tasker_rows.append({
                "tasker_id": tasker.id,
                "tasker_name": " ".join(filter(None, [tasker.first_name, tasker.last_name])) or tasker.email or tasker.id,
                "country_code": tasker.country_code,
                "badge": badge.get("label"),
                "active_months": overview.get("active_months", 0),
                "completed_tasks": overview.get("total_completed_tasks", 0),
                "currencies": currencies_summary,
            })

        for currency_code, bucket in currencies.items():
            bucket["pension_balance_total"] = str(self._system_wallet_balance(settings.pension_fund_user_id, currency_code))
            bucket["health_balance_total"] = str(self._system_wallet_balance(settings.health_fund_user_id, currency_code))
            bucket["smoothing_balance_total"] = str(self._system_wallet_balance(settings.smoothing_fund_user_id, currency_code))
            bucket["pension_contributions_total"] = str(bucket["pension_contributions_total"])
            bucket["health_contributions_total"] = str(bucket["health_contributions_total"])
            bucket["smoothing_contributions_total"] = str(bucket["smoothing_contributions_total"])
            bucket["smoothing_outstanding_total"] = str(bucket["smoothing_outstanding_total"])
            bucket["simulated_interest_month"] = str(bucket["simulated_interest_month"])

        return {
            "totals": totals,
            "currencies": list(currencies.values()),
            "countries": sorted(by_country.values(), key=lambda row: int(row["users"]), reverse=True),
            "taskers": sorted(tasker_rows, key=lambda row: int(row["completed_tasks"]), reverse=True)[:200],
            "generated_at": now.isoformat(),
        }

    def get_accounting_overview(self) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        transactions = self.db.execute(
            select(Transaction, Wallet)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(
                Transaction.status == "completed",
                Transaction.type == "credit",
                Transaction.reference.like("escrow_release:%"),
            )
        ).all()

        summary = {
            "released_tasks": set(),
            "currencies": set(),
        }
        by_currency: dict[str, dict[str, object]] = {}

        for tx, wallet in transactions:
            meta = self.wallet_service._parse_metadata(tx)
            split_line = meta.get("split_line")
            if split_line not in SOCIAL_SPLIT_LINES:
                continue
            currency = wallet.currency
            summary["currencies"].add(currency)
            if meta.get("task_id"):
                summary["released_tasks"].add(str(meta["task_id"]))

            bucket = by_currency.setdefault(currency, self._new_accounting_bucket(currency))
            amount = Decimal(str(tx.amount))
            created_at = tx.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            self._add_split_amount(bucket["lifetime"], split_line, amount)
            if created_at.date() == now.date():
                self._add_split_amount(bucket["today"], split_line, amount)
            if created_at.year == now.year and created_at.month == now.month:
                self._add_split_amount(bucket["month"], split_line, amount)
            if created_at.year == now.year:
                self._add_split_amount(bucket["year"], split_line, amount)

        for currency, bucket in by_currency.items():
            bucket["fund_balances"] = {
                "zaska_operations": self._wallet_snapshot(settings.zaska_wallet_user_id, currency),
                "pension_fund": self._wallet_snapshot(settings.pension_fund_user_id, currency),
                "health_fund": self._wallet_snapshot(settings.health_fund_user_id, currency),
                "smoothing_fund": self._wallet_snapshot(settings.smoothing_fund_user_id, currency),
            }
            bucket["event_totals"] = self._accounting_event_totals(currency, now)
            bucket["simulated_interest"] = {
                "pension_month": str(
                    (Decimal(bucket["fund_balances"]["pension_fund"]["wallet_balance"]) * Decimal("0.06") / Decimal("12")).quantize(Decimal("0.000001"))
                ),
                "smoothing_month": str(
                    (Decimal(bucket["fund_balances"]["smoothing_fund"]["wallet_balance"]) * Decimal("0.04") / Decimal("12")).quantize(Decimal("0.000001"))
                ),
            }
            bucket["lifetime"] = self._stringify_amount_map(bucket["lifetime"])
            bucket["today"] = self._stringify_amount_map(bucket["today"])
            bucket["month"] = self._stringify_amount_map(bucket["month"])
            bucket["year"] = self._stringify_amount_map(bucket["year"])

        return {
            "summary": {
                "released_tasks_count": len(summary["released_tasks"]),
                "currencies_count": len(summary["currencies"]),
            },
            "currencies": list(by_currency.values()),
            "tasker_badges": TrustService(self.db).get_tasker_badge_overview(),
            "generated_at": now.isoformat(),
        }

    def _build_tasker_monthly_summary(self, user_id: str) -> dict[str, dict[str, object]]:
        entries = [
            self.wallet_service._build_split_history_entry(tx)
            for tx in self.wallet_service._list_tasker_split_transactions(user_id=user_id, currency=None)
        ]
        by_currency: dict[str, dict[str, object]] = {}
        for entry in entries:
            currency = str(entry["currency"])
            currency_bucket = by_currency.setdefault(
                currency,
                {
                    "entries": [],
                    "monthly_gross": defaultdict(lambda: Decimal("0")),
                    "monthly_health": defaultdict(lambda: Decimal("0")),
                    "monthly_pension": defaultdict(lambda: Decimal("0")),
                    "total_pension": Decimal("0"),
                },
            )
            currency_bucket["entries"].append(entry)  # type: ignore[index]
            month_key = str(entry["released_at"])[:7]
            currency_bucket["monthly_gross"][month_key] += Decimal(entry["gross_amount"])  # type: ignore[index]
            currency_bucket["monthly_health"][month_key] += Decimal(entry["split"]["health_fund"])  # type: ignore[index]
            pension_amount = Decimal(entry["split"]["pension_fund"])
            currency_bucket["monthly_pension"][month_key] += pension_amount  # type: ignore[index]
            currency_bucket["total_pension"] += pension_amount  # type: ignore[index]
        return by_currency

    def _qualifies_for_insufficient_month(
        self,
        monthly_gross: dict[str, Decimal],
        period_key: str,
    ) -> tuple[bool, Decimal, Decimal]:
        previous_keys = _previous_month_keys(period_key, 3)
        previous_amounts = [monthly_gross.get(key, Decimal("0")) for key in previous_keys]
        if any(amount <= Decimal("0") for amount in previous_amounts):
            return False, Decimal("0"), Decimal("0")
        previous_average = sum(previous_amounts) / Decimal("3")
        current_gross = monthly_gross.get(period_key, Decimal("0"))
        threshold = previous_average * Decimal("0.5")
        return current_gross < threshold, current_gross, previous_average

    def _maybe_send_health_activity_alert(
        self,
        tasker: User,
        currency: str,
        monthly: dict[str, object],
        now: datetime,
    ) -> int:
        if now.day < 20:
            return 0
        period_key = now.strftime("%Y-%m")
        monthly_gross = monthly["monthly_gross"]  # type: ignore[assignment]
        is_insufficient, current_gross, previous_average = self._qualifies_for_insufficient_month(monthly_gross, period_key)
        if not is_insufficient:
            return 0
        if self._event_exists(tasker.id, HEALTH_ACTIVITY_ALERT, period_key, currency):
            return 0
        self._create_notification(
            user_id=tasker.id,
            notif_type="warning",
            title="Couverture santé sous surveillance",
            body=(
                "Votre activité ce mois est insuffisante pour maintenir votre couverture santé. "
                "Le fonds de lissage interviendra automatiquement si nécessaire."
            ),
        )
        self._create_event(
            user_id=tasker.id,
            event_type=HEALTH_ACTIVITY_ALERT,
            currency=currency,
            period_key=period_key,
            amount=previous_average - current_gross,
            reference=f"social-alert:{tasker.id}:{currency}:{period_key}",
            metadata={
                "current_gross": str(current_gross),
                "previous_average_gross": str(previous_average),
            },
        )
        return 1

    def _maybe_apply_smoothing_intervention(
        self,
        tasker: User,
        currency: str,
        monthly: dict[str, object],
        now: datetime,
    ) -> int:
        if now.day < 20:
            return 0
        if not settings.smoothing_fund_user_id or not settings.health_fund_user_id:
            logger.warning("social_smoothing skipped missing system fund ids currency={}", currency)
            return 0
        period_key = now.strftime("%Y-%m")
        if self._event_exists(tasker.id, SMOOTHING_INTERVENTION, period_key, currency):
            return 0

        monthly_gross = monthly["monthly_gross"]  # type: ignore[assignment]
        monthly_health = monthly["monthly_health"]  # type: ignore[assignment]
        is_insufficient, current_gross, previous_average = self._qualifies_for_insufficient_month(monthly_gross, period_key)
        if not is_insufficient:
            return 0

        previous_health_keys = _previous_month_keys(period_key, 3)
        previous_health_amounts = [monthly_health.get(key, Decimal("0")) for key in previous_health_keys]
        previous_health_average = sum(previous_health_amounts) / Decimal("3")
        current_health = monthly_health.get(period_key, Decimal("0"))
        missing_health = max(Decimal("0"), previous_health_average - current_health)
        available_balance = self._tasker_smoothing_available_balance(tasker.id, currency, monthly)
        intervention_amount = min(missing_health, available_balance)
        if intervention_amount <= Decimal("0"):
            return 0

        reference = f"social-smoothing:{tasker.id}:{currency}:{period_key}"
        self.wallet_service.transfer_atomic(
            from_user_id=settings.smoothing_fund_user_id,
            to_user_id=settings.health_fund_user_id,
            currency=currency,
            amount=intervention_amount,
            reference=reference,
            note=f"Health coverage maintenance for tasker {tasker.id}",
        )
        self._create_notification(
            user_id=tasker.id,
            notif_type="success",
            title="Couverture santé maintenue",
            body=(
                "Votre couverture santé a été maintenue automatiquement "
                "ce mois grâce au fonds de lissage."
            ),
        )
        self._create_event(
            user_id=tasker.id,
            event_type=SMOOTHING_INTERVENTION,
            currency=currency,
            period_key=period_key,
            amount=intervention_amount,
            reference=reference,
            metadata={
                "current_gross": str(current_gross),
                "previous_average_gross": str(previous_average),
                "current_health": str(current_health),
                "previous_average_health": str(previous_health_average),
            },
        )
        return 1

    def _maybe_apply_smoothing_reimbursement(
        self,
        tasker: User,
        currency: str,
        monthly: dict[str, object],
        now: datetime,
    ) -> int:
        if now.day < 20:
            return 0
        if not settings.smoothing_fund_user_id:
            return 0
        period_key = now.strftime("%Y-%m")
        if self._event_exists(tasker.id, SMOOTHING_REIMBURSEMENT, period_key, currency):
            return 0

        monthly_gross = monthly["monthly_gross"]  # type: ignore[assignment]
        previous_keys = _previous_month_keys(period_key, 3)
        previous_amounts = [monthly_gross.get(key, Decimal("0")) for key in previous_keys]
        if any(amount <= Decimal("0") for amount in previous_amounts):
            return 0
        previous_average = sum(previous_amounts) / Decimal("3")
        current_gross = monthly_gross.get(period_key, Decimal("0"))
        if current_gross < previous_average:
            return 0

        outstanding = self._tasker_smoothing_outstanding(tasker.id, currency)
        if outstanding <= Decimal("0"):
            return 0

        reimbursement_target = min(outstanding, (current_gross * Decimal("0.01")).quantize(Decimal("0.000001")))
        if reimbursement_target <= Decimal("0"):
            return 0

        try:
            reference = f"social-reimbursement:{tasker.id}:{currency}:{period_key}"
            self.wallet_service.transfer_atomic(
                from_user_id=tasker.id,
                to_user_id=settings.smoothing_fund_user_id,
                currency=currency,
                amount=reimbursement_target,
                reference=reference,
                note="Progressive smoothing fund reconstitution",
            )
        except InsufficientFundsError:
            return 0

        self._create_notification(
            user_id=tasker.id,
            notif_type="info",
            title="Reconstitution du fonds de lissage",
            body=(
                "Une reconstitution progressive de 1% a été effectuée ce mois "
                "pour réalimenter votre fonds de lissage."
            ),
        )
        self._create_event(
            user_id=tasker.id,
            event_type=SMOOTHING_REIMBURSEMENT,
            currency=currency,
            period_key=period_key,
            amount=reimbursement_target,
            reference=reference,
            metadata={
                "current_gross": str(current_gross),
                "previous_average_gross": str(previous_average),
                "outstanding_before": str(outstanding),
            },
        )
        return 1

    def _maybe_send_pension_progress_alert(
        self,
        tasker: User,
        currency: str,
        monthly: dict[str, object],
        now: datetime,
    ) -> int:
        period_key = now.strftime("%Y-%m")
        if self._event_exists(tasker.id, PENSION_PROGRESS_ALERT, period_key, currency):
            return 0

        total_pension = monthly["total_pension"]  # type: ignore[assignment]
        monthly_pension = monthly["monthly_pension"]  # type: ignore[assignment]
        current_month_pension = monthly_pension.get(period_key, Decimal("0"))
        if total_pension <= Decimal("0") and current_month_pension <= Decimal("0"):
            return 0

        overview = self.wallet_service.get_social_protection_overview(tasker.id)
        currency_summary = next(
            (item for item in overview.get("currencies", []) if item.get("currency") == currency),
            None,
        )
        projected = "0"
        if currency_summary:
            projected = currency_summary["pension"]["projected_monthly_pension"]

        self._create_notification(
            user_id=tasker.id,
            notif_type="info",
            title="Progression retraite",
            body=(
                f"Ce mois vous avez accumulé {current_month_pension} {currency} pour votre retraite. "
                f"Total depuis le début : {total_pension} {currency}. "
                f"Projection à 60 ans : {projected} {currency}/mois."
            ),
        )
        self._create_event(
            user_id=tasker.id,
            event_type=PENSION_PROGRESS_ALERT,
            currency=currency,
            period_key=period_key,
            amount=current_month_pension,
            reference=f"social-pension:{tasker.id}:{currency}:{period_key}",
            metadata={
                "total_pension": str(total_pension),
                "projected_monthly_pension": str(projected),
            },
        )
        return 1

    def _tasker_smoothing_available_balance(
        self,
        user_id: str,
        currency: str,
        monthly: dict[str, object],
    ) -> Decimal:
        entries = monthly["entries"]  # type: ignore[assignment]
        total_contributed = sum(Decimal(entry["split"]["smoothing_fund"]) for entry in entries)
        outstanding = self._tasker_smoothing_outstanding(user_id, currency)
        return max(Decimal("0"), total_contributed - outstanding)

    def _tasker_smoothing_outstanding(self, user_id: str, currency: str) -> Decimal:
        events = self._list_events(user_id=user_id, currency=currency)
        interventions = sum(event.amount for event in events if event.event_type == SMOOTHING_INTERVENTION)
        reimbursements = sum(event.amount for event in events if event.event_type == SMOOTHING_REIMBURSEMENT)
        return max(Decimal("0"), interventions - reimbursements)

    def _list_events(self, user_id: str, currency: str | None = None) -> list[SocialProtectionEvent]:
        stmt = select(SocialProtectionEvent).where(SocialProtectionEvent.user_id == user_id)
        if currency:
            stmt = stmt.where(SocialProtectionEvent.currency == currency)
        return self.db.execute(stmt.order_by(SocialProtectionEvent.created_at.desc())).scalars().all()

    def _event_exists(self, user_id: str, event_type: str, period_key: str, currency: str) -> bool:
        stmt = select(SocialProtectionEvent).where(
            SocialProtectionEvent.user_id == user_id,
            SocialProtectionEvent.event_type == event_type,
            SocialProtectionEvent.period_key == period_key,
            SocialProtectionEvent.currency == currency,
        )
        return self.db.execute(stmt).scalars().first() is not None

    def _create_event(
        self,
        user_id: str,
        event_type: str,
        currency: str,
        period_key: str,
        amount: Decimal,
        reference: str,
        metadata: dict[str, str],
    ) -> None:
        if self._event_exists(user_id, event_type, period_key, currency):
            return
        event = SocialProtectionEvent(
            user_id=user_id,
            event_type=event_type,
            currency=currency,
            period_key=period_key,
            amount=amount,
            reference=reference,
            metadata_json=json.dumps(metadata),
        )
        self.db.add(event)
        self.db.commit()

    def _create_notification(self, user_id: str, notif_type: str, title: str, body: str) -> None:
        self.db.add(Notification(user_id=user_id, type=notif_type, title=title, body=body))
        self.db.commit()

    def _system_wallet_balance(self, user_id: str | None, currency: str) -> Decimal:
        if not user_id:
            return Decimal("0")
        try:
            return self.wallet_service.get_balance(user_id, currency)
        except Exception:
            return Decimal("0")

    @staticmethod
    def _new_accounting_bucket(currency: str) -> dict[str, object]:
        return {
            "currency": currency,
            "lifetime": {line: Decimal("0") for line in SOCIAL_SPLIT_LINES},
            "today": {line: Decimal("0") for line in SOCIAL_SPLIT_LINES},
            "month": {line: Decimal("0") for line in SOCIAL_SPLIT_LINES},
            "year": {line: Decimal("0") for line in SOCIAL_SPLIT_LINES},
        }

    @staticmethod
    def _add_split_amount(bucket: dict[str, Decimal], split_line: str, amount: Decimal) -> None:
        bucket[split_line] += amount

    @staticmethod
    def _stringify_amount_map(bucket: dict[str, Decimal]) -> dict[str, str]:
        return {key: str(value) for key, value in bucket.items()}

    def _wallet_snapshot(self, user_id: str | None, currency: str) -> dict[str, str]:
        if not user_id:
            return {
                "wallet_balance": "0",
                "ledger_balance": "0",
                "drift": "0",
            }
        try:
            wallet_balance = self.wallet_service.get_balance(user_id, currency)
            ledger_balance = self.wallet_service.recompute_balance_from_ledger(user_id, currency)
        except Exception:
            wallet_balance = Decimal("0")
            ledger_balance = Decimal("0")
        return {
            "wallet_balance": str(wallet_balance),
            "ledger_balance": str(ledger_balance),
            "drift": str(wallet_balance - ledger_balance),
        }

    def _accounting_event_totals(self, currency: str, now: datetime) -> dict[str, object]:
        events = self.db.execute(
            select(SocialProtectionEvent).where(SocialProtectionEvent.currency == currency)
        ).scalars().all()
        interventions_total = Decimal("0")
        reimbursements_total = Decimal("0")
        interventions_month = 0
        reimbursements_month = 0

        for event in events:
            if event.event_type == SMOOTHING_INTERVENTION:
                interventions_total += event.amount
                if event.period_key == now.strftime("%Y-%m"):
                    interventions_month += 1
            elif event.event_type == SMOOTHING_REIMBURSEMENT:
                reimbursements_total += event.amount
                if event.period_key == now.strftime("%Y-%m"):
                    reimbursements_month += 1

        return {
            "smoothing_interventions_total": str(interventions_total),
            "smoothing_reimbursements_total": str(reimbursements_total),
            "smoothing_interventions_month": interventions_month,
            "smoothing_reimbursements_month": reimbursements_month,
        }
