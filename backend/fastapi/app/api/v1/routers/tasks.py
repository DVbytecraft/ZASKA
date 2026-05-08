from __future__ import annotations

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
    assigned_to_me: bool = False,
    lat: float | None = None,
    lng: float | None = None,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        tasks, distances = service.list_tasks(
            status=status,
            created_by=user_id if mine else None,
            assigned_to=user_id if assigned_to_me else None,
            ref_lat=lat,
            ref_lng=lng,
        )
        result = []
        for t, dist in zip(tasks, distances):
            d = _serialize_task(t)
            d["distanceKm"] = round(dist, 1) if dist is not None else None
            result.append(d)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de charger les tâches") from exc


@router.get("/my-applications")
def get_my_applications(
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    try:
        applications = service.get_user_applications(user_id)
        return success_response([
            {
                "id": app.id,
                "taskId": app.task_id,
                "taskerId": app.tasker_id,
                "proposedPrice": float(app.proposed_price) if app.proposed_price is not None else None,
                "currency": app.currency,
                "status": app.status,
                "message": app.message,
                "createdAt": app.created_at.isoformat(),
            }
            for app in applications
        ])
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de charger vos candidatures") from exc


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
        if task.status in ("ASSIGNED", "PENDING_VALIDATION"):
            raise HTTPException(status_code=409, detail="Impossible de supprimer une tâche avec un prestataire actif")
        service.delete_task(task_id)
        return success_response({"deleted": True})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de supprimer la tâche") from exc


@router.post("/{task_id}/pause")
def pause_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    """Créateur désactive temporairement sa tâche (OPEN → PAUSED)."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé")
        if task.status != "OPEN":
            raise HTTPException(status_code=409, detail="Seules les tâches OPEN peuvent être mises en pause")
        task = service.update_status(task_id, "PAUSED")
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de mettre en pause la tâche") from exc


@router.post("/{task_id}/reactivate")
def reactivate_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    """Créateur réactive une tâche mise en pause (PAUSED → OPEN)."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé")
        if task.status != "PAUSED":
            raise HTTPException(status_code=409, detail="Seules les tâches PAUSED peuvent être réactivées")
        task = service.update_status(task_id, "OPEN")
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de réactiver la tâche") from exc


# ─── Choose Mode — Applications ──────────────────────────────────────────────

@router.post("/{task_id}/apply")
def apply_task(
    task_id: str,
    payload: TaskApplyPayload,
    service: TaskService = Depends(get_task_service),
    db: Session = Depends(get_db),
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

        # Notify task creator
        try:
            from app.core.email import send_task_application_email
            creator = db.get(User, task.created_by)
            tasker = db.get(User, user_id)
            if creator and creator.email:
                tasker_name = " ".join(filter(None, [tasker.first_name, tasker.last_name])) if tasker else "Un prestataire"
                send_task_application_email(
                    to_email=creator.email,
                    task_title=task.title,
                    tasker_name=tasker_name or "Un prestataire",
                    proposed_price=float(payload.proposed_price) if payload.proposed_price else None,
                    currency=currency,
                )
        except Exception:
            pass  # email is best-effort — never block the response

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
    db: Session = Depends(get_db),
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

        # Notify task creator of new price proposal
        try:
            from app.core.email import send_price_proposal_email
            creator = db.get(User, task.created_by)
            proposer = db.get(User, user_id)
            if creator and creator.email:
                proposer_name = " ".join(filter(None, [proposer.first_name, proposer.last_name])) if proposer else "Un prestataire"
                send_price_proposal_email(
                    to_email=creator.email,
                    task_title=task.title,
                    tasker_name=proposer_name or "Un prestataire",
                    proposed_price=float(payload.proposed_price),
                    currency=task.currency,
                )
        except Exception:
            pass

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


# ─── Task Completion ──────────────────────────────────────────────────────────

@router.post("/{task_id}/complete")
def mark_task_complete(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Exécutant déclare la prestation terminée.
    Passe la tâche en PENDING_VALIDATION et ouvre une fenêtre de 6h.
    Le client confirme ou conteste directement dans l'app — aucun code email requis.
    """
    try:
        task = _get_task_or_404(task_id, service)
        if task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Seul l'exécutant assigné peut déclarer la tâche terminée")
        if task.status != "ASSIGNED":
            raise HTTPException(status_code=409, detail="La tâche doit être ASSIGNED pour être déclarée terminée")

        service.update_status(task_id, "PENDING_VALIDATION")

        # Put escrow on 6h hold — auto-released if client doesn't act
        escrow = wallet_svc.get_escrow_by_task(task_id)
        if escrow and escrow.status == "funded":
            wallet_svc.hold_escrow_6h(escrow.id)

        # Notify client (best-effort)
        try:
            from app.core.email import send_task_done_email
            client = db.get(User, task.created_by)
            executor = db.get(User, user_id)
            if client and client.email:
                executor_name = " ".join(filter(None, [executor.first_name, executor.last_name])) if executor else "Le prestataire"
                send_task_done_email(
                    to_email=client.email,
                    task_title=task.title,
                    executor_name=executor_name or "Le prestataire",
                )
        except Exception:
            pass

        logger.info("task:pending_validation task_id={}", task_id)
        return success_response({
            "task_id": task_id,
            "status": "PENDING_VALIDATION",
            "message": "Prestation déclarée terminée. Le client a 6h pour confirmer ou contester.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task:complete_error task_id={} error={}", task_id, exc)
        raise HTTPException(status_code=500, detail="Impossible de déclarer la tâche terminée") from exc


@router.post("/{task_id}/confirm")
def confirm_task_complete(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Client confirme que le travail est réalisé → libération immédiate de l'escrow."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Seul le client peut confirmer la réalisation")
        if task.status != "PENDING_VALIDATION":
            raise HTTPException(status_code=409, detail="La tâche n'est pas en attente de validation")

        service.update_status(task_id, "COMPLETED")

        # Release escrow immediately — client explicitly confirmed
        escrow = wallet_svc.get_escrow_by_task(task_id)
        if escrow and escrow.status in ("funded", "hold"):
            try:
                wallet_svc.release_escrow(escrow.id)
            except EscrowError as exc:
                logger.error("task:confirm_escrow_error task_id={} error={}", task_id, exc)

        # Notify executor (best-effort)
        try:
            from app.core.email import send_email
            executor = db.get(User, task.assigned_to) if task.assigned_to else None
            if executor and executor.email:
                send_email(
                    to_email=executor.email,
                    subject="ZASKA — Paiement libéré !",
                    html_content=(
                        f"<p>Le client a confirmé la réalisation de <strong>{task.title}</strong>.</p>"
                        f"<p>Votre paiement a été libéré sur votre portefeuille ZASKA.</p>"
                    ),
                    text_content=f"Paiement libéré pour la tâche : {task.title}",
                )
        except Exception:
            pass

        logger.info("task:confirmed task_id={}", task_id)
        updated_task = service.get_task(task_id)
        return success_response({
            **(_serialize_task(updated_task) if updated_task else {"task_id": task_id}),
            "message": "Tâche confirmée. Le paiement a été libéré au prestataire.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task:confirm_error task_id={} error={}", task_id, exc)
        raise HTTPException(status_code=500, detail="Impossible de confirmer la tâche") from exc


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
    """Client conteste le travail dans la fenêtre de 6h. Le paiement est gelé."""
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
    """Libère le paiement après 6h (si aucune contestation). Peut aussi être appelé
    avant les 6h par le client pour libérer immédiatement (satisfaction confirmée).
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
            # Executor waits for 6h
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
