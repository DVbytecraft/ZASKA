from __future__ import annotations

import json
import secrets
import string
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.observability import logger
from app.models.notification import Notification
from app.models.referral import ReferralEvent, ReferralProgram, ReferralReward
from app.models.task import Task
from app.models.user import User
from app.services.wallet_service import WalletService

CLIENT_REFERRAL = "CLIENT"
TASKER_REFERRAL = "TASKER"
REWARD_WALLET = "WALLET_CREDIT"
REWARD_PLATFORM = "PLATFORM_CREDIT"

_DEFAULT_REWARD_MATRIX = {
    "EUR": {"client": Decimal("5.00"), "tasker": Decimal("10.00")},
    "USD": {"client": Decimal("5.00"), "tasker": Decimal("10.00")},
    "GBP": {"client": Decimal("5.00"), "tasker": Decimal("10.00")},
    "CAD": {"client": Decimal("7.00"), "tasker": Decimal("12.00")},
    "XOF": {"client": Decimal("3000"), "tasker": Decimal("5000")},
    "XAF": {"client": Decimal("3000"), "tasker": Decimal("5000")},
    "GHS": {"client": Decimal("35"), "tasker": Decimal("70")},
    "NGN": {"client": Decimal("4000"), "tasker": Decimal("8000")},
}


class ReferralService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_catalog(self) -> None:
        from app.models.location_config import Country

        countries = self.db.execute(select(Country)).scalars().all()
        changed = False
        changed = self._upsert_program(
            code="CLIENT_REFERRAL_DEFAULT",
            referral_type=CLIENT_REFERRAL,
            country_code=None,
            reward_kind=REWARD_PLATFORM,
            reward_amount=_DEFAULT_REWARD_MATRIX["EUR"]["client"],
            reward_currency="EUR",
            qualification_threshold=1,
            description="Crédit de parrainage client par défaut.",
        ) or changed
        changed = self._upsert_program(
            code="TASKER_REFERRAL_DEFAULT",
            referral_type=TASKER_REFERRAL,
            country_code=None,
            reward_kind=REWARD_WALLET,
            reward_amount=_DEFAULT_REWARD_MATRIX["EUR"]["tasker"],
            reward_currency="EUR",
            qualification_threshold=10,
            description="Prime de parrainage tasker par défaut.",
        ) or changed
        for country in countries:
            currency = (country.currency_code or "EUR").upper()
            matrix = _DEFAULT_REWARD_MATRIX.get(currency, _DEFAULT_REWARD_MATRIX["EUR"])
            changed = self._upsert_program(
                code=f"CLIENT_REFERRAL_{country.iso_code}",
                referral_type=CLIENT_REFERRAL,
                country_code=country.iso_code,
                reward_kind=REWARD_PLATFORM,
                reward_amount=matrix["client"],
                reward_currency=currency,
                qualification_threshold=1,
                description=f"Crédit parrainage client pour {country.iso_code}.",
            ) or changed
            changed = self._upsert_program(
                code=f"TASKER_REFERRAL_{country.iso_code}",
                referral_type=TASKER_REFERRAL,
                country_code=country.iso_code,
                reward_kind=REWARD_WALLET,
                reward_amount=matrix["tasker"],
                reward_currency=currency,
                qualification_threshold=10,
                description=f"Prime parrainage tasker pour {country.iso_code}.",
            ) or changed
        if changed:
            self.db.commit()

    def ensure_user_referral_code(self, user: User, commit: bool = True) -> str:
        if user.referral_code:
            return user.referral_code
        code = self._generate_unique_code(user)
        user.referral_code = code
        if commit:
            self.db.commit()
        return code

    def attach_referral_to_registration(
        self,
        *,
        user: User,
        referral_code: str | None,
    ) -> None:
        self.ensure_user_referral_code(user, commit=False)
        if not referral_code:
            return
        code = referral_code.strip().upper()
        referrer = self.db.execute(
            select(User).where(User.referral_code == code, User.is_verified == True)  # noqa: E712
        ).scalars().one_or_none()
        if referrer is None:
            raise ValueError("Code de parrainage invalide.")
        if referrer.id == user.id:
            raise ValueError("Vous ne pouvez pas utiliser votre propre code de parrainage.")
        user.referred_by_user_id = referrer.id
        program = self._resolve_program(
            referral_type=TASKER_REFERRAL if user.role == "tasker" else CLIENT_REFERRAL,
            country_code=user.country_code,
        )
        event = ReferralEvent(
            id=str(uuid.uuid4()),
            referral_type=program.referral_type,
            referral_code=code,
            referrer_user_id=referrer.id,
            referred_user_id=user.id,
            program_id=program.id,
            status="PENDING",
            qualification_threshold=program.qualification_threshold,
            progress_count=0,
            reward_kind=program.reward_kind,
            reward_amount=program.reward_amount,
            reward_currency=program.reward_currency,
            country_code=user.country_code,
            metadata_json=json.dumps({"source": "registration"}),
        )
        self.db.add(event)

    def process_client_first_order(self, referred_user_id: str, task_id: str) -> None:
        event = self._get_pending_event(referred_user_id, CLIENT_REFERRAL)
        if event is None:
            return
        total_orders = self.db.execute(
            select(func.count(Task.id)).where(Task.created_by == referred_user_id)
        ).scalar() or 0
        event.progress_count = int(total_orders)
        event.trigger_task_id = task_id
        if total_orders >= event.qualification_threshold:
            self._reward_event(event, trigger_task_id=task_id)
        self.db.commit()

    def process_tasker_progress(self, referred_user_id: str, task_id: str) -> None:
        event = self._get_pending_event(referred_user_id, TASKER_REFERRAL)
        if event is None:
            return
        completed = self.db.execute(
            select(func.count(Task.id)).where(
                Task.assigned_to == referred_user_id,
                Task.status == "COMPLETED",
            )
        ).scalar() or 0
        event.progress_count = int(completed)
        event.trigger_task_id = task_id
        if completed >= event.qualification_threshold:
            self._reward_event(event, trigger_task_id=task_id)
        self.db.commit()

    def get_user_referral_dashboard(self, user_id: str) -> dict[str, Any]:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")
        code = self.ensure_user_referral_code(user)
        events = self.db.execute(
            select(ReferralEvent).where(
                (ReferralEvent.referrer_user_id == user_id) | (ReferralEvent.referred_user_id == user_id)
            ).order_by(ReferralEvent.created_at.desc())
        ).scalars().all()
        rewards = self.db.execute(
            select(ReferralReward).where(ReferralReward.beneficiary_user_id == user_id).order_by(ReferralReward.created_at.desc())
        ).scalars().all()
        return {
            "referralCode": code,
            "referredByUserId": user.referred_by_user_id,
            "events": [self._serialize_event(item) for item in events],
            "rewards": [self._serialize_reward(item) for item in rewards],
        }

    def list_programs(self) -> list[dict[str, Any]]:
        rows = self.db.execute(select(ReferralProgram).order_by(ReferralProgram.referral_type.asc(), ReferralProgram.country_code.asc())).scalars().all()
        return [self._serialize_program(item) for item in rows]

    def update_program(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        program = self.db.get(ReferralProgram, program_id)
        if program is None:
            raise ValueError("Programme de parrainage introuvable.")
        for field in ("reward_kind", "qualification_threshold", "description", "is_active"):
            if field in payload and payload[field] is not None:
                setattr(program, field, payload[field])
        if "reward_amount" in payload and payload["reward_amount"] is not None:
            program.reward_amount = Decimal(str(payload["reward_amount"]))
        if "reward_currency" in payload and payload["reward_currency"]:
            program.reward_currency = str(payload["reward_currency"]).strip().upper()
        self.db.commit()
        self.db.refresh(program)
        return self._serialize_program(program)

    def list_events(self, status: str | None = None, referral_type: str | None = None) -> list[dict[str, Any]]:
        stmt = select(ReferralEvent).order_by(ReferralEvent.created_at.desc())
        if status:
            stmt = stmt.where(ReferralEvent.status == status.strip().upper())
        if referral_type:
            stmt = stmt.where(ReferralEvent.referral_type == referral_type.strip().upper())
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_event(item) for item in rows]

    def list_rewards(self, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(ReferralReward).order_by(ReferralReward.created_at.desc())
        if status:
            stmt = stmt.where(ReferralReward.status == status.strip().upper())
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_reward(item) for item in rows]

    def _reward_event(self, event: ReferralEvent, trigger_task_id: str | None) -> None:
        if event.status == "REWARDED":
            return
        event.status = "QUALIFIED"
        event.qualified_at = datetime.now(timezone.utc)
        reward = ReferralReward(
            id=str(uuid.uuid4()),
            referral_event_id=event.id,
            beneficiary_user_id=event.referrer_user_id,
            reward_kind=event.reward_kind,
            amount_total=event.reward_amount,
            amount_remaining=event.reward_amount,
            currency=event.reward_currency,
            status="AVAILABLE",
            applied_task_id=trigger_task_id,
            available_at=datetime.now(timezone.utc),
        )
        self.db.add(reward)
        if event.reward_kind == REWARD_WALLET:
            tx = WalletService(self.db).credit_wallet(
                user_id=event.referrer_user_id,
                currency=event.reward_currency,
                amount=event.reward_amount,
                reference=f"referral_reward:{event.id}",
                provider="internal",
                metadata={
                    "type": "referral_reward",
                    "referral_event_id": event.id,
                    "referred_user_id": event.referred_user_id,
                    "trigger_task_id": trigger_task_id,
                },
            )
            reward.wallet_transaction_id = tx.id
            reward.amount_remaining = Decimal("0")
            reward.status = "APPLIED"
        event.status = "REWARDED"
        event.rewarded_at = datetime.now(timezone.utc)
        self._notify_reward(event)

    def _notify_reward(self, event: ReferralEvent) -> None:
        self.db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=event.referrer_user_id,
            type="success",
            title="Prime de parrainage débloquée",
            body=(
                f"Votre parrainage a été validé. Récompense : {event.reward_amount} {event.reward_currency} "
                f"({event.reward_kind})."
            ),
        ))

    def _get_pending_event(self, referred_user_id: str, referral_type: str) -> ReferralEvent | None:
        return self.db.execute(
            select(ReferralEvent).where(
                ReferralEvent.referred_user_id == referred_user_id,
                ReferralEvent.referral_type == referral_type,
                ReferralEvent.status.in_(["PENDING", "QUALIFIED"]),
            ).order_by(ReferralEvent.created_at.desc())
        ).scalars().first()

    def _resolve_program(self, referral_type: str, country_code: str | None) -> ReferralProgram:
        cc = (country_code or "").upper() or None
        if cc:
            country_program = self.db.execute(
                select(ReferralProgram).where(
                    ReferralProgram.referral_type == referral_type,
                    ReferralProgram.country_code == cc,
                    ReferralProgram.is_active == True,  # noqa: E712
                )
            ).scalars().one_or_none()
            if country_program is not None:
                return country_program
        program = self.db.execute(
            select(ReferralProgram).where(
                ReferralProgram.referral_type == referral_type,
                ReferralProgram.country_code.is_(None),
                ReferralProgram.is_active == True,  # noqa: E712
            )
        ).scalars().one_or_none()
        if program is None:
            raise ValueError("Aucun programme de parrainage actif n'est configuré.")
        return program

    def _upsert_program(
        self,
        *,
        code: str,
        referral_type: str,
        country_code: str | None,
        reward_kind: str,
        reward_amount: Decimal,
        reward_currency: str,
        qualification_threshold: int,
        description: str,
    ) -> bool:
        existing = self.db.execute(
            select(ReferralProgram).where(ReferralProgram.code == code)
        ).scalars().one_or_none()
        if existing is None:
            self.db.add(ReferralProgram(
                id=str(uuid.uuid4()),
                code=code,
                referral_type=referral_type,
                country_code=country_code,
                reward_kind=reward_kind,
                reward_amount=reward_amount,
                reward_currency=reward_currency,
                qualification_threshold=qualification_threshold,
                description=description,
                is_active=True,
            ))
            return True
        changed = False
        for field, value in {
            "referral_type": referral_type,
            "country_code": country_code,
            "reward_kind": reward_kind,
            "reward_amount": reward_amount,
            "reward_currency": reward_currency,
            "qualification_threshold": qualification_threshold,
            "description": description,
        }.items():
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True
        return changed

    def _generate_unique_code(self, user: User) -> str:
        prefix = ((user.first_name or user.full_name or "ZSK")[:3]).upper()
        prefix = "".join(ch for ch in prefix if ch in string.ascii_uppercase) or "ZSK"
        while True:
            suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
            code = f"{prefix}{suffix}"
            exists = self.db.execute(select(User.id).where(User.referral_code == code)).scalars().first()
            if not exists:
                return code

    @staticmethod
    def _serialize_program(program: ReferralProgram) -> dict[str, Any]:
        return {
            "id": program.id,
            "code": program.code,
            "referralType": program.referral_type,
            "countryCode": program.country_code,
            "rewardKind": program.reward_kind,
            "rewardAmount": float(program.reward_amount),
            "rewardCurrency": program.reward_currency,
            "qualificationThreshold": program.qualification_threshold,
            "description": program.description,
            "isActive": bool(program.is_active),
        }

    @staticmethod
    def _serialize_event(event: ReferralEvent) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if event.metadata_json:
            try:
                metadata = json.loads(event.metadata_json)
            except Exception:
                metadata = {}
        return {
            "id": event.id,
            "referralType": event.referral_type,
            "referralCode": event.referral_code,
            "referrerUserId": event.referrer_user_id,
            "referredUserId": event.referred_user_id,
            "programId": event.program_id,
            "status": event.status,
            "qualificationThreshold": event.qualification_threshold,
            "progressCount": event.progress_count,
            "triggerTaskId": event.trigger_task_id,
            "rewardKind": event.reward_kind,
            "rewardAmount": float(event.reward_amount),
            "rewardCurrency": event.reward_currency,
            "countryCode": event.country_code,
            "qualifiedAt": event.qualified_at.isoformat() if event.qualified_at else None,
            "rewardedAt": event.rewarded_at.isoformat() if event.rewarded_at else None,
            "metadata": metadata,
            "createdAt": event.created_at.isoformat() if event.created_at else None,
        }

    @staticmethod
    def _serialize_reward(reward: ReferralReward) -> dict[str, Any]:
        return {
            "id": reward.id,
            "referralEventId": reward.referral_event_id,
            "beneficiaryUserId": reward.beneficiary_user_id,
            "rewardKind": reward.reward_kind,
            "amountTotal": float(reward.amount_total),
            "amountRemaining": float(reward.amount_remaining),
            "currency": reward.currency,
            "status": reward.status,
            "walletTransactionId": reward.wallet_transaction_id,
            "appliedTaskId": reward.applied_task_id,
            "availableAt": reward.available_at.isoformat() if reward.available_at else None,
            "appliedAt": reward.applied_at.isoformat() if reward.applied_at else None,
            "createdAt": reward.created_at.isoformat() if reward.created_at else None,
        }
