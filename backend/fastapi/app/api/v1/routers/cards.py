"""Cartes de crédit virtuelles Visa/Mastercard — génération et gestion."""
from __future__ import annotations

import hashlib
import hmac
import random
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db, require_kyc_approved
from app.core.config import settings
from app.core.responses import success_response
from app.models.virtual_card import VirtualCard

router = APIRouter(prefix="/cards", tags=["cards"])

_VISA_PREFIXES = ["4532", "4916", "4556", "4929"]
_MASTERCARD_PREFIXES = ["5234", "5412", "5522", "5198"]


def _luhn_checksum(number: str) -> int:
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10


def _generate_card_number(card_type: str) -> str:
    """Generate a valid Luhn card number."""
    if card_type == "visa":
        prefix = random.choice(_VISA_PREFIXES)
        length = 16
    else:
        prefix = random.choice(_MASTERCARD_PREFIXES)
        length = 16

    partial = prefix + "".join([str(random.randint(0, 9)) for _ in range(length - len(prefix) - 1)])
    # Compute check digit
    check = (10 - _luhn_checksum(partial + "0")) % 10
    return partial + str(check)


def _mask_card(number: str) -> str:
    return f"{number[:4]} **** **** {number[-4:]}"


def _hash_value(value: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _generate_expiry() -> tuple[int, int]:
    """Expiry = 4 years from now."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return now.month, now.year + 4


def _generate_cvv() -> str:
    return str(random.randint(100, 999))


def _serialize_card(card: VirtualCard, show_full: bool = False) -> dict:
    return {
        "id": card.id,
        "cardType": card.card_type,
        "cardNumberMasked": card.card_number_masked,
        "expiryMonth": card.expiry_month,
        "expiryYear": card.expiry_year,
        "status": card.status,
        "walletCurrency": card.wallet_currency,
        "createdAt": card.created_at.isoformat(),
    }


class CardCreatePayload(BaseModel):
    card_type: str = Field(pattern="^(visa|mastercard)$")
    wallet_currency: str = Field(default="USD", min_length=3, max_length=8)


class CardStatusPayload(BaseModel):
    status: str = Field(pattern="^(active|frozen|cancelled)$")


@router.get("")
def list_cards(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    cards = (
        db.query(VirtualCard)
        .filter(VirtualCard.user_id == user_id, VirtualCard.status != "cancelled")
        .order_by(VirtualCard.created_at.desc())
        .all()
    )
    return success_response([_serialize_card(c) for c in cards])


@router.post("")
def generate_card(
    payload: CardCreatePayload,
    user_id: str = Depends(require_kyc_approved),
    db: Session = Depends(get_db),
):
    """Génère une carte virtuelle Visa ou Mastercard pour l'utilisateur."""
    # Limit: max 2 active cards per user
    active_count = (
        db.query(VirtualCard)
        .filter(VirtualCard.user_id == user_id, VirtualCard.status == "active")
        .count()
    )
    if active_count >= 2:
        raise HTTPException(
            status_code=409,
            detail="Limite de 2 cartes actives atteinte. Annulez une carte existante pour en créer une nouvelle.",
        )

    card_number = _generate_card_number(payload.card_type)
    cvv = _generate_cvv()
    expiry_month, expiry_year = _generate_expiry()

    card = VirtualCard(
        user_id=user_id,
        card_type=payload.card_type,
        card_number_masked=_mask_card(card_number),
        card_number_hash=_hash_value(card_number),
        expiry_month=expiry_month,
        expiry_year=expiry_year,
        cvv_hash=_hash_value(cvv),
        status="active",
        wallet_currency=payload.wallet_currency.upper(),
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    # Return full details only at creation time
    return success_response({
        **_serialize_card(card),
        "cardNumber": _mask_card(card_number),
        "cvv": cvv,
        "expiryFormatted": f"{expiry_month:02d}/{str(expiry_year)[-2:]}",
        "notice": "Conservez ces informations en sécurité. Le CVV ne sera plus affiché.",
    })


@router.patch("/{card_id}/status")
def update_card_status(
    card_id: str,
    payload: CardStatusPayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    card = db.query(VirtualCard).filter(VirtualCard.id == card_id, VirtualCard.user_id == user_id).one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Carte introuvable")
    if card.status == "cancelled":
        raise HTTPException(status_code=409, detail="Une carte annulée ne peut pas être modifiée")

    card.status = payload.status
    db.commit()
    db.refresh(card)
    return success_response(_serialize_card(card))
