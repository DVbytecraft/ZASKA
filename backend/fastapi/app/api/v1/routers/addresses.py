"""Gestion des adresses utilisateur — Mes Adresses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.responses import success_response
from app.models.user_address import UserAddress

router = APIRouter(prefix="/addresses", tags=["addresses"])


class AddressCreatePayload(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    street: str = Field(min_length=2, max_length=255)
    city: str = Field(min_length=2, max_length=128)
    country: str = Field(min_length=2, max_length=64)
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False


class AddressUpdatePayload(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=64)
    street: str | None = Field(default=None, min_length=2, max_length=255)
    city: str | None = Field(default=None, min_length=2, max_length=128)
    country: str | None = Field(default=None, min_length=2, max_length=64)
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool | None = None


def _serialize(addr: UserAddress) -> dict:
    return {
        "id": addr.id,
        "label": addr.label,
        "street": addr.street,
        "city": addr.city,
        "country": addr.country,
        "latitude": addr.latitude,
        "longitude": addr.longitude,
        "isDefault": addr.is_default,
        "createdAt": addr.created_at.isoformat(),
    }


@router.get("")
def list_addresses(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    addresses = (
        db.query(UserAddress)
        .filter(UserAddress.user_id == user_id)
        .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc())
        .all()
    )
    return success_response([_serialize(a) for a in addresses])


@router.post("")
def create_address(
    payload: AddressCreatePayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if payload.is_default:
        db.query(UserAddress).filter(UserAddress.user_id == user_id).update({"is_default": False})

    addr = UserAddress(
        user_id=user_id,
        label=payload.label,
        street=payload.street,
        city=payload.city,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_default=payload.is_default,
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return success_response(_serialize(addr))


@router.patch("/{address_id}")
def update_address(
    address_id: str,
    payload: AddressUpdatePayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    addr = db.query(UserAddress).filter(UserAddress.id == address_id, UserAddress.user_id == user_id).one_or_none()
    if addr is None:
        raise HTTPException(status_code=404, detail="Adresse introuvable")

    if payload.is_default:
        db.query(UserAddress).filter(UserAddress.user_id == user_id).update({"is_default": False})

    changes = payload.model_dump(exclude_none=True)
    for key, val in changes.items():
        setattr(addr, key, val)

    db.commit()
    db.refresh(addr)
    return success_response(_serialize(addr))


@router.delete("/{address_id}")
def delete_address(
    address_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    addr = db.query(UserAddress).filter(UserAddress.id == address_id, UserAddress.user_id == user_id).one_or_none()
    if addr is None:
        raise HTTPException(status_code=404, detail="Adresse introuvable")
    db.delete(addr)
    db.commit()
    return success_response({"deleted": True})
