from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
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
    CancelTaskPayload,
    CompleteTaskPayload,
    MatchQueryPayload,
    TaskAcceptPayload,
    TaskApplyPayload,
    TaskCreatePayload,
    TaskStatusPayload,
    TaskUpdatePayload,
)
from app.services.task_service import TaskService
from app.services.wallet_service import EscrowError, InsufficientFundsError, WalletService

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ─── In-app notification helper ───────────────────────────────────────────────

def _notify(db: Session, user_id: str, type_: str, title: str, body: str, task_id: str | None = None) -> None:
    """Persist a single in-app notification. Never raises."""
    try:
        from app.models.notification import Notification
        notif = Notification(user_id=user_id, type=type_, title=title, body=body, task_id=task_id)
        db.add(notif)
        db.flush()
    except Exception:
        pass


def _record_neg_event(
    db: Session, task_id: str, actor_id: str,
    event_type: str, price: Decimal | None, currency: str
) -> None:
    """Persist a negotiation event to the audit trail. Never raises."""
    try:
        from app.models.negotiation_event import NegotiationEvent
        ev = NegotiationEvent(
            task_id=task_id, actor_id=actor_id,
            event_type=event_type, price=price, currency=currency,
        )
        db.add(ev)
        db.flush()
    except Exception:
        pass


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
        "mode": getattr(task, "mode", "fast") or "fast",
        "createdBy": task.created_by,
        "assignedTo": task.assigned_to,
        "completionPercent": task.completion_percent,
        "negotiationStatus": task.negotiation_status,
        "originalPrice": float(task.original_price) if task.original_price else None,
        "negotiatedPrice": float(task.negotiated_price) if task.negotiated_price else None,
        "negotiatedBy": task.negotiated_by,
        "scheduledAt": task.scheduled_at.isoformat() if task.scheduled_at else None,
        "anySchedule": bool(task.any_schedule),
        "createdAt": task.created_at.isoformat() if task.created_at else None,
        "stops": task.stops,
        "city": getattr(task, "city", None),
        "country": getattr(task, "country", None),
        "creatorRated": bool(getattr(task, "creator_rated", False)),
        "proofPhotoUrl": getattr(task, "proof_photo_url", None),
    }


def _serialize_application(app, user: User) -> dict:
    display_name = (
        " ".join(filter(None, [user.first_name, user.last_name]))
        or (user.email.split("@")[0] if user.email else user.id[:8])
    )
    rating_count = getattr(user, "rating_count", 0) or 0
    rating_sum = getattr(user, "rating_sum", 0.0) or 0.0
    rating = round(rating_sum / rating_count, 1) if rating_count > 0 else None
    return {
        "id": app.id,
        "taskId": app.task_id,
        "taskerId": app.tasker_id,
        "taskerName": display_name,
        "taskerEmail": user.email,
        "taskerRating": rating,
        "taskerReviews": rating_count if rating_count > 0 else None,
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
        # Idempotency: return existing task if this key was already used
        idem_key = data.get("idempotency_key")
        if idem_key:
            existing = service.find_by_idempotency_key(idem_key)
            if existing:
                return success_response(_serialize_task(existing))
        # When stops provided, derive primary coords from first stop
        if data.get("stops"):
            first = data["stops"][0]
            data["latitude"] = first["latitude"]
            data["longitude"] = first["longitude"]
            data["address"] = first["address"]
        elif not data.get("latitude") or not data.get("longitude"):
            raise HTTPException(status_code=422, detail="latitude et longitude requis si stops absent")
        task = service.create_task(data)
        return success_response(_serialize_task(task))
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except IntegrityError:
        # Race condition on idempotency key — return the already-created task
        idem_key = payload.idempotency_key
        if idem_key:
            existing = service.find_by_idempotency_key(idem_key)
            if existing:
                return success_response(_serialize_task(existing))
        raise HTTPException(status_code=409, detail="Tâche déjà créée (clé d'idempotence)")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de créer la tâche") from exc


@router.get("")
def list_tasks(
    status: str | None = None,
    mine: bool = False,
    assigned_to_me: bool = False,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    country: str | None = None,
    city: str | None = None,
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
            radius_km=radius_km,
            country=country,
            city=city,
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


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: str,
    payload: CancelTaskPayload,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Client annule une tâche ASSIGNED ou PAUSED.
    - republish=True → tâche republiée (OPEN), escrow remboursé
    - republish=False → tâche annulée définitivement (CANCELLED), escrow remboursé
    """
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé")
        if task.status not in ("ASSIGNED", "PAUSED", "OPEN"):
            raise HTTPException(status_code=409, detail="La tâche ne peut être annulée dans cet état")

        tasker_id = task.assigned_to
        new_status = "OPEN" if payload.republish else "CANCELLED"

        # Refund escrow if funded (only relevant when ASSIGNED)
        if tasker_id:
            escrow = wallet_svc.get_escrow_by_task(task_id)
            if escrow and escrow.status in ("funded", "hold"):
                try:
                    wallet_svc.refund_escrow(escrow.id)
                except EscrowError as exc:
                    raise HTTPException(status_code=409, detail=f"Remboursement impossible : {exc}. Annulation refusée.")

        updated = service.cancel_task(task_id, new_status)

        # Notify tasker
        if tasker_id:
            msg = ("Le client a annulé cette tâche et l'a republiée. Votre paiement a été remboursé."
                   if payload.republish else
                   "Le client a annulé définitivement cette tâche. Votre paiement a été remboursé.")
            _notify(db, tasker_id, "warning", "Tâche annulée", msg, task_id=task_id)
        db.commit()

        out_msg = ("Tâche republiée. Le paiement a été remboursé." if payload.republish
                   else "Tâche annulée définitivement. Le paiement a été remboursé.")
        return success_response({**_serialize_task(updated), "message": out_msg})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'annuler la tâche") from exc


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

        # Freeze: one active application at a time (first-come, first-served)
        if service.count_pending_applications(task_id) > 0:
            raise HTTPException(
                status_code=409,
                detail="Cette tâche est déjà en cours de traitement par un prestataire. Réessayez plus tard.",
            )

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

        _notify(db, task.created_by, "info", "Nouvelle candidature",
                f"Un prestataire a postulé à votre tâche : {task.title}", task_id=task_id)
        db.commit()

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
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Vous avez déjà postulé à cette tâche")
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
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        task = _get_task_or_404(task_id, service)
        if task.status != "OPEN":
            raise HTTPException(status_code=409, detail="Cette tâche n'est plus ouverte")

        creator_is_acting = task.created_by == user_id
        if creator_is_acting:
            if not payload.tasker_id:
                raise HTTPException(status_code=400, detail="tasker_id requis pour accepter un exécutant")
            tasker_id = payload.tasker_id
        else:
            tasker_id = user_id

        task = service.accept_task(task_id=task_id, tasker_id=tasker_id)

        # In-app + email notifications (best-effort)
        try:
            if creator_is_acting:
                # Choose Mode: notify the accepted tasker
                tasker = db.get(User, tasker_id)
                _notify(db, tasker_id, "success", "Candidature acceptée ! 🎉",
                        f"Le client a accepté votre candidature pour : {task.title}", task_id=task_id)
                if tasker and tasker.email:
                    from app.core.email import send_application_accepted_email
                    send_application_accepted_email(
                        to_email=tasker.email,
                        task_title=task.title,
                    )
            else:
                # Fast Mode: notify the creator that a tasker self-assigned
                creator = db.get(User, task.created_by)
                tasker = db.get(User, tasker_id)
                tasker_name = " ".join(filter(None, [tasker.first_name, tasker.last_name])) if tasker else "Un prestataire"
                _notify(db, task.created_by, "info", "Prestataire assigné",
                        f"{tasker_name} a accepté votre tâche : {task.title}", task_id=task_id)
                if creator and creator.email:
                    from app.core.email import send_task_application_email
                    send_task_application_email(
                        to_email=creator.email,
                        task_title=task.title,
                        tasker_name=tasker_name,
                        proposed_price=None,
                        currency=task.currency,
                    )
        except Exception:
            pass

        db.commit()
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
        if task.assigned_to != user_id and task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé à négocier cette tâche")
        if task.status not in ("OPEN", "ASSIGNED"):
            raise HTTPException(status_code=409, detail="La négociation n'est possible que sur une tâche en cours ou ouverte")
        # Prevent proposing when you're already the proposer (wait for other party)
        if task.negotiation_status == "pending" and task.negotiated_by == user_id:
            raise HTTPException(status_code=409, detail="Vous avez déjà soumis un prix. Attendez la réponse de l'autre partie.")

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

        _notify(db, task.created_by, "warning", "Modification de prix demandée",
                f"Un prestataire propose un nouveau prix pour : {task.title}", task_id=task_id)
        _record_neg_event(db, task_id, user_id, "proposed", payload.proposed_price, task.currency)
        db.commit()

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
    wallet_svc: WalletService = Depends(get_wallet_service),
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
            # Adjust escrow amount to match the newly accepted price
            try:
                escrow = wallet_svc.get_escrow_by_task(task_id)
                if escrow and task.price and escrow.status in ("funded", "hold"):
                    diff = task.price - escrow.amount
                    if diff < Decimal("0"):
                        # Negotiated price is lower — refund surplus to client
                        wallet_svc.credit_wallet(
                            user_id=escrow.payer_id, currency=escrow.currency,
                            amount=-diff, reference=f"neg_refund:{escrow.id}",
                            metadata={"type": "negotiation_refund", "task_id": task_id},
                        )
                        escrow.amount = task.price
                        db.flush()
                    elif diff > Decimal("0"):
                        # Negotiated price is higher — debit client if they have funds
                        try:
                            wallet_svc.debit_wallet(
                                user_id=escrow.payer_id, currency=escrow.currency,
                                amount=diff, reference=f"neg_topup:{escrow.id}",
                                metadata={"type": "negotiation_topup", "task_id": task_id},
                            )
                            escrow.amount = task.price
                            db.flush()
                        except InsufficientFundsError:
                            # Client can't afford the increase — escrow stays at original amount
                            pass
            except Exception:
                pass  # escrow adjustment is best-effort
        else:
            task = service.reject_negotiation(task_id)

        # Notify negotiator via email if we have their email
        negotiator = db.get(User, task.negotiated_by) if task.negotiated_by else None
        if negotiator and negotiator.email:
            try:
                from app.core.email import send_price_accepted_email, send_price_rejected_email
                if payload.accept:
                    send_price_accepted_email(
                        to_email=negotiator.email,
                        task_title=task.title,
                        accepted_price=float(task.negotiated_price or task.price),
                        currency=task.currency,
                    )
                else:
                    send_price_rejected_email(
                        to_email=negotiator.email,
                        task_title=task.title,
                        original_price=float(task.original_price or task.price),
                        currency=task.currency,
                    )
            except Exception:
                pass

        # In-app notification to the executor who proposed the price
        if task.negotiated_by:
            if payload.accept:
                _notify(db, task.negotiated_by, "success", "Modification de prix acceptée ✓",
                        f"Le client a accepté votre prix pour : {task.title}", task_id=task_id)
            else:
                _notify(db, task.negotiated_by, "warning", "Modification de prix refusée",
                        f"Le client a refusé votre demande de prix pour : {task.title}", task_id=task_id)
        ev_type = "accepted" if payload.accept else "rejected"
        ev_price = task.negotiated_price if payload.accept else None
        _record_neg_event(db, task_id, user_id, ev_type, ev_price, task.currency)
        db.commit()

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
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Exécutant abandonne après refus du prix → tâche republié (OPEN)."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id and task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé")
        # Either party can abandon a pending or open negotiation
        if task.negotiation_status not in ("pending", "none") or task.status not in ("OPEN", "ASSIGNED"):
            raise HTTPException(status_code=409, detail="Aucune négociation active à abandonner")

        task = service.abandon_and_republish(task_id)
        _record_neg_event(db, task_id, user_id, "abandoned", None, task.currency)
        db.commit()
        return success_response({
            **_serialize_task(task),
            "message": "Tâche abandonnée et republiée. Elle est de nouveau visible pour tous.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'abandonner la tâche") from exc


@router.get("/{task_id}/negotiate/history")
def get_negotiation_history(
    task_id: str,
    service: TaskService = Depends(get_task_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Historique complet des échanges de prix pour une tâche."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id and task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Accès non autorisé à cet historique")
        from app.models.negotiation_event import NegotiationEvent
        events = (
            db.query(NegotiationEvent)
            .filter(NegotiationEvent.task_id == task_id)
            .order_by(NegotiationEvent.created_at.asc())
            .all()
        )
        # Enrich with actor name
        actor_cache: dict[str, str] = {}
        def actor_name(actor_id: str) -> str:
            if actor_id not in actor_cache:
                u = db.get(User, actor_id)
                if u:
                    name = " ".join(filter(None, [u.first_name, u.last_name])) or (u.email or u.id[:8])
                else:
                    name = actor_id[:8]
                actor_cache[actor_id] = name
            return actor_cache[actor_id]

        result = [
            {
                "id": ev.id,
                "taskId": ev.task_id,
                "actorId": ev.actor_id,
                "actorName": actor_name(ev.actor_id),
                "eventType": ev.event_type,
                "price": float(ev.price) if ev.price is not None else None,
                "currency": ev.currency,
                "createdAt": ev.created_at.isoformat(),
            }
            for ev in events
        ]
        return success_response(result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de charger l'historique") from exc


# ─── Task Completion ──────────────────────────────────────────────────────────

@router.post("/{task_id}/complete")
def mark_task_complete(
    task_id: str,
    payload: CompleteTaskPayload,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Exécutant déclare la prestation terminée (totalement ou partiellement).
    Passe la tâche en PENDING_VALIDATION et ouvre une fenêtre de 6h.
    Le client confirme ou conteste directement dans l'app.
    """
    try:
        task = _get_task_or_404(task_id, service)
        if task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Seul l'exécutant assigné peut déclarer la tâche terminée")
        if task.status != "ASSIGNED":
            raise HTTPException(status_code=409, detail="La tâche doit être ASSIGNED pour être déclarée terminée")

        pct = payload.completion_percent if payload.partial else 100
        service.set_completion_percent(task_id, pct)
        if payload.proof_photo_url:
            task.proof_photo_url = payload.proof_photo_url
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

        if pct < 100:
            notif_body = f"Votre prestataire a déclaré la tâche terminée à {pct}% : {task.title}. Vous avez 6h pour confirmer."
        else:
            notif_body = f"Votre prestataire a déclaré la tâche terminée : {task.title}. Vous avez 6h pour confirmer."
        _notify(db, task.created_by, "success", "Prestation déclarée terminée", notif_body, task_id=task_id)
        db.commit()

        logger.info("task:pending_validation task_id={} pct={}", task_id, pct)
        return success_response({
            "task_id": task_id,
            "status": "PENDING_VALIDATION",
            "completion_percent": pct,
            "partial": pct < 100,
            "message": (f"Prestation déclarée terminée à {pct}%. Le client a 6h pour confirmer."
                        if pct < 100 else
                        "Prestation déclarée terminée. Le client a 6h pour confirmer ou contester."),
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

        # Release escrow — proportionally if partial, fully if complete
        escrow = wallet_svc.get_escrow_by_task(task_id)
        if escrow and escrow.status in ("funded", "hold"):
            try:
                pct = task.completion_percent if task.completion_percent is not None else 100
                if pct < 100:
                    wallet_svc.partial_release_escrow(escrow.id, pct)
                else:
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

        if task.assigned_to:
            pct = task.completion_percent if task.completion_percent is not None else 100
            gross = float(escrow.amount) if escrow else 0.0
            if pct < 100:
                net = round(gross * 0.10, 2)
                zaska_cut = round(gross * 0.05, 2)
                client_back = round(gross * 0.85, 2)
                pay_msg = (
                    f"Paiement libéré pour {task.title}. "
                    f"Brut : {gross:.2f} {task.currency}. "
                    f"Votre part (10%) : {net:.2f} — Commission ZASKA (5%) : {zaska_cut:.2f} — "
                    f"Remboursement client (85%) : {client_back:.2f} {task.currency}."
                )
            else:
                commission_bps = settings.zaska_commission_bps
                zaska_cut = round(gross * commission_bps / 10000, 2)
                net = round(gross - zaska_cut, 2)
                pay_msg = (
                    f"Paiement libéré pour {task.title}. "
                    f"Brut : {gross:.2f} {task.currency}. "
                    f"Commission ZASKA (15%) : {zaska_cut:.2f} — "
                    f"Net reçu : {net:.2f} {task.currency}."
                )
            _notify(db, task.assigned_to, "success", "Paiement libéré 🎉", pay_msg, task_id=task_id)
        db.commit()

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


# ─── Rating ───────────────────────────────────────────────────────────────────

class RateTaskPayload(BaseModel):
    score: int = Field(ge=1, le=5)


@router.post("/{task_id}/rate")
def rate_task(
    task_id: str,
    payload: RateTaskPayload,
    service: TaskService = Depends(get_task_service),
    user_id: str = Depends(get_current_user_id),
):
    """Créateur note le prestataire (1–5) après la fin de la tâche. Une seule fois par tâche."""
    try:
        service.rate_task(task_id=task_id, score=payload.score, rater_id=user_id)
        return success_response({"rated": True, "score": payload.score})
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'enregistrer la note") from exc


# ─── Tasker abandon ──────────────────────────────────────────────────────────

class TaskerAbandonPayload(BaseModel):
    completion_percent: int = Field(default=0, ge=0, le=99,
        description="Pourcentage de travail réellement accompli (0 = rien fait, 1-99 = travail partiel). "
                    "Détermine le remboursement : 0% → client remboursé intégralement ; "
                    ">0% → exécutant payé proportionnellement, client remboursé du reste.")


@router.post("/{task_id}/tasker-abandon")
def tasker_abandon(
    task_id: str,
    payload: TaskerAbandonPayload,
    service: TaskService = Depends(get_task_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """L'exécutant assigné se désiste.

    - completion_percent == 0 : n'a pas commencé → remboursement intégral au client.
    - completion_percent 1–99 : travail partiel → exécutant reçoit sa part, client
      remboursé du reste. Nécessite que l'escrow ait un payee_id (tâche financée).
    """
    try:
        task = _get_task_or_404(task_id, service)
        if task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Seul l'exécutant assigné peut se désister")
        if task.status not in ("ASSIGNED", "PAUSED"):
            raise HTTPException(status_code=409, detail="Le désistement n'est possible que sur une tâche ASSIGNED ou PAUSED")

        pct = payload.completion_percent
        escrow = wallet_svc.get_escrow_by_task(task_id)

        if escrow and escrow.status in ("funded", "hold"):
            try:
                if pct == 0:
                    # Hasn't started — full refund to client
                    wallet_svc.refund_escrow(escrow.id)
                    payment_msg = "Remboursement intégral effectué au client."
                else:
                    # Partial work done — proportional split
                    if not escrow.payee_id:
                        # Assign payee so partial_release_escrow can credit the tasker
                        escrow.payee_id = user_id
                        db.flush()
                    _, exec_amt, client_refund = wallet_svc.partial_release_escrow(escrow.id, pct)
                    payment_msg = (
                        f"Désistement à {pct}% : votre part (10%) = {exec_amt} {escrow.currency}. "
                        f"Commission ZASKA (5%) déduite. Client remboursé (85%) : {client_refund} {escrow.currency}."
                    )
            except EscrowError as exc:
                raise HTTPException(status_code=409, detail=f"Erreur de paiement : {exc}")
        else:
            payment_msg = "Aucun paiement actif à rembourser."

        # Record declared completion before resetting the task
        if pct > 0:
            service.set_completion_percent(task_id, pct)

        task = service.tasker_abandon(task_id=task_id, tasker_id=user_id)

        # Notify creator
        creator = db.get(User, task.created_by)
        tasker = db.get(User, user_id)
        tasker_name = " ".join(filter(None, [tasker.first_name, tasker.last_name])) if tasker else "Le prestataire"

        if pct == 0:
            notif_body = f"{tasker_name} a abandonné votre tâche sans l'avoir commencée : {task.title}. Vous avez été remboursé intégralement."
            email_body = (
                f"<p>{tasker_name} a abandonné la tâche <strong>{task.title}</strong> sans l'avoir commencée.</p>"
                f"<p>Vous avez été remboursé intégralement. La tâche est de nouveau disponible.</p>"
            )
        else:
            notif_body = (
                f"{tasker_name} a abandonné votre tâche à {pct}% : {task.title}. "
                f"Remboursement partiel effectué. La tâche est de nouveau disponible."
            )
            email_body = (
                f"<p>{tasker_name} a abandonné la tâche <strong>{task.title}</strong> après en avoir réalisé {pct}%.</p>"
                f"<p>{payment_msg} La tâche est de nouveau disponible.</p>"
            )

        _notify(db, task.created_by, "warning", "Prestataire désisté", notif_body, task_id=task_id)
        if creator and creator.email:
            try:
                from app.core.email import send_email
                send_email(
                    to_email=creator.email,
                    subject="ZASKA — Prestataire désisté",
                    html_content=email_body,
                    text_content=notif_body,
                )
            except Exception:
                pass

        db.commit()
        return success_response({
            **_serialize_task(task),
            "completion_percent_declared": pct,
            "payment_summary": payment_msg,
            "message": f"Désistement enregistré. {payment_msg} La tâche est de nouveau ouverte.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'enregistrer le désistement") from exc


# ─── Negotiation — multi-round fixes ─────────────────────────────────────────

class CounterProposePayload(BaseModel):
    proposed_price: Decimal = Field(gt=0)


@router.post("/{task_id}/negotiate/counter")
def counter_propose(
    task_id: str,
    payload: CounterProposePayload,
    service: TaskService = Depends(get_task_service),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """L'une ou l'autre partie soumet un contre-prix. Interdit à l'auteur de la proposition en cours."""
    try:
        task = _get_task_or_404(task_id, service)
        if task.created_by != user_id and task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Non autorisé")
        if task.negotiation_status == "pending" and task.negotiated_by == user_id:
            raise HTTPException(status_code=409, detail="Vous avez déjà soumis un prix, attendez la réponse de l'autre partie")

        task = service.propose_price(
            task_id=task_id, proposer_id=user_id,
            proposed_price=payload.proposed_price,
        )
        _record_neg_event(db, task_id, user_id, "counter", payload.proposed_price, task.currency)

        other_id = task.assigned_to if task.created_by == user_id else task.created_by
        if other_id:
            _notify(db, other_id, "warning", "Contre-proposition de prix",
                    f"Nouvelle proposition de prix pour : {task.title}", task_id=task_id)
        db.commit()

        return success_response({
            **_serialize_task(task),
            "message": "Contre-proposition envoyée. En attente de réponse.",
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d'envoyer la contre-proposition") from exc
