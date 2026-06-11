"""
P4 — Public demo endpoints (no auth, CORS *).

Covers:
  - GET  /api/v1/allocation-rules
  - POST /api/v1/simulate-allocation
  - POST /api/v1/calculate-benefits

These reuse WalletService.calculate_social_split (the real, corrected
social_v2 split logic from P1.3) so the public website demo always matches
production behaviour.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routers import public_demo
from app.services.wallet_service import SOCIAL_SPLIT_BPS, WalletService


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(public_demo.router, prefix="/api")
    return TestClient(app)


def test_allocation_rules_matches_social_split_bps(client: TestClient) -> None:
    response = client.get("/api/v1/allocation-rules")
    assert response.status_code == 200
    body = response.json()
    assert body["split_model"] == "social_v2"
    assert body["split_bps"] == SOCIAL_SPLIT_BPS


def test_simulate_allocation_matches_wallet_service(client: TestClient) -> None:
    response = client.post("/api/v1/simulate-allocation", json={"amount": "300", "currency": "XOF"})
    assert response.status_code == 200
    body = response.json()

    expected = WalletService.calculate_social_split(Decimal("300"))
    assert Decimal(body["allocations"]["tasker_net"]) == expected["tasker_net"]
    assert Decimal(body["allocations"]["zaska_operations"]) == expected["zaska_operations"]
    assert body["currency"] == "XOF"
    assert body["split_model"] == "social_v2"


def test_simulate_allocation_rejects_non_positive_amount(client: TestClient) -> None:
    response = client.post("/api/v1/simulate-allocation", json={"amount": "0"})
    assert response.status_code == 422

    response = client.post("/api/v1/simulate-allocation", json={"amount": "-10"})
    assert response.status_code == 422


def test_calculate_benefits_projects_over_months(client: TestClient) -> None:
    response = client.post(
        "/api/v1/calculate-benefits",
        json={"monthly_revenue": "1000", "currency": "XOF", "months": 12},
    )
    assert response.status_code == 200
    body = response.json()

    monthly = WalletService.calculate_social_split(Decimal("1000"))
    assert Decimal(body["monthly_contributions"]["pension_fund"]) == monthly["pension_fund"]
    assert Decimal(body["projected_totals"]["pension_fund"]) == monthly["pension_fund"] * 12


def test_calculate_benefits_rejects_invalid_months(client: TestClient) -> None:
    response = client.post(
        "/api/v1/calculate-benefits",
        json={"monthly_revenue": "1000", "months": 0},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/calculate-benefits",
        json={"monthly_revenue": "1000", "months": 361},
    )
    assert response.status_code == 422
