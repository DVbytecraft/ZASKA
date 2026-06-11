"""
Endpoints publics de demonstration — aucune authentification requise.

GET  /api/v1/allocation-rules
POST /api/v1/simulate-allocation
POST /api/v1/calculate-benefits

Utilises par le simulateur interactif du site vitrine ZASKA pour expliquer,
en temps reel et avec la logique de calcul reellement utilisee en production
(WalletService.calculate_social_split, modele social_v2), comment un montant
paye se repartit entre le tasker et les fonds de protection sociale.

Ces routes sont volontairement publiques (CORS *, pas de cle API) : elles ne
lisent ni n'ecrivent aucune donnee utilisateur, elles ne font que calculer.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.services.wallet_service import (
    SOCIAL_SPLIT_BPS,
    SOCIAL_SPLIT_LINES,
    SOCIAL_SPLIT_MODEL,
    WalletService,
)

router = APIRouter(prefix="/v1", tags=["public-demo"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SimulateAllocationRequest(BaseModel):
    amount: Decimal
    currency: str = "XOF"

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount doit etre superieur a 0")
        return value


class SimulateAllocationResponse(BaseModel):
    amount: Decimal
    currency: str
    split_model: str
    allocations: dict[str, Decimal]
    percentages: dict[str, float]


class CalculateBenefitsRequest(BaseModel):
    monthly_revenue: Decimal
    currency: str = "XOF"
    months: int = 12

    @field_validator("monthly_revenue")
    @classmethod
    def _revenue_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("monthly_revenue doit etre superieur a 0")
        return value

    @field_validator("months")
    @classmethod
    def _months_in_range(cls, value: int) -> int:
        if not (1 <= value <= 360):
            raise ValueError("months doit etre compris entre 1 et 360")
        return value


class CalculateBenefitsResponse(BaseModel):
    monthly_revenue: Decimal
    currency: str
    months: int
    monthly_contributions: dict[str, Decimal]
    projected_totals: dict[str, Decimal]


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/allocation-rules")
def get_allocation_rules() -> dict:
    """Regles de repartition sociale actuellement en vigueur (modele social_v2)."""
    return {
        "split_model": SOCIAL_SPLIT_MODEL,
        "lines": list(SOCIAL_SPLIT_LINES),
        "split_bps": SOCIAL_SPLIT_BPS,
        "percentages": {line: bps / 100 for line, bps in SOCIAL_SPLIT_BPS.items()},
        "description": {
            "tasker_net": "Montant net verse au tasker",
            "zaska_operations": "Frais de fonctionnement de la plateforme ZASKA",
            "pension_fund": "Caisse de retraite des taskers",
            "health_fund": "Caisse de sante des taskers",
            "smoothing_fund": "Fonds de lissage des revenus",
        },
    }


@router.post("/simulate-allocation", response_model=SimulateAllocationResponse)
def simulate_allocation(payload: SimulateAllocationRequest) -> SimulateAllocationResponse:
    """Repartit un montant selon le modele social_v2 reellement applique en production."""
    try:
        allocations = WalletService.calculate_social_split(payload.amount)
    except InvalidOperation as exc:
        raise HTTPException(status_code=400, detail="Montant invalide") from exc

    return SimulateAllocationResponse(
        amount=payload.amount,
        currency=payload.currency,
        split_model=SOCIAL_SPLIT_MODEL,
        allocations=allocations,
        percentages={line: bps / 100 for line, bps in SOCIAL_SPLIT_BPS.items()},
    )


@router.post("/calculate-benefits", response_model=CalculateBenefitsResponse)
def calculate_benefits(payload: CalculateBenefitsRequest) -> CalculateBenefitsResponse:
    """Projette les contributions mensuelles aux fonds de protection sociale sur N mois."""
    try:
        monthly = WalletService.calculate_social_split(payload.monthly_revenue)
    except InvalidOperation as exc:
        raise HTTPException(status_code=400, detail="Montant invalide") from exc

    projected = {line: amount * payload.months for line, amount in monthly.items()}

    return CalculateBenefitsResponse(
        monthly_revenue=payload.monthly_revenue,
        currency=payload.currency,
        months=payload.months,
        monthly_contributions=monthly,
        projected_totals=projected,
    )
