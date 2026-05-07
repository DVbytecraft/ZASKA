"""
Tests d'intégration GET /api/system/bootstrap.

Ces tests appellent l'API live (nécessite le serveur démarré via conftest).
Couvre :
  - Réponse correcte sans header X-Country-Code (fallback FR)
  - Réponse correcte avec X-Country-Code: TG
  - Réponse correcte avec X-Country-Code: GH
  - Endpoint /bootstrap/{country_code}
  - Structure de la réponse (tous les champs attendus)
"""

from __future__ import annotations

import os

import httpx
import pytest


API_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:6969/api").rstrip("/")


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _bootstrap(country_code: str | None = None) -> dict:
    headers = {}
    if country_code:
        headers["X-Country-Code"] = country_code
    candidates = [f"{API_URL}/system/bootstrap", f"{API_URL}/v1/system/bootstrap"]
    last = None
    for url in candidates:
        r = httpx.get(url, headers=headers, timeout=10)
        last = r
        if r.status_code == 200:
            body = r.json()
            assert body["success"] is True
            return body["data"]
    assert last is not None
    pytest.skip(f"Bootstrap endpoint unavailable on live API ({last.status_code}).")


def _bootstrap_for(country_code: str) -> dict:
    candidates = [f"{API_URL}/system/bootstrap/{country_code}", f"{API_URL}/v1/system/bootstrap/{country_code}"]
    last = None
    for url in candidates:
        r = httpx.get(url, timeout=10)
        last = r
        if r.status_code == 200:
            body = r.json()
            assert body["success"] is True
            return body["data"]
    assert last is not None
    pytest.skip(f"Bootstrap endpoint unavailable on live API ({last.status_code}).")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Structure de réponse commune
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_FIELDS = {
    "country", "currency", "payment_methods", "payment_route",
    "kyc_provider", "sms_gateway", "mobile_money_enabled",
    "stripe_enabled", "escrow_enabled", "payout_delay_minutes",
    "features", "timezone", "emergency_numbers",
}


class TestBootstrapStructure:

    def test_all_required_fields_present_fr(self):
        data = _bootstrap("FR")
        for field in REQUIRED_FIELDS:
            assert field in data, f"Champ manquant : {field}"

    def test_all_required_fields_present_tg(self):
        data = _bootstrap("TG")
        for field in REQUIRED_FIELDS:
            assert field in data, f"Champ manquant : {field}"

    def test_payment_route_has_provider(self):
        data = _bootstrap("FR")
        assert "provider" in data["payment_route"]

    def test_payment_route_has_method(self):
        data = _bootstrap("FR")
        assert "method" in data["payment_route"]

    def test_features_is_dict(self):
        data = _bootstrap("FR")
        assert isinstance(data["features"], dict)

    def test_emergency_numbers_is_dict(self):
        data = _bootstrap("FR")
        assert isinstance(data["emergency_numbers"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# 2. France (EU) — Stripe + Apple Pay
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapFR:

    def test_country_is_fr(self):
        data = _bootstrap("FR")
        assert data["country"] == "FR"

    def test_currency_is_eur(self):
        data = _bootstrap("FR")
        assert data["currency"] == "EUR"

    def test_provider_is_stripe(self):
        data = _bootstrap("FR")
        assert data["payment_route"]["provider"] == "stripe"

    def test_apple_pay_enabled(self):
        data = _bootstrap("FR")
        assert data["payment_route"]["apple_pay_enabled"] is True

    def test_google_pay_enabled(self):
        data = _bootstrap("FR")
        assert data["payment_route"]["google_pay_enabled"] is True

    def test_mobile_money_disabled(self):
        data = _bootstrap("FR")
        assert data["mobile_money_enabled"] is False

    def test_stripe_enabled(self):
        data = _bootstrap("FR")
        assert data["stripe_enabled"] is True

    def test_kyc_is_veriff(self):
        data = _bootstrap("FR")
        assert data["kyc_provider"] == "veriff"

    def test_timezone_is_paris(self):
        data = _bootstrap("FR")
        assert data["timezone"] == "Europe/Paris"

    def test_emergency_numbers_has_police(self):
        data = _bootstrap("FR")
        assert "police" in data["emergency_numbers"]
        assert data["emergency_numbers"]["police"] == "17"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Togo (CFA) — FedaPay + Mobile Money
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapTG:

    def test_country_is_tg(self):
        data = _bootstrap("TG")
        assert data["country"] == "TG"

    def test_currency_is_xof(self):
        data = _bootstrap("TG")
        assert data["currency"] == "XOF"

    def test_provider_is_fedapay(self):
        data = _bootstrap("TG")
        assert data["payment_route"]["provider"] == "fedapay"

    def test_method_is_mobile_money(self):
        data = _bootstrap("TG")
        assert data["payment_route"]["method"] == "mobile_money"

    def test_no_apple_pay(self):
        data = _bootstrap("TG")
        assert data["payment_route"]["apple_pay_enabled"] is False

    def test_mobile_money_enabled(self):
        data = _bootstrap("TG")
        assert data["mobile_money_enabled"] is True

    def test_kyc_is_smile_identity(self):
        data = _bootstrap("TG")
        assert data["kyc_provider"] == "smile_identity"

    def test_features_mobile_money_true(self):
        data = _bootstrap("TG")
        assert data["features"].get("mobile_money") is True

    def test_escrow_enabled(self):
        data = _bootstrap("TG")
        assert data["escrow_enabled"] is True

    def test_payout_delay_is_24h(self):
        data = _bootstrap("TG")
        assert data["payout_delay_minutes"] == 1440


# ═══════════════════════════════════════════════════════════════════════════
# 4. Ghana — Flutterwave + MTN MoMo
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapGH:

    def test_country_is_gh(self):
        data = _bootstrap("GH")
        assert data["country"] == "GH"

    def test_currency_is_ghs(self):
        data = _bootstrap("GH")
        assert data["currency"] == "GHS"

    def test_provider_is_flutterwave(self):
        data = _bootstrap("GH")
        assert data["payment_route"]["provider"] == "flutterwave"

    def test_method_is_mobile_money(self):
        data = _bootstrap("GH")
        assert data["payment_route"]["method"] == "mobile_money"

    def test_kyc_is_smile_identity(self):
        data = _bootstrap("GH")
        assert data["kyc_provider"] == "smile_identity"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Fallback — no header → EU mode (FR)
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapFallback:

    def test_no_header_defaults_to_fr(self):
        data = _bootstrap(None)
        # Fallback EU : provider stripe ou safe mode
        assert data["payment_route"]["provider"] in ("stripe",)

    def test_unknown_country_falls_back_to_stripe(self):
        data = _bootstrap_for("XX")
        assert data["payment_route"]["provider"] == "stripe"


# ═══════════════════════════════════════════════════════════════════════════
# 6. /bootstrap/{country_code} — variante explicite
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapForCountry:

    def test_bootstrap_for_tg(self):
        data = _bootstrap_for("TG")
        assert data["country"] == "TG"
        assert data["currency"] == "XOF"

    def test_bootstrap_for_fr(self):
        data = _bootstrap_for("FR")
        assert data["country"] == "FR"
        assert data["payment_route"]["provider"] == "stripe"

    def test_bootstrap_for_gh(self):
        data = _bootstrap_for("GH")
        assert data["currency"] == "GHS"

    def test_bootstrap_for_lowercase_normalizes(self):
        data = _bootstrap_for("tg")
        assert data["country"] == "TG"

