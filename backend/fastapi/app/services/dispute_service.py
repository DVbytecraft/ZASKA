from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.observability import logger
from app.models.chat_message import ChatMessage
from app.models.dispute import DisputeEvent, DisputeRecord
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow
from app.services.wallet_service import WalletService


class DisputeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallet_service = WalletService(db)

    def open_task_dispute(self, *, task_id: str, actor_user_id: str, reason: str) -> dict[str, Any]:
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one_or_none()
        if task is None:
            raise ValueError("Tâche introuvable")
        if actor_user_id not in {task.created_by, task.assigned_to}:
            raise ValueError("Seuls le client ou le tasker peuvent ouvrir un litige sur cette tâche")
        if task.status not in {"ASSIGNED", "PENDING_VALIDATION"}:
            raise ValueError("Le litige doit être ouvert avant la validation finale de la tâche")

        existing = self.db.execute(
            select(DisputeRecord).where(
                DisputeRecord.task_id == task_id,
                DisputeRecord.status.in_(["open", "under_review", "escalated"]),
            )
        ).scalars().first()
        if existing is not None:
            raise ValueError("Un litige est déjà ouvert pour cette tâche")

        escrow = self.wallet_service.get_escrow_by_task_for_update(task_id)
        if escrow is None:
            raise ValueError("Aucun escrow actif n'est associé à cette tâche")
        self.wallet_service.freeze_escrow_for_audit(escrow.id, actor_user_id, commit=False)

        actor_role = "client" if actor_user_id == task.created_by else "tasker"
        counterparty_user_id = task.assigned_to if actor_role == "client" else task.created_by
        now = datetime.now(timezone.utc)
        dispute = DisputeRecord(
            id=str(uuid.uuid4()),
            user_id=actor_user_id,
            task_id=task.id,
            escrow_id=escrow.id,
            counterparty_user_id=counterparty_user_id,
            opened_by_role=actor_role,
            transaction_id=escrow.funding_tx_id,
            dispute_type="task_dispute",
            reason=reason.strip(),
            priority=self._priority_for(task, escrow),
            amount=escrow.amount,
            currency=escrow.currency,
            status="open",
            source_channel="task_contest",
            task_snapshot_json=json.dumps(self._task_snapshot(task)),
            chat_snapshot_json=json.dumps(self._chat_snapshot(task.id)),
            geo_snapshot_json=json.dumps(self._geo_snapshot(task)),
            photos_snapshot_json=json.dumps(self._photos_snapshot(task.id, task)),
            due_at=now + timedelta(hours=24),
            latest_action_at=now,
        )
        self.db.add(dispute)
        self.db.flush()
        self._add_event(
            dispute_id=dispute.id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            event_type="OPENED",
            message=reason.strip(),
            payload={
                "task_id": task.id,
                "escrow_id": escrow.id,
                "amount": str(escrow.amount),
                "currency": escrow.currency,
            },
        )
        self._notify_dispute_status(
            dispute,
            title="Litige ouvert",
            body="Un litige a été ouvert sur cette tâche. Les fonds sont maintenant gelés en audit.",
        )
        self.db.commit()
        self.db.refresh(dispute)
        return self.serialize_dispute(dispute)

    def list_disputes(
        self,
        *,
        viewer_user_id: str | None = None,
        admin_view: bool = False,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = select(DisputeRecord).order_by(desc(DisputeRecord.created_at)).limit(min(limit, 200))
        if not admin_view and viewer_user_id:
            stmt = stmt.where(
                (DisputeRecord.user_id == viewer_user_id) |
                (DisputeRecord.counterparty_user_id == viewer_user_id)
            )
        if status:
            stmt = stmt.where(DisputeRecord.status == status)
        if priority:
            stmt = stmt.where(DisputeRecord.priority == priority)
        rows = self.db.execute(stmt).scalars().all()
        return [self.serialize_dispute(row) for row in rows]

    def get_dispute_detail(self, dispute_id: str, viewer_user_id: str | None = None, admin_view: bool = False) -> dict[str, Any]:
        dispute = self.db.get(DisputeRecord, dispute_id)
        if dispute is None:
            raise ValueError("Litige introuvable")
        if not admin_view and viewer_user_id not in {dispute.user_id, dispute.counterparty_user_id}:
            raise ValueError("Accès non autorisé à ce litige")
        data = self.serialize_dispute(dispute)
        data["events"] = self._list_events(dispute.id)
        return data

    def assign_agent(self, dispute_id: str, agent_user_id: str, admin_user_id: str) -> dict[str, Any]:
        dispute = self._lock_dispute(dispute_id)
        dispute.assigned_agent_id = agent_user_id
        dispute.status = "under_review"
        dispute.latest_action_at = datetime.now(timezone.utc)
        self._add_event(
            dispute_id=dispute.id,
            actor_user_id=admin_user_id,
            actor_role="admin",
            event_type="ASSIGNED",
            message=f"Litige assigné à l'agent {agent_user_id}",
            payload={"assigned_agent_id": agent_user_id},
        )
        self._notify_dispute_status(
            dispute,
            title="Litige en cours de revue",
            body="Votre litige est maintenant pris en charge par un agent Zaska.",
        )
        self.db.commit()
        self.db.refresh(dispute)
        return self.serialize_dispute(dispute)

    def add_note(self, dispute_id: str, actor_user_id: str, actor_role: str, note: str) -> dict[str, Any]:
        dispute = self._lock_dispute(dispute_id)
        dispute.latest_action_at = datetime.now(timezone.utc)
        self._add_event(
            dispute_id=dispute.id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            event_type="NOTE_ADDED",
            message=note.strip(),
        )
        self.db.commit()
        return self.get_dispute_detail(dispute_id, admin_view=True)

    def escalate(self, dispute_id: str, actor_user_id: str, note: str | None = None, escalated_to_user_id: str | None = None) -> dict[str, Any]:
        dispute = self._lock_dispute(dispute_id)
        dispute.status = "escalated"
        dispute.escalated_to_user_id = escalated_to_user_id
        dispute.latest_action_at = datetime.now(timezone.utc)
        self._add_event(
            dispute_id=dispute.id,
            actor_user_id=actor_user_id,
            actor_role="admin",
            event_type="ESCALATED",
            message=note or "Escalade vers le management",
            payload={"escalated_to_user_id": escalated_to_user_id},
        )
        self._notify_dispute_status(
            dispute,
            title="Litige escaladé",
            body="Votre litige a été escaladé vers un niveau de gestion supérieur.",
        )
        self.db.commit()
        self.db.refresh(dispute)
        return self.serialize_dispute(dispute)

    def decide(
        self,
        *,
        dispute_id: str,
        admin_user_id: str,
        decision: str,
        admin_notes: str = "",
        tasker_percent: int | None = None,
    ) -> dict[str, Any]:
        dispute = self._lock_dispute(dispute_id)
        if dispute.status not in {"open", "under_review", "escalated"}:
            raise ValueError("Ce litige est déjà clôturé")
        if not dispute.escrow_id:
            raise ValueError("Ce litige n'est pas lié à un escrow exploitable")
        escrow = self.wallet_service.get_escrow(dispute.escrow_id)

        resolution_tx_id: str | None = None
        resolution_type = decision
        if decision == "release_tasker":
            settled = self.wallet_service.release_escrow(dispute.escrow_id, allow_frozen=True)
            resolution_tx_id = settled.settlement_tx_id
        elif decision == "refund_client":
            settled = self.wallet_service.refund_escrow(dispute.escrow_id, allow_frozen=True)
            resolution_tx_id = settled.settlement_tx_id
        elif decision == "partial_refund_client":
            if tasker_percent is None or not (0 <= int(tasker_percent) <= 100):
                raise ValueError("tasker_percent doit être fourni entre 0 et 100 pour un remboursement partiel")
            settled, _, _ = self.wallet_service.partial_release_escrow(
                dispute.escrow_id, int(tasker_percent), allow_frozen=True
            )
            resolution_tx_id = settled.settlement_tx_id
            resolution_type = f"partial_release_{int(tasker_percent)}"
        elif decision == "escalate":
            return self.escalate(dispute_id, admin_user_id, note=admin_notes)
        else:
            raise ValueError("Décision invalide")

        dispute.status = "resolved"
        dispute.resolution_type = resolution_type
        dispute.admin_notes = admin_notes or dispute.admin_notes
        dispute.resolution_tx_id = resolution_tx_id
        dispute.resolved_at = datetime.now(timezone.utc)
        dispute.latest_action_at = datetime.now(timezone.utc)
        self._add_event(
            dispute_id=dispute.id,
            actor_user_id=admin_user_id,
            actor_role="admin",
            event_type="DECISION",
            message=admin_notes or f"Décision: {resolution_type}",
            payload={"decision": decision, "tasker_percent": tasker_percent},
        )
        self._notify_dispute_status(
            dispute,
            title="Litige résolu",
            body="Votre litige a été traité par Zaska. Consultez le détail de la décision.",
        )
        self.db.commit()
        self.db.refresh(dispute)
        return self.serialize_dispute(dispute)

    def serialize_dispute(self, dispute: DisputeRecord) -> dict[str, Any]:
        return {
            "id": dispute.id,
            "userId": dispute.user_id,
            "taskId": dispute.task_id,
            "escrowId": dispute.escrow_id,
            "counterpartyUserId": dispute.counterparty_user_id,
            "openedByRole": dispute.opened_by_role,
            "assignedAgentId": dispute.assigned_agent_id,
            "escalatedToUserId": dispute.escalated_to_user_id,
            "transactionId": dispute.transaction_id,
            "payoutId": dispute.payout_id,
            "disputeType": dispute.dispute_type,
            "reason": dispute.reason,
            "priority": dispute.priority,
            "amount": float(dispute.amount) if dispute.amount is not None else None,
            "currency": dispute.currency,
            "status": dispute.status,
            "resolutionType": dispute.resolution_type,
            "sourceChannel": dispute.source_channel,
            "adminNotes": dispute.admin_notes,
            "resolutionTxId": dispute.resolution_tx_id,
            "taskSnapshot": self._decode_json(dispute.task_snapshot_json),
            "chatSnapshot": self._decode_json(dispute.chat_snapshot_json),
            "geoSnapshot": self._decode_json(dispute.geo_snapshot_json),
            "photosSnapshot": self._decode_json(dispute.photos_snapshot_json),
            "dueAt": dispute.due_at.isoformat() if dispute.due_at else None,
            "resolvedAt": dispute.resolved_at.isoformat() if dispute.resolved_at else None,
            "latestActionAt": dispute.latest_action_at.isoformat() if dispute.latest_action_at else None,
            "createdAt": dispute.created_at.isoformat() if dispute.created_at else None,
            "updatedAt": dispute.updated_at.isoformat() if dispute.updated_at else None,
        }

    def _lock_dispute(self, dispute_id: str) -> DisputeRecord:
        dispute = self.db.execute(
            select(DisputeRecord).where(DisputeRecord.id == dispute_id).with_for_update()
        ).scalars().one_or_none()
        if dispute is None:
            raise ValueError("Litige introuvable")
        return dispute

    def _add_event(
        self,
        *,
        dispute_id: str,
        actor_user_id: str | None,
        actor_role: str | None,
        event_type: str,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            DisputeEvent(
                id=str(uuid.uuid4()),
                dispute_id=dispute_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                event_type=event_type,
                message=message,
                payload_json=json.dumps(payload) if payload else None,
            )
        )

    def _list_events(self, dispute_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(DisputeEvent).where(DisputeEvent.dispute_id == dispute_id).order_by(DisputeEvent.created_at.asc())
        ).scalars().all()
        return [
            {
                "id": row.id,
                "actorUserId": row.actor_user_id,
                "actorRole": row.actor_role,
                "eventType": row.event_type,
                "message": row.message,
                "payload": self._decode_json(row.payload_json),
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    def _notify_dispute_status(self, dispute: DisputeRecord, *, title: str, body: str) -> None:
        recipients = {dispute.user_id, dispute.counterparty_user_id}
        for user_id in recipients:
            if not user_id:
                continue
            self.db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type="warning" if dispute.status != "resolved" else "info",
                title=title,
                body=body,
                task_id=dispute.task_id,
            ))

    def _priority_for(self, task: Task, escrow: Escrow) -> str:
        amount = float(escrow.amount or 0)
        if amount >= 500:
            return "urgent"
        if task.status == "PENDING_VALIDATION":
            return "high"
        if amount >= 100:
            return "high"
        return "medium"

    def _task_snapshot(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "price": float(task.price),
            "currency": task.currency,
            "status": task.status,
            "completionPercent": task.completion_percent,
            "createdBy": task.created_by,
            "assignedTo": task.assigned_to,
            "serviceCategory": getattr(task, "service_category", None),
            "isUrgent": bool(getattr(task, "is_urgent", False)),
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "proofPhotoUrl": getattr(task, "proof_photo_url", None),
        }

    def _chat_snapshot(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(ChatMessage).where(ChatMessage.task_id == task_id).order_by(ChatMessage.created_at.asc())
        ).scalars().all()
        return [
            {
                "id": row.id,
                "senderId": row.sender_id,
                "message": row.message,
                "mediaUrl": row.media_url,
                "mediaType": row.media_type,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    def _geo_snapshot(self, task: Task) -> dict[str, Any]:
        return {
            "latitude": task.latitude,
            "longitude": task.longitude,
            "address": task.address,
            "city": task.city,
            "country": task.country,
            "stops": task.stops,
        }

    def _photos_snapshot(self, task_id: str, task: Task) -> dict[str, Any]:
        chat_media = self.db.execute(
            select(ChatMessage).where(
                ChatMessage.task_id == task_id,
                ChatMessage.media_url.is_not(None),
            ).order_by(ChatMessage.created_at.asc())
        ).scalars().all()
        return {
            "proofPhotoUrl": getattr(task, "proof_photo_url", None),
            "chatMedia": [
                {
                    "messageId": row.id,
                    "mediaUrl": row.media_url,
                    "mediaType": row.media_type,
                    "senderId": row.sender_id,
                }
                for row in chat_media
            ],
        }

    @staticmethod
    def _decode_json(raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception as exc:
            logger.error("dispute:json_decode_failed error={}", exc)
            return None
