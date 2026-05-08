from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TaskCreatePayload(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=2000)
    price: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)
    latitude: float
    longitude: float
    address: str | None = Field(default=None, max_length=512)
    mode: str | None = Field(default=None, pattern="^(fast|choose)$")
    status: str = Field(default="OPEN", pattern="^(OPEN|ASSIGNED|COMPLETED)$")


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
