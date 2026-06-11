from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class TaskStop(BaseModel):
    model_config = ConfigDict(strict=False)
    address: str = Field(max_length=512)
    latitude: float
    longitude: float


class TaskCreatePayload(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=2000)
    price: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)
    # Primary location — derived from stops[0] when stops provided, else required
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = Field(default=None, max_length=512)
    mode: str | None = Field(default=None, pattern="^(fast|choose)$")
    status: str = Field(default="OPEN", pattern="^(OPEN|ASSIGNED|COMPLETED)$")
    service_category: str = Field(default="TASK", max_length=32)
    is_urgent: bool = False
    # Scheduling
    scheduled_at: datetime | None = None
    any_schedule: bool = False
    # Multi-stop: up to 4 waypoints [{address, latitude, longitude}]
    stops: Annotated[list[TaskStop], Field(max_length=4)] | None = None
    # Idempotency: client-generated UUID prevents double-submit
    idempotency_key: str | None = Field(default=None, max_length=64)
    # Structured location from reverse geocoding
    city: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=64)


class TaskApplyPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    proposed_price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    message: str | None = Field(default=None, max_length=1000)


class TaskAcceptPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    # Choose Mode : le client fournit l'ID du tasker à accepter.
    # Fast Mode   : vide — le tasker s'assigne lui-même.
    tasker_id: str | None = None


class TaskStatusPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    status: str = Field(pattern="^(OPEN|ASSIGNED|COMPLETED)$")


class CompleteTaskPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    partial: bool = False
    completion_percent: int = Field(default=100, ge=1, le=100)
    proof_photo_url: str | None = Field(default=None, max_length=512)


class CancelTaskPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    republish: bool = True
    reason: str | None = Field(default=None, max_length=500)


class TaskNegotiationPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    proposed_budget: Decimal = Field(gt=0)


class TaskUpdatePayload(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=3, max_length=2000)
    price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    latitude: float | None = None
    longitude: float | None = None


class MatchQueryPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    latitude: float
    longitude: float
    radius_km: float = Field(gt=0, le=100)
