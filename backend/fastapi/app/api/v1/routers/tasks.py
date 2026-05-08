from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user_id,
    get_db,
    get_task_service,
    get_wallet_service,
    require_verified_user,
)
from app.core.config import settings
from app.core.observability import logger
from app.core.responses import success_response
from app.models.task import Task
from app.models.task_completion_code import TaskCompletionCode
from app.models.user import User
from app.schemas.task import (
    MatchQueryPayload,
    TaskAcceptPayload,
    TaskApplyPayload,
    TaskCreatePayload,
    TaskStatusPayload,
    TaskUpdatePayload,
)
from app.services.email_service import EmailService
from app.services.task_service import TaskService
from app.services.wallet_service import EscrowError, WalletService

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ─── Serializers ─────────────────────────────────────────────────────────────

def _serialize_task(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "price": float(task.price),
        "currency": task.currency,
        "latitude": task.latitude,
        "longitude": task.longitude,
        "address": task.address,
        "status": task.status,
        "createdBy": task.created_by,
        "assignedTo": task.assigned_to,
        "completionPercent": task.completion_percent,
        "negotiationStatus": task.negotiation_status,
        "negotiatedPrice": float(task.negotiated_price) if task.negotiated_price else None,
        "createdAt": task.created_at.isoformat() if task.created_at else None,
        "mode": task.mode,
    }


def _serialize_application(app, user: User) -> dict:
    display_name = user.email.split("@")[0] if user.email else user.id[:8]
    return {
        "id": app.id,
        "taskId": app.task_id,
        "taskerId": app.tasker_id,
        "taskerName": display_name,
        "taskerEmail": user.email,
        "proposedPrice": float(app.proposed_price) if app.proposed_price is not None else None,
        "currency": app.currency,
        "status": app.status,
        "message": app.message,
        "createdAt": app.created_at.isoformat(),
    }


def _get_task_or_404(task_id: str, service: TaskService) -> Task:
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return task


def _hash_code(code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def _send_completion_code_email(email: str, code: str, role: str, task_title: str) -> None:
    role_label = "client" if role == "client" else "exécutant"
    EmailService().send_email(
        to_email=email,
        subject=f"ZASKA — Code de finalisation de tâche",
        html_content=(
            f"<p>Bonjour,</p>"
            f"<p>La tâche <strong>{task_title}</strong> est marquée comme terminée.</p>"
            f"<p>En tant que <strong>{role_label}</strong>, votre code de validation est :</p>"
            f"<h2 style='letter-spacing:8px'>{code}</h2>"
            f"<p>Entrez ce code dans l'application pour confirmer la finalisation.<br>"
            f"Ce code expire dans 48 heures.</p>"
            f"<p>Si vous n'avez pas terminé ce travail, ne validez pas ce code.</p>"
        ),
        text_content=f"Code de finalisation ZASKA : {code}",
    )


# ─── CRUD ────────────────────────────────────────────────────────────────────

@router.post("")
def create_task(
    payload: TaskCreatePayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(require_verified_user),
):
    try:
        data = payload.model_dump()
        data["created_by"] = user_id
        task = service.create_task(data)
        return success_response(_serialize_task(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de créer la tâche") from exc


@router.get("")
def list_tasks(
    status: str | None = None,
    mine: bool = False,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        tasks = service.list_tasks(status=status, created_by=user_id if mine else None)
        return success_response([_serialize_task(t) for t in tasks])
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de charger les tâches") from exc


@router.get("/{task_id}")
def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    _ = user_id
    try:
        task = _get_task_or_404(task_id, service)
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de charger la tâche") from exc


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    payload: TaskUpdatePayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé à modifier cette tâche")
        changes = payload.model_dump(exclude_none=True)
        task = service.update_task(task_id=task_id, changes=changes)
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de modifier la tâche") from exc


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé à supprimer cette tâche")
        service.delete_task(task_id)
        return success_response({"deleted": True})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de supprimer la tâche") from exc


# ─── Choose Mode — Applications ──────────────────────────────────────────────

@router.post("/{task_id}/apply")
def apply_task(
    task_id: str,
    payload: TaskApplyPayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(require_verified_user),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by == user_id:
            raise HTTPException(status_code=403, detail="Vous ne pouvez pas postuler à votre propre tâche")
        if task.status != "OPEN":
            raise HTTPException(status_code=409, detail="Cette tâche n'est plus disponible")

        currency = (payload.currency or task.currency or "USD").upper()
        application = service.apply_task(
            task_id=task_id,
            tasker_id=user_id,
            proposed_price=payload.proposed_price,
            currency=currency,
            message=payload.message,
        )
        return success_response({
            "id": application.id,
            "taskId": application.task_id,
            "taskerId": application.tasker_id,
            "proposedPrice": float(application.proposed_price) if application.proposed_price else None,
            "currency": application.currency,
            "status": application.status,
            "message": application.message,
            "createdAt": application.created_at.isoformat(),
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de postuler à la tâche") from exc


@router.get("/{task_id}/applications")
def list_applications(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Seul le créateur de la tâche peut voir les candidatures")
        rows = service.list_applications(task_id)
        return success_response([_serialize_application(app, user) for app, user in rows])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de charger les candidatures") from exc


# ─── Accept ──────────────────────────────────────────────────────────────────

@router.post("/{task_id}/accept")
def accept_task(
    task_id: str,
    payload: TaskAcceptPayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.status != "OPEN":
            raise HTTPException(status_code=409, detail="Cette tâche n'est plus ouverte")

        if task.created_by == user_id:
            if not payload.tasker_id:
                raise HTTPException(status_code=400, detail="tasker_id requis pour accepter un exécutant")
            tasker_id = payload.tasker_id
        else:
            tasker_id = user_id

        task = service.accept_task(task_id=task_id, tasker_id=tasker_id)
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'accepter la tâche") from exc


# ─── Status ───────────────────────────────────────────────────────────────────

@router.patch("/{task_id}/status")
def update_status(
    task_id: str,
    payload: TaskStatusPayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id and task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé à modifier le statut de cette tâche")
        task = service.update_status(task_id=task_id, status=payload.status)
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de modifier le statut") from exc


# ─── Price Negotiation ────────────────────────────────────────────────────────

class NegotiatePayload(BaseModel):
    proposed_price: Decimal = Field(gt=0)


@router.post("/{task_id}/negotiate")
def negotiate_price(
    task_id: str,
    payload: NegotiatePayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    """Exécutant soumet un contre-prix. Le client reçoit la demande à valider."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.assigned_to == user_id or task.created_by == user_id:
            pass
        else:
            raise HTTPException(status_code=403, detail="Non autorisé à négocier cette tâche")
        if task.created_by == user_id:
            raise HTTPException(status_code=400, detail="Le créateur ne peut pas négocier son propre prix")
        if task.status not in ("OPEN",):
            raise HTTPException(status_code=409, detail="La négociation n'est possible que sur une tâche OPEN")

        task = service.propose_price(task_id=task_id, proposer_id=user_id, proposed_price=payload.proposed_price)
        return success_response({
            **_serialize_task(task),
            "message": "Demande de modification de prix envoyée au client. En attente de validation.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de soumettre la négociation") from exc


class NegotiationResponsePayload(BaseModel):
    accept: bool


@router.post("/{task_id}/negotiate/respond")
def respond_to_negotiation(
    task_id: str,
    payload: NegotiationResponsePayload,
    service: TaskService = Depends(get_task_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Client valide ou refuse la demande de modification de prix."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Seul le créateur de la tâche peut répondre à la négociation")
        if task.negotiation_status != "pending":
            raise HTTPException(status_code=409, detail="Aucune négociation en attente")

        if payload.accept:
            task = service.accept_negotiation(task_id)
        else:
            task = service.reject_negotiation(task_id)

        # Notify negotiator via email if we have their email
        negotiator = db.get(User, task.negotiated_by) if task.negotiated_by else None
        if negotiator and negotiator.email and not payload.accept:
            EmailService().send_email(
                to_email=negotiator.email,
                subject="ZASKA — Modification de prix refusée",
                html_content=(
                    f"<p>Le client a refusé votre demande de modification de prix pour la tâche "
                    f"<strong>{task.title}</strong>.</p>"
                    f"<p>Vous pouvez continuer avec le prix initial ({float(task.price)} {task.currency}) "
                    f"ou abandonner la tâche dans l'application.</p>"
                ),
                text_content=f"Modification de prix refusée pour la tâche {task.title}.",
            )

        msg = "Prix accepté. La messagerie est maintenant ouverte." if payload.accept else "Prix refusé. L'exécutant sera notifié."
        return success_response({**_serialize_task(task), "message": msg})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de répondre à la négociation") from exc


class AbandonNegotiationPayload(BaseModel):
    abandon: bool = True


@router.post("/{task_id}/negotiate/abandon")
def abandon_negotiation(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    """Exécutant abandonne après refus du prix → tâche republié (OPEN)."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.negotiated_by != user_id:
            raise HTTPException(status_code=403, detail="Seul l'exécutant ayant proposé le prix peut abandonner")
        if task.negotiation_status != "rejected":
            raise HTTPException(status_code=409, detail="L'abandon n'est possible qu'après un refus de prix")

        task = service.abandon_and_republish(task_id)
        return success_response({
            **_serialize_task(task),
            "message": "Tâche abandonnée et republiée. Elle est de nouveau visible pour tous.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'abandonner la tâche") from exc


# ─── Task Completion Codes ────────────────────────────────────────────────────

class CompleteTaskPayload(BaseModel):
    completion_percent: int = Field(default=100, ge=1, le=100)


@router.post("/{task_id}/complete")
def mark_task_complete(
    task_id: str,
    payload: CompleteTaskPayload,
    service: TaskService = Depends(get_task_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Exécutant déclare la tâche terminée (ou partiellement).
    Génère 2 codes email — un pour chaque partie — pour valider la finalisation.
    """
    try:
        task = _get_task_or_404(task_id, service)
        if task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Seul l'exécutant assigné peut déclarer la tâche terminée")
        if task.status not in ("ASSIGNED",):
            raise HTTPException(status_code=409, detail="La tâche doit être ASSIGNED pour être déclarée terminée")

        # Update completion_percent
        service.set_completion_percent(task_id, payload.completion_percent)

        # Delete any previous unused codes for this task
        db.query(TaskCompletionCode).filter(
            TaskCompletionCode.task_id == task_id,
            TaskCompletionCode.is_used == False,
        ).delete()
        db.commit()

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=48)

        # Generate code for client
        client = db.get(User, task.created_by)
        client_code = secrets.token_urlsafe(4).upper()[:6]
        db.add(TaskCompletionCode(
            task_id=task_id,
            user_id=task.created_by,
            role="client",
            code_hash=_hash_code(client_code),
            is_used=False,
            expires_at=expires_at,
        ))

        # Generate code for executor
        executor = db.get(User, user_id)
        executor_code = secrets.token_urlsafe(4).upper()[:6]
        db.add(TaskCompletionCode(
            task_id=task_id,
            user_id=user_id,
            role="executor",
            code_hash=_hash_code(executor_code),
            is_used=False,
            expires_at=expires_at,
        ))
        db.commit()

        # Send emails
        if client and client.email:
            _send_completion_code_email(client.email, client_code, "client", task.title)
        if executor and executor.email:
            _send_completion_code_email(executor.email, executor_code, "executor", task.title)

        logger.info("task:completion_codes_generated task_id={} completion={}%", task_id, payload.completion_percent)
        return success_response({
            "task_id": task_id,
            "completion_percent": payload.completion_percent,
            "message": "Codes de finalisation envoyés par email aux deux parties. Entrez votre code pour valider.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task:complete_error task_id={} error={}", task_id, exc)
        raise HTTPException(status_code=500, detail="Impossible de marquer la tâche terminée") from exc


class SubmitCodePayload(BaseModel):
    code: str = Field(min_length=4, max_length=12)


@router.post("/{task_id}/finalize")
def submit_completion_code(
    task_id: str,
    payload: SubmitCodePayload,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Soumettre son code de finalisation. Quand les 2 codes sont validés,
    le paiement passe en hold 24h (contestation possible), puis libéré automatiquement.
    """
    try:
        task = _get_task_or_404(task_id, service)
        if user_id not in {task.created_by, task.assigned_to}:
            raise HTTPException(status_code=403, detail="Non autorisé pour cette tâche")

        now = datetime.now(timezone.utc)

        # Find this user's code
        my_code_row = (
            db.query(TaskCompletionCode)
            .filter(
                TaskCompletionCode.task_id == task_id,
                TaskCompletionCode.user_id == user_id,
                TaskCompletionCode.is_used == False,
            )
            .one_or_none()
        )
        if my_code_row is None:
            raise HTTPException(status_code=404, detail="Aucun code de finalisation en attente pour vous")
        if my_code_row.expires_at.replace(tzinfo=timezone.utc) < now:
            raise HTTPException(status_code=410, detail="Votre code a expiré. L'exécutant doit redéclarer la tâche terminée.")

        submitted_hash = _hash_code(payload.code.strip().upper())
        if not hmac.compare_digest(submitted_hash, my_code_row.code_hash):
            raise HTTPException(status_code=400, detail="Code incorrect")

        my_code_row.is_used = True
        db.commit()

        # Check if both codes are now validated
        pending_codes = (
            db.query(TaskCompletionCode)
            .filter(
                TaskCompletionCode.task_id == task_id,
                TaskCompletionCode.is_used == False,
            )
            .count()
        )

        if pending_codes > 0:
            return success_response({
                "task_id": task_id,
                "code_validated": True,
                "both_validated": False,
                "message": "Votre code est validé. En attente de la validation de l'autre partie.",
            })

        # Both codes validated — trigger payment flow
        task_obj = service.get_task(task_id)
        completion_percent = task_obj.completion_percent if task_obj else 100

        escrow = wallet_svc.get_escrow_by_task(task_id)
        if escrow is None or escrow.status not in {"funded", "hold"}:
            # No escrow — just mark task completed
            service.update_status(task_id, "COMPLETED")
            return success_response({
                "task_id": task_id,
                "code_validated": True,
                "both_validated": True,
                "message": "Les deux codes sont validés. Tâche finalisée.",
            })

        if completion_percent < 100:
            # Partial work: executor 10%, client refund 90%
            task_price = task_obj.price if task_obj else escrow.amount
            esc, exec_amount, client_refund = wallet_svc.partial_release_escrow(
                escrow_id=escrow.id,
                task_price=task_price,
            )
            service.update_status(task_id, "COMPLETED")
            return success_response({
                "task_id": task_id,
                "code_validated": True,
                "both_validated": True,
                "completion_percent": completion_percent,
                "executor_paid": str(exec_amount),
                "client_refunded": str(client_refund),
                "currency": escrow.currency,
                "message": f"Travail partiel validé ({completion_percent}%). Paiement distribué.",
            })
        else:
            # Full work: hold 24h before releasing
            wallet_svc.hold_escrow_24h(escrow.id)
            service.update_status(task_id, "COMPLETED")
            return success_response({
                "task_id": task_id,
                "code_validated": True,
                "both_validated": True,
                "completion_percent": 100,
                "message": "Tâche validée. Le paiement sera libéré dans 24h si aucune contestation.",
                "payout_available_in_hours": 24,
            })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task:finalize_error task_id={} error={}", task_id, exc)
        raise HTTPException(status_code=500, detail="Impossible de finaliser la tâche") from exc


# ─── Contest & Release ────────────────────────────────────────────────────────

class ContestPayload(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


@router.post("/{task_id}/contest")
def contest_task(
    task_id: str,
    payload: ContestPayload,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Client conteste le travail dans la fenêtre de 24h. Le paiement est gelé."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Seul le client peut contester une tâche")

        escrow = wallet_svc.get_escrow_by_task(task_id)
        if escrow is None:
            raise HTTPException(status_code=404, detail="Aucun escrow associé à cette tâche")

        try:
            escrow = wallet_svc.contest_escrow(escrow.id, user_id)
        except EscrowError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        # Open a dispute record
        wallet_svc.open_dispute(
            user_id=user_id,
            reason=payload.reason,
            dispute_type="dispute",
            transaction_id=escrow.funding_tx_id,
        )

        return success_response({
            "task_id": task_id,
            "escrow_status": escrow.status,
            "message": "Contestation enregistrée. Le paiement est gelé en attendant la résolution.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de contester la tâche") from exc


@router.post("/{task_id}/release-payment")
def release_payment(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id),
):
    """Libère le paiement après 24h (si aucune contestation). Peut aussi être appelé
    avant les 24h par le client pour libérer immédiatement (satisfaction confirmée).
    """
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id and task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé")

        escrow = wallet_svc.get_escrow_by_task(task_id)
        if escrow is None:
            raise HTTPException(status_code=404, detail="Aucun escrow pour cette tâche")

        # Client can force-release early
        if task.created_by == user_id:
            try:
                escrow = wallet_svc.release_escrow(escrow.id)
            except EscrowError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
        else:
            # Executor waits for 24h
            try:
                escrow = wallet_svc.release_held_escrow(escrow.id)
            except EscrowError as exc:
                raise HTTPException(status_code=409, detail=str(exc))

        return success_response({
            "task_id": task_id,
            "escrow_id": escrow.id,
            "escrow_status": escrow.status,
            "amount": str(escrow.amount),
            "currency": escrow.currency,
            "message": "Paiement libéré avec succès.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de libérer le paiement") from exc


# ─── Geo Match ───────────────────────────────────────────────────────────────

@router.post("/match")
def match_tasks(
    payload: MatchQueryPayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    _ = user_id
    try:
        tasks = service.match_tasks(payload.latitude, payload.longitude, payload.radius_km)
        return success_response([_serialize_task(t) for t in tasks])
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de rechercher les tâches") from exc
