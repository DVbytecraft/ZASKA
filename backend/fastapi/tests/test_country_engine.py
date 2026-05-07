"""
Tests unitaires du Country Runtime Engine (CRE).
Ces tests sont purs — aucune API live ni base de données requise.
Lancer avec : pytest tests/test_country_engine.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.country_engine import (
    COUNTRY_REGISTRY,
    CFA_ZONE,
    EU_ZONE,
    CountryEngineService,
    FeatureFlagEngine,
    PaymentRouterService,
    get_config,
)
from app.core.country_engine.definitions import FLUTTERWAVE_ZONE


# ═══════════════════════════════════════════════════════════════════════════
# 1. test_country_resolution — registre statique
# ═══════════════════════════════════════════════════════════════════════════

class TestCountryResolution:

    def test_tg_config_currency_xof(self):
        cfg = get_config("TG")
        assert cfg.currency == "XOF"

    def test_tg_config_mobile_money_enabled(self):
        cfg = get_config("TG")
        assert cfg.mobile_money_enabled is True

    def test_tg_config_provider_fedapay(self):
        cfg = get_config("TG")
        assert "fedapay" in cfg.payment_providers

    def test_tg_config_kyc_smile_identity(self):
        cfg = get_config("TG")
        assert cfg.kyc_provider == "smile_identity"

    def test_fr_config_currency_eur(self):
        cfg = get_config("FR")
        assert cfg.currency == "EUR"

    def test_fr_config_stripe_enabled(self):
        cfg = get_config("FR")
        assert cfg.stripe_enabled is True

    def test_fr_config_no_mobile_money(self):
        cfg = get_config("FR")
        assert cfg.mobile_money_enabled is False

    def test_gh_config_currency_ghs(self):
        cfg = get_config("GH")
        assert cfg.currency == "GHS"

    def test_gh_config_provider_flutterwave(self):
        cfg = get_config("GH")
        assert "flutterwave" in cfg.payment_providers

    def test_unknown_country_fallback_to_default(self):
        cfg = get_config("XX")
        assert cfg.country_code == "DEFAULT"
        assert cfg.stripe_enabled is True  # safe fallback EU

    def test_case_insensitive_lookup(self):
        cfg_lower = get_config("tg")
        cfg_upper = get_config("TG")
        assert cfg_lower == cfg_upper

    def test_all_registry_entries_have_required_fields(self):
        for code, cfg in COUNTRY_REGISTRY.items():
            assert cfg.currency, f"{code}: currency manquante"
            assert cfg.kyc_provider, f"{code}: kyc_provider manquant"
            assert cfg.sms_gateway, f"{code}: sms_gateway manquant"
            assert cfg.timezone, f"{code}: timezone manquante"

    def test_cfa_zone_subset_of_registry(self):
        for cc in ["TG", "SN", "CI"]:
            assert cc in CFA_ZONE
            assert cc in COUNTRY_REGISTRY

    def test_eu_zone_contains_fr_be(self):
        assert "FR" in EU_ZONE
        assert "BE" in EU_ZONE


# ═══════════════════════════════════════════════════════════════════════════
# 2. test_payment_routing_fr — Zone EU → Stripe + Apple/Google Pay
# ═══════════════════════════════════════════════════════════════════════════

class TestPaymentRoutingFR:

    def test_provider_is_stripe(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        assert route.provider == "stripe"

    def test_method_is_card(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        assert route.method == "card"

    def test_apple_pay_enabled(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        assert route.apple_pay_enabled is True

    def test_google_pay_enabled(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        assert route.google_pay_enabled is True

    def test_region_eu(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        assert route.region == "EU"

    def test_currency_preserved(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        assert route.currency == "EUR"

    def test_be_same_as_fr(self):
        route_fr = PaymentRouterService.route_payment("FR", 100, "EUR")
        route_be = PaymentRouterService.route_payment("BE", 100, "EUR")
        assert route_fr.provider == route_be.provider
        assert route_fr.region == route_be.region

    def test_available_methods_includes_apple_google(self):
        route = PaymentRouterService.route_payment("FR", 100, "EUR")
        methods = route.available_methods()
        assert "apple_pay" in methods
        assert "google_pay" in methods
        assert "card" in methods

    def test_commission_computation(self):
        breakdown = PaymentRouterService.compute_commission(100, "FR")
        assert breakdown["provider"] == "stripe"
        assert breakdown["commission"] == pytest.approx(15.0)
        assert breakdown["escrow_amount"] == pytest.approx(85.0)
        assert breakdown["commission_rate"] == pytest.approx(0.15)


# ═══════════════════════════════════════════════════════════════════════════
# 3. test_payment_routing_tg — Zone CFA → FedaPay + Mobile Money
# ═══════════════════════════════════════════════════════════════════════════

class TestPaymentRoutingTG:

    def test_provider_is_fedapay(self):
        route = PaymentRouterService.route_payment("TG", 5000, "XOF")
        assert route.provider == "fedapay"

    def test_method_is_mobile_money(self):
        route = PaymentRouterService.route_payment("TG", 5000, "XOF")
        assert route.method == "mobile_money"

    def test_no_apple_pay(self):
        route = PaymentRouterService.route_payment("TG", 5000, "XOF")
        assert route.apple_pay_enabled is False

    def test_no_google_pay(self):
        route = PaymentRouterService.route_payment("TG", 5000, "XOF")
        assert route.google_pay_enabled is False

    def test_currency_is_xof(self):
        route = PaymentRouterService.route_payment("TG", 5000, "XOF")
        assert route.currency == "XOF"

    def test_region_is_waf_cfa(self):
        route = PaymentRouterService.route_payment("TG", 5000, "XOF")
        assert route.region == "WAF_CFA"

    def test_sn_same_as_tg(self):
        route_tg = PaymentRouterService.route_payment("TG", 5000, "XOF")
        route_sn = PaymentRouterService.route_payment("SN", 5000, "XOF")
        assert route_tg.provider == route_sn.provider
        assert route_tg.method == route_sn.method

    def test_ci_same_as_tg(self):
        route_tg = PaymentRouterService.route_payment("TG", 5000, "XOF")
        route_ci = PaymentRouterService.route_payment("CI", 5000, "XOF")
        assert route_tg.provider == route_ci.provider

    def test_commission_in_xof(self):
        breakdown = PaymentRouterService.compute_commission(10000, "TG")
        assert breakdown["provider"] == "fedapay"
        assert breakdown["commission"] == pytest.approx(1500.0)
        assert breakdown["escrow_amount"] == pytest.approx(8500.0)


# ═══════════════════════════════════════════════════════════════════════════
# 4. test_feature_flags_merge — statique + override DB
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureFlagsMerge:

    def _make_engine(self, db_flags=None, db_country=None) -> FeatureFlagEngine:
        """Construit un FeatureFlagEngine avec Redis et DB mockés."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None   # cache miss systématique
        mock_redis.setex.return_value = True

        mock_country = MagicMock() if db_country is not False else None
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = mock_country

        if db_flags is not None and mock_country:
            mock_db.query.return_value.filter.return_value.all.return_value = db_flags
        else:
            mock_db.query.return_value.filter.return_value.all.return_value = []

        return FeatureFlagEngine(mock_redis, mock_db)

    def test_tg_static_flags_mobile_money_true(self):
        engine = self._make_engine()
        flags = engine.get_flags("TG")
        assert flags.get("mobile_money") is True

    def test_tg_static_flags_escrow_true(self):
        engine = self._make_engine()
        flags = engine.get_flags("TG")
        assert flags.get("escrow") is True

    def test_fr_static_flags_apple_pay_true(self):
        engine = self._make_engine()
        flags = engine.get_flags("FR")
        assert flags.get("apple_pay") is True

    def test_fr_static_flags_mobile_money_false(self):
        engine = self._make_engine()
        flags = engine.get_flags("FR")
        assert flags.get("mobile_money") is False

    def test_db_override_wins_over_static(self):
        """Un override DB active mobile_money pour FR (cas test admin)."""
        mock_flag = MagicMock()
        mock_flag.feature = "mobile_money"
        mock_flag.enabled = True
        engine = self._make_engine(db_flags=[mock_flag])
        flags = engine.get_flags("FR")
        assert flags.get("mobile_money") is True

    def test_cache_hit_returns_cached_value(self):
        import json
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"mobile_money": True, "chat_enabled": True})
        mock_db = MagicMock()
        engine = FeatureFlagEngine(mock_redis, mock_db)
        flags = engine.get_flags("TG")
        assert flags["mobile_money"] is True
        mock_db.query.assert_not_called()  # DB non consultée si cache hit

    def test_unknown_country_uses_default_flags(self):
        engine = self._make_engine(db_country=False)
        flags = engine.get_flags("XX")
        assert "chat_enabled" in flags


# ═══════════════════════════════════════════════════════════════════════════
# 5. test_kyc_provider_selection — bon provider par pays
# ═══════════════════════════════════════════════════════════════════════════

class TestKycProviderSelection:

    def _make_cre(self) -> CountryEngineService:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        return CountryEngineService(mock_redis)

    def test_tg_kyc_is_smile_identity(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("TG") == "smile_identity"

    def test_sn_kyc_is_smile_identity(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("SN") == "smile_identity"

    def test_gh_kyc_is_smile_identity(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("GH") == "smile_identity"

    def test_fr_kyc_is_veriff(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("FR") == "veriff"

    def test_be_kyc_is_veriff(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("BE") == "veriff"

    def test_us_kyc_is_veriff(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("US") == "veriff"

    def test_unknown_country_kyc_is_manual(self):
        cre = self._make_cre()
        assert cre.resolve_kyc_provider("XX") == "manual"

    def test_sms_gateway_tg_is_africas_talking(self):
        cre = self._make_cre()
        assert cre.resolve_sms_gateway("TG") == "africas_talking"

    def test_sms_gateway_fr_is_brevo_smtp(self):
        cre = self._make_cre()
        assert cre.resolve_sms_gateway("FR") == "brevo_smtp"

    def test_gh_flutterwave_route(self):
        route = PaymentRouterService.route_payment("GH", 50, "GHS")
        assert route.provider == "flutterwave"
        assert route.method == "mobile_money"
        assert route.currency == "GHS"

    def test_ng_flutterwave_route(self):
        route = PaymentRouterService.route_payment("NG", 5000, "NGN")
        assert route.provider == "flutterwave"
        assert route.currency == "NGN"

    def test_unknown_country_fallback_stripe(self):
        route = PaymentRouterService.route_payment("XX", 100, "USD")
        assert route.provider == "stripe"
        assert route.region == "INTL"
        assert route.apple_pay_enabled is True  # safe fallback complet


# ═══════════════════════════════════════════════════════════════════════════
# 6. CountryEngineService — détection depuis requête (mock Request)
# ═══════════════════════════════════════════════════════════════════════════

class TestCountryDetection:

    def _make_cre(self) -> CountryEngineService:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        return CountryEngineService(mock_redis)

    def _mock_request(self, header: str | None = None, ip: str = "127.0.0.1") -> MagicMock:
        req = MagicMock()
        req.headers.get.return_value = header or ""
        req.client.host = ip
        return req

    def test_header_override_wins(self):
        cre = self._make_cre()
        req = self._mock_request(header="TG")
        assert cre.detect_country_from_request(req) == "TG"

    def test_header_case_insensitive(self):
        cre = self._make_cre()
        req = self._mock_request(header="tg")
        assert cre.detect_country_from_request(req) == "TG"

    def test_invalid_header_falls_to_ip(self):
        cre = self._make_cre()
        req = self._mock_request(header="TOOLONG", ip="127.0.0.1")
        # IP privée → fallback FR
        assert cre.detect_country_from_request(req) == "FR"

    def test_private_ip_falls_back_to_fr(self):
        cre = self._make_cre()
        req = self._mock_request(ip="192.168.1.1")
        assert cre.detect_country_from_request(req) == "FR"

    def test_cache_warmed_covers_all_registry(self):
        mock_redis = MagicMock()
        mock_redis.setex.return_value = True
        cre = CountryEngineService(mock_redis)
        loaded = cre.warm_cache()
        assert "TG" in loaded
        assert "FR" in loaded
        assert "GH" in loaded
        assert "DEFAULT" in loaded
