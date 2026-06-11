from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import SubscriptionPlan, SubscriptionUsage, UserSubscription
from app.models.task import Task
from app.models.user import User

_DEFAULT_PLANS = [
    {
        "code": "ZASKA_PRO_MONTHLY",
        "name": "Zaska Pro",
        "description": "Abonnement général avec accès prioritaire, support prioritaire et diaspora incluse.",
        "subscription_type": "GENERAL",
        "service_category": None,
        "price_monthly": Decimal("4.99"),
        "currency": "EUR",
        "tasks_included_monthly": None,
        "priority_enabled": True,
        "diaspora_included": True,
        "support_priority": True,
    },
    {
        "code": "HOME_CLEANING_MONTHLY",
        "name": "Abonnement Ménage",
        "description": "Quota mensuel pour services de ménage.",
        "subscription_type": "SERVICE",
        "service_category": "CLEANING",
        "price_monthly": Decimal("29.99"),
        "currency": "EUR",
        "tasks_included_monthly": 4,
        "priority_enabled": True,
        "diaspora_included": False,
        "support_priority": False,
    },
    {
        "code": "GROCERIES_MONTHLY",
        "name": "Abonnement Courses",
        "description": "Quota mensuel pour services de courses et approvisionnement.",
        "subscription_type": "SERVICE",
        "service_category": "GROCERIES",
        "price_monthly": Decimal("19.99"),
        "currency": "EUR",
        "tasks_included_monthly": 4,
        "priority_enabled": False,
        "diaspora_included": False,
        "support_priority": False,
    },
    {
        "code": "SENIOR_ASSISTANCE_MONTHLY",
        "name": "Abonnement Assistance Senior",
        "description": "Quota mensuel pour accompagnement des seniors par taskers certifiés.",
        "subscription_type": "SERVICE",
        "service_category": "SENIOR_ASSISTANCE",
        "price_monthly": Decimal("39.99"),
        "currency": "EUR",
        "tasks_included_monthly": 2,
        "priority_enabled": True,
        "diaspora_included": False,
        "support_priority": True,
    },
]


class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_catalog(self) -> None:
        changed = False
        for item in _DEFAULT_PLANS:
            existing = self.db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.code == item["code"])
            ).scalars().one_or_none()
            if existing is None:
                self.db.add(
                    SubscriptionPlan(
                        id=str(uuid.uuid4()),
                        code=item["code"],
                        name=item["name"],
                        description=item["description"],
                        subscription_type=item["subscription_type"],
                        service_category=item["service_category"],
                        billing_cycle="MONTHLY",
                        price_monthly=item["price_monthly"],
                        currency=item["currency"],
                        tasks_included_monthly=item["tasks_included_monthly"],
                        priority_enabled=item["priority_enabled"],
                        diaspora_included=item["diaspora_included"],
                        support_priority=item["support_priority"],
                        is_active=True,
                        is_public=True,
                    )
                )
                changed = True
                continue
            for field in (
                "name",
                "description",
                "subscription_type",
                "service_category",
                "price_monthly",
                "currency",
                "tasks_included_monthly",
                "priority_enabled",
                "diaspora_included",
                "support_priority",
            ):
                if getattr(existing, field) != item[field]:
                    setattr(existing, field, item[field])
                    changed = True
        if changed:
            self.db.commit()

    def list_public_plans(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        stmt = select(SubscriptionPlan).where(SubscriptionPlan.is_public == True)  # noqa: E712
        if not include_inactive:
            stmt = stmt.where(SubscriptionPlan.is_active == True)  # noqa: E712
        plans = self.db.execute(stmt.order_by(SubscriptionPlan.subscription_type.asc(), SubscriptionPlan.name.asc())).scalars().all()
        return [self._serialize_plan(plan) for plan in plans]

    def list_all_plans(self) -> list[dict[str, Any]]:
        plans = self.db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.name.asc())).scalars().all()
        return [self._serialize_plan(plan) for plan in plans]

    def create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        code = str(payload["code"]).strip().upper()
        if self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code)).scalars().one_or_none():
            raise ValueError("Un plan avec ce code existe déjà.")
        plan = SubscriptionPlan(
            id=str(uuid.uuid4()),
            code=code,
            name=str(payload["name"]).strip(),
            description=(str(payload["description"]).strip() if payload.get("description") else None),
            subscription_type=str(payload["subscription_type"]).strip().upper(),
            service_category=(str(payload["service_category"]).strip().upper() if payload.get("service_category") else None),
            billing_cycle="MONTHLY",
            price_monthly=Decimal(str(payload["price_monthly"])),
            currency=str(payload["currency"]).strip().upper(),
            tasks_included_monthly=payload.get("tasks_included_monthly"),
            overage_price=(Decimal(str(payload["overage_price"])) if payload.get("overage_price") is not None else None),
            priority_enabled=bool(payload.get("priority_enabled", False)),
            diaspora_included=bool(payload.get("diaspora_included", False)),
            support_priority=bool(payload.get("support_priority", False)),
            is_active=bool(payload.get("is_active", True)),
            is_public=bool(payload.get("is_public", True)),
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return self._serialize_plan(plan)

    def update_plan(self, plan_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.db.get(SubscriptionPlan, plan_id)
        if plan is None:
            raise ValueError("Plan introuvable.")
        for field in (
            "name",
            "description",
            "tasks_included_monthly",
            "priority_enabled",
            "diaspora_included",
            "support_priority",
            "is_active",
            "is_public",
        ):
            if field in payload and payload[field] is not None:
                setattr(plan, field, payload[field])
        if "subscription_type" in payload and payload["subscription_type"]:
            plan.subscription_type = str(payload["subscription_type"]).strip().upper()
        if "service_category" in payload:
            plan.service_category = str(payload["service_category"]).strip().upper() if payload["service_category"] else None
        if "price_monthly" in payload and payload["price_monthly"] is not None:
            plan.price_monthly = Decimal(str(payload["price_monthly"]))
        if "currency" in payload and payload["currency"]:
            plan.currency = str(payload["currency"]).strip().upper()
        if "overage_price" in payload:
            plan.overage_price = Decimal(str(payload["overage_price"])) if payload["overage_price"] is not None else None
        self.db.commit()
        self.db.refresh(plan)
        return self._serialize_plan(plan)

    def subscribe_user(
        self,
        *,
        user_id: str,
        plan_code: str,
        country_code: str | None = None,
        source: str = "self_service",
        auto_renew: bool = True,
    ) -> dict[str, Any]:
        plan = self._get_active_plan(plan_code)
        self._ensure_no_conflicting_active_subscription(user_id, plan)
        now = datetime.now(timezone.utc)
        renewal = now + timedelta(days=30)
        subscription = UserSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            plan_id=plan.id,
            plan_code=plan.code,
            subscription_type=plan.subscription_type,
            service_category=plan.service_category,
            status="ACTIVE",
            price_monthly=plan.price_monthly,
            currency=plan.currency,
            tasks_included_monthly=plan.tasks_included_monthly,
            tasks_used_this_month=0,
            auto_renew=auto_renew,
            started_at=now,
            renewal_date=renewal,
            next_reset_at=renewal,
            country_code=(country_code or "").upper() or None,
            source=source,
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return self._serialize_user_subscription(subscription)

    def list_user_subscriptions(self, user_id: str) -> list[dict[str, Any]]:
        self._reset_due_cycles(user_id)
        rows = self.db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id).order_by(UserSubscription.created_at.desc())
        ).scalars().all()
        return [self._serialize_user_subscription(row) for row in rows]

    def get_user_summary(self, user_id: str) -> dict[str, Any]:
        self._reset_due_cycles(user_id)
        subscriptions = self.list_user_subscriptions(user_id)
        usages = self.db.execute(
            select(SubscriptionUsage).where(SubscriptionUsage.user_id == user_id).order_by(SubscriptionUsage.created_at.desc())
        ).scalars().all()
        total_saved = sum(Decimal(str(item.amount_saved or 0)) for item in usages)
        return {
            "subscriptions": subscriptions,
            "usages": [self._serialize_usage(row) for row in usages[:50]],
            "totalEstimatedSavings": float(total_saved),
            "activeGeneral": next((item for item in subscriptions if item["subscriptionType"] == "GENERAL" and item["status"] == "ACTIVE"), None),
            "activeServices": [item for item in subscriptions if item["subscriptionType"] == "SERVICE" and item["status"] == "ACTIVE"],
        }

    def pause_subscription(self, user_id: str, subscription_id: str) -> dict[str, Any]:
        subscription = self._lock_user_subscription(user_id, subscription_id)
        if subscription.status != "ACTIVE":
            raise ValueError("Seuls les abonnements actifs peuvent être mis en pause.")
        subscription.status = "PAUSED"
        subscription.paused_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(subscription)
        return self._serialize_user_subscription(subscription)

    def resume_subscription(self, user_id: str, subscription_id: str) -> dict[str, Any]:
        subscription = self._lock_user_subscription(user_id, subscription_id)
        if subscription.status != "PAUSED":
            raise ValueError("Seuls les abonnements en pause peuvent être réactivés.")
        subscription.status = "ACTIVE"
        subscription.paused_at = None
        self.db.commit()
        self.db.refresh(subscription)
        return self._serialize_user_subscription(subscription)

    def cancel_subscription(self, user_id: str, subscription_id: str) -> dict[str, Any]:
        subscription = self._lock_user_subscription(user_id, subscription_id)
        if subscription.status in {"CANCELLED", "EXPIRED"}:
            raise ValueError("Cet abonnement est déjà arrêté.")
        subscription.status = "CANCELLED"
        subscription.cancelled_at = datetime.now(timezone.utc)
        subscription.auto_renew = False
        self.db.commit()
        self.db.refresh(subscription)
        return self._serialize_user_subscription(subscription)

    def preview_for_service(
        self,
        *,
        user_id: str,
        service_category: str,
        estimated_amount: Decimal | None = None,
        currency: str = "EUR",
    ) -> dict[str, Any]:
        self._reset_due_cycles(user_id)
        category = service_category.strip().upper()
        active_general = self._find_active_general_subscription(user_id)
        service_sub = self._find_active_service_subscription(user_id, category)
        remaining_quota = None
        if service_sub and service_sub.tasks_included_monthly is not None:
            remaining_quota = max(0, int(service_sub.tasks_included_monthly) - int(service_sub.tasks_used_this_month))
        return {
            "serviceCategory": category,
            "generalSubscriptionActive": bool(active_general),
            "generalPlanCode": active_general.plan_code if active_general else None,
            "serviceSubscriptionActive": bool(service_sub),
            "servicePlanCode": service_sub.plan_code if service_sub else None,
            "remainingQuota": remaining_quota,
            "quotaWillApply": bool(service_sub and remaining_quota and remaining_quota > 0),
            "estimatedAmount": float(estimated_amount) if estimated_amount is not None else None,
            "currency": currency.upper(),
        }

    def apply_task_subscription(self, user_id: str, task: Task) -> dict[str, Any] | None:
        self._reset_due_cycles(user_id)
        now = datetime.now(timezone.utc)
        service_category = (getattr(task, "service_category", None) or "TASK").upper()
        applied: dict[str, Any] | None = None

        service_sub = self._find_active_service_subscription(user_id, service_category)
        if service_sub and service_sub.tasks_included_monthly is not None:
            remaining = int(service_sub.tasks_included_monthly) - int(service_sub.tasks_used_this_month)
            if remaining > 0:
                service_sub.tasks_used_this_month += 1
                usage = SubscriptionUsage(
                    id=str(uuid.uuid4()),
                    subscription_id=service_sub.id,
                    user_id=user_id,
                    plan_code=service_sub.plan_code,
                    service_category=service_category,
                    task_id=task.id,
                    benefit_type="SERVICE_QUOTA",
                    units_used=1,
                    amount_saved=Decimal("0"),
                    currency=task.currency,
                    period_key=now.strftime("%Y-%m"),
                )
                self.db.add(usage)
                applied = {
                    "subscriptionId": service_sub.id,
                    "planCode": service_sub.plan_code,
                    "benefitType": "SERVICE_QUOTA",
                    "remainingQuotaAfterUse": max(0, int(service_sub.tasks_included_monthly) - int(service_sub.tasks_used_this_month)),
                }

        general_sub = self._find_active_general_subscription(user_id)
        if general_sub:
            self.db.add(
                SubscriptionUsage(
                    id=str(uuid.uuid4()),
                    subscription_id=general_sub.id,
                    user_id=user_id,
                    plan_code=general_sub.plan_code,
                    service_category=service_category,
                    task_id=task.id,
                    benefit_type="PRO_ACTIVE",
                    units_used=1,
                    amount_saved=Decimal("0"),
                    currency=task.currency,
                    period_key=now.strftime("%Y-%m"),
                )
            )
            if applied is None:
                applied = {
                    "subscriptionId": general_sub.id,
                    "planCode": general_sub.plan_code,
                    "benefitType": "PRO_ACTIVE",
                }
            else:
                applied["generalPlanCode"] = general_sub.plan_code

        return applied

    def list_all_user_subscriptions(
        self,
        status: str | None = None,
        country_code: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(UserSubscription).order_by(UserSubscription.created_at.desc())
        if status:
            stmt = stmt.where(UserSubscription.status == status.strip().upper())
        if country_code:
            stmt = stmt.where(UserSubscription.country_code == country_code.strip().upper())
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_user_subscription(row) for row in rows]

    def _get_active_plan(self, plan_code: str) -> SubscriptionPlan:
        plan = self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.code == plan_code.strip().upper(),
                SubscriptionPlan.is_active == True,  # noqa: E712
            )
        ).scalars().one_or_none()
        if plan is None:
            raise ValueError("Plan d'abonnement introuvable ou inactif.")
        return plan

    def _ensure_no_conflicting_active_subscription(self, user_id: str, plan: SubscriptionPlan) -> None:
        stmt = select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.status.in_(["ACTIVE", "PAUSED"]),
        )
        if plan.subscription_type == "GENERAL":
            stmt = stmt.where(UserSubscription.subscription_type == "GENERAL")
        else:
            stmt = stmt.where(
                UserSubscription.subscription_type == "SERVICE",
                UserSubscription.service_category == plan.service_category,
            )
        conflict = self.db.execute(stmt).scalars().one_or_none()
        if conflict is not None:
            raise ValueError("Un abonnement actif ou en pause existe déjà sur ce périmètre.")

    def _lock_user_subscription(self, user_id: str, subscription_id: str) -> UserSubscription:
        row = self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.id == subscription_id, UserSubscription.user_id == user_id)
            .with_for_update()
        ).scalars().one_or_none()
        if row is None:
            raise ValueError("Abonnement introuvable.")
        return row

    def _reset_due_cycles(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        changed = False
        rows = self.db.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "ACTIVE",
            )
        ).scalars().all()
        for row in rows:
            if row.next_reset_at and row.next_reset_at <= now:
                row.tasks_used_this_month = 0
                row.next_reset_at = row.next_reset_at + timedelta(days=30)
                row.renewal_date = row.next_reset_at
                changed = True
        if changed:
            self.db.commit()

    def _find_active_general_subscription(self, user_id: str) -> UserSubscription | None:
        return self.db.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "ACTIVE",
                UserSubscription.subscription_type == "GENERAL",
            ).order_by(UserSubscription.created_at.desc())
        ).scalars().first()

    def _find_active_service_subscription(self, user_id: str, service_category: str) -> UserSubscription | None:
        return self.db.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "ACTIVE",
                UserSubscription.subscription_type == "SERVICE",
                UserSubscription.service_category == service_category,
            ).order_by(UserSubscription.created_at.desc())
        ).scalars().first()

    @staticmethod
    def _serialize_plan(plan: SubscriptionPlan) -> dict[str, Any]:
        return {
            "id": plan.id,
            "code": plan.code,
            "name": plan.name,
            "description": plan.description,
            "subscriptionType": plan.subscription_type,
            "serviceCategory": plan.service_category,
            "billingCycle": plan.billing_cycle,
            "priceMonthly": float(plan.price_monthly),
            "currency": plan.currency,
            "tasksIncludedMonthly": plan.tasks_included_monthly,
            "overagePrice": float(plan.overage_price) if plan.overage_price is not None else None,
            "priorityEnabled": bool(plan.priority_enabled),
            "diasporaIncluded": bool(plan.diaspora_included),
            "supportPriority": bool(plan.support_priority),
            "isActive": bool(plan.is_active),
            "isPublic": bool(plan.is_public),
        }

    @staticmethod
    def _serialize_user_subscription(subscription: UserSubscription) -> dict[str, Any]:
        remaining_quota = None
        if subscription.tasks_included_monthly is not None:
            remaining_quota = max(0, int(subscription.tasks_included_monthly) - int(subscription.tasks_used_this_month))
        return {
            "id": subscription.id,
            "userId": subscription.user_id,
            "planId": subscription.plan_id,
            "planCode": subscription.plan_code,
            "subscriptionType": subscription.subscription_type,
            "serviceCategory": subscription.service_category,
            "status": subscription.status,
            "priceMonthly": float(subscription.price_monthly),
            "currency": subscription.currency,
            "tasksIncludedMonthly": subscription.tasks_included_monthly,
            "tasksUsedThisMonth": subscription.tasks_used_this_month,
            "remainingQuota": remaining_quota,
            "autoRenew": bool(subscription.auto_renew),
            "startedAt": subscription.started_at.isoformat() if subscription.started_at else None,
            "renewalDate": subscription.renewal_date.isoformat() if subscription.renewal_date else None,
            "nextResetAt": subscription.next_reset_at.isoformat() if subscription.next_reset_at else None,
            "pausedAt": subscription.paused_at.isoformat() if subscription.paused_at else None,
            "cancelledAt": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
            "countryCode": subscription.country_code,
            "source": subscription.source,
        }

    @staticmethod
    def _serialize_usage(usage: SubscriptionUsage) -> dict[str, Any]:
        return {
            "id": usage.id,
            "subscriptionId": usage.subscription_id,
            "userId": usage.user_id,
            "planCode": usage.plan_code,
            "serviceCategory": usage.service_category,
            "taskId": usage.task_id,
            "benefitType": usage.benefit_type,
            "unitsUsed": usage.units_used,
            "amountSaved": float(usage.amount_saved),
            "currency": usage.currency,
            "periodKey": usage.period_key,
            "createdAt": usage.created_at.isoformat() if usage.created_at else None,
        }
