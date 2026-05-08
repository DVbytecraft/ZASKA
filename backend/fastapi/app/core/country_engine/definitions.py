"""
Registre statique des configurations pays du Country Runtime Engine.
"""

from __future__ import annotations

from pydantic import BaseModel

# ─────────────────────────────────────── zones géographiques ───────────────

EU_ZONE: frozenset[str] = frozenset(
    {
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
        "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
        "NL", "PL", "PT", "RO", "SE", "SI", "SK", "CH", "NO", "IS",
    }
)

CFA_ZONE: frozenset[str] = frozenset(
    {"TG", "SN", "CI", "ML", "BF", "NE", "BJ", "GW", "CM", "GA", "CG", "CF", "TD"}
)

FLUTTERWAVE_ZONE: frozenset[str] = frozenset({"GH", "NG", "KE", "ZA", "TZ", "UG", "RW"})


# ─────────────────────────────────────── opérateurs mobile money ───────────

MOBILE_MONEY_OPERATORS: dict[str, list[dict]] = {
    "TG": [
        {"id": "tmoney",       "name": "T-Money",       "color": "#FF6B00", "network": "moov"},
        {"id": "flooz",        "name": "Flooz",          "color": "#0066CC", "network": "togocel"},
    ],
    "CI": [
        {"id": "orange_money", "name": "Orange Money",   "color": "#FF6600", "network": "orange"},
        {"id": "wave",         "name": "Wave",           "color": "#1B75BC", "network": "wave"},
        {"id": "mtn_momo",     "name": "MTN MoMo",       "color": "#FFC107", "network": "mtn"},
        {"id": "moov_money",   "name": "Moov Money",     "color": "#00A0E3", "network": "moov"},
    ],
    "SN": [
        {"id": "orange_money", "name": "Orange Money",   "color": "#FF6600", "network": "orange"},
        {"id": "wave",         "name": "Wave",           "color": "#1B75BC", "network": "wave"},
        {"id": "free_money",   "name": "Free Money",     "color": "#E40000", "network": "free"},
    ],
    "BJ": [
        {"id": "mtn_momo",     "name": "MTN MoMo",       "color": "#FFC107", "network": "mtn"},
        {"id": "moov_money",   "name": "Moov Money",     "color": "#00A0E3", "network": "moov"},
    ],
    "BF": [
        {"id": "orange_money", "name": "Orange Money",   "color": "#FF6600", "network": "orange"},
        {"id": "moov_money",   "name": "Moov Money",     "color": "#00A0E3", "network": "moov"},
    ],
    "ML": [
        {"id": "orange_money", "name": "Orange Money",   "color": "#FF6600", "network": "orange"},
        {"id": "moov_money",   "name": "Moov Money",     "color": "#00A0E3", "network": "moov"},
    ],
    "NE": [
        {"id": "orange_money", "name": "Orange Money",   "color": "#FF6600", "network": "orange"},
        {"id": "moov_money",   "name": "Moov Money",     "color": "#00A0E3", "network": "moov"},
    ],
    "CM": [
        {"id": "orange_money", "name": "Orange Money",   "color": "#FF6600", "network": "orange"},
        {"id": "mtn_momo",     "name": "MTN MoMo",       "color": "#FFC107", "network": "mtn"},
    ],
    "GH": [
        {"id": "mtn_momo",     "name": "MTN MoMo",       "color": "#FFC107", "network": "mtn"},
        {"id": "airteltigo",   "name": "AirtelTigo Money","color": "#E40000", "network": "airtel"},
        {"id": "vodafone_cash","name": "Vodafone Cash",  "color": "#E60000", "network": "vodafone"},
    ],
    "NG": [
        {"id": "mtn_momo",     "name": "MTN MoMo",       "color": "#FFC107", "network": "mtn"},
        {"id": "airtel_money", "name": "Airtel Money",   "color": "#E40000", "network": "airtel"},
    ],
    "KE": [
        {"id": "mpesa",        "name": "M-Pesa",         "color": "#4CAF50", "network": "safaricom"},
        {"id": "airtel_money", "name": "Airtel Money",   "color": "#E40000", "network": "airtel"},
    ],
}

# Données de test par pays (mode dev/sandbox uniquement)
TEST_PAYMENT_METHODS: dict[str, list[dict]] = {
    "TG": [
        {"provider": "tmoney",       "phone": "+22890000001", "nickname": "T-Money TEST"},
        {"provider": "flooz",        "phone": "+22891000001", "nickname": "Flooz TEST"},
    ],
    "CI": [
        {"provider": "orange_money", "phone": "+22507000001", "nickname": "Orange Money TEST"},
        {"provider": "wave",         "phone": "+22507000002", "nickname": "Wave TEST"},
    ],
    "SN": [
        {"provider": "orange_money", "phone": "+22177000001", "nickname": "Orange Money TEST"},
        {"provider": "wave",         "phone": "+22177000002", "nickname": "Wave TEST"},
    ],
    "GH": [
        {"provider": "mtn_momo",     "phone": "+23324000001", "nickname": "MTN MoMo TEST"},
    ],
    "NG": [
        {"provider": "mtn_momo",     "phone": "+23480000001", "nickname": "MTN MoMo TEST"},
    ],
    "KE": [
        {"provider": "mpesa",        "phone": "+25470000001", "nickname": "M-Pesa TEST"},
    ],
    "DEFAULT": [
        {"provider": "tmoney",       "phone": "+22890000001", "nickname": "T-Money TEST"},
    ],
}


def get_operators(country_code: str) -> list[dict]:
    return MOBILE_MONEY_OPERATORS.get(country_code.upper(), [])


def get_test_methods(country_code: str) -> list[dict]:
    return TEST_PAYMENT_METHODS.get(country_code.upper(), TEST_PAYMENT_METHODS["DEFAULT"])


# ─────────────────────────────────────── modèle ────────────────────────────

class CountryConfig(BaseModel, frozen=True):
    country_code: str
    currency: str
    payment_methods: list[str]
    payment_providers: list[str]
    kyc_provider: str
    sms_gateway: str
    mobile_money_enabled: bool
    stripe_enabled: bool
    escrow_enabled: bool
    payout_delay_minutes: int
    feature_flags_defaults: dict[str, bool]
    timezone: str
    emergency_numbers: dict[str, str]


_BASE_FLAGS: dict[str, bool] = {
    "chat_enabled": True,
    "task_matching": True,
    "notifications": True,
    "escrow": False,
    "mobile_money": False,
    "apple_pay": False,
    "google_pay": False,
    "wallet": False,
    "kyc_required": False,
    "multi_currency": False,
    "real_money_enabled": False,
}

_CFA_CONFIG = dict(
    payment_methods=["mobile_money"],
    payment_providers=["fedapay"],
    kyc_provider="smile_identity",
    sms_gateway="africas_talking",
    mobile_money_enabled=True,
    stripe_enabled=False,
    escrow_enabled=True,
    payout_delay_minutes=1440,
    feature_flags_defaults={**_BASE_FLAGS, "mobile_money": True, "escrow": True, "wallet": True},
)

COUNTRY_REGISTRY: dict[str, CountryConfig] = {

    "TG": CountryConfig(
        country_code="TG", currency="XOF",
        timezone="Africa/Lome",
        emergency_numbers={"police": "117", "medical": "8200", "fire": "118"},
        **_CFA_CONFIG,
    ),
    "SN": CountryConfig(
        country_code="SN", currency="XOF",
        timezone="Africa/Dakar",
        emergency_numbers={"police": "17", "medical": "15", "fire": "18"},
        **_CFA_CONFIG,
    ),
    "CI": CountryConfig(
        country_code="CI", currency="XOF",
        timezone="Africa/Abidjan",
        emergency_numbers={"police": "111", "medical": "185", "fire": "180"},
        **_CFA_CONFIG,
    ),
    "BJ": CountryConfig(
        country_code="BJ", currency="XOF",
        timezone="Africa/Porto-Novo",
        emergency_numbers={"police": "117", "medical": "118", "fire": "118"},
        **_CFA_CONFIG,
    ),
    "BF": CountryConfig(
        country_code="BF", currency="XOF",
        timezone="Africa/Ouagadougou",
        emergency_numbers={"police": "17", "medical": "112", "fire": "18"},
        **_CFA_CONFIG,
    ),
    "ML": CountryConfig(
        country_code="ML", currency="XOF",
        timezone="Africa/Bamako",
        emergency_numbers={"police": "17", "medical": "15", "fire": "18"},
        **_CFA_CONFIG,
    ),
    "NE": CountryConfig(
        country_code="NE", currency="XOF",
        timezone="Africa/Niamey",
        emergency_numbers={"police": "17", "medical": "15", "fire": "18"},
        **_CFA_CONFIG,
    ),
    "CM": CountryConfig(
        country_code="CM", currency="XAF",
        timezone="Africa/Douala",
        emergency_numbers={"police": "117", "medical": "112", "fire": "118"},
        **_CFA_CONFIG,
    ),
    "GH": CountryConfig(
        country_code="GH", currency="GHS",
        payment_methods=["mobile_money", "card"],
        payment_providers=["flutterwave"],
        kyc_provider="smile_identity",
        sms_gateway="termii",
        mobile_money_enabled=True,
        stripe_enabled=False,
        escrow_enabled=True,
        payout_delay_minutes=720,
        feature_flags_defaults={**_BASE_FLAGS, "mobile_money": True, "escrow": True, "wallet": True},
        timezone="Africa/Accra",
        emergency_numbers={"police": "191", "medical": "193", "fire": "192"},
    ),
    "NG": CountryConfig(
        country_code="NG", currency="NGN",
        payment_methods=["mobile_money", "card"],  # MM primary for Africa
        payment_providers=["paystack", "flutterwave"],  # paystack primary; flutterwave fallback
        kyc_provider="smile_identity",
        sms_gateway="termii",
        mobile_money_enabled=True,
        stripe_enabled=False,
        escrow_enabled=True,
        payout_delay_minutes=720,
        feature_flags_defaults={**_BASE_FLAGS, "mobile_money": True, "escrow": True, "wallet": True},
        timezone="Africa/Lagos",
        emergency_numbers={"police": "199", "medical": "199", "fire": "199"},
    ),
    "KE": CountryConfig(
        country_code="KE", currency="KES",
        payment_methods=["mobile_money"],
        payment_providers=["flutterwave"],
        kyc_provider="smile_identity",
        sms_gateway="africas_talking",
        mobile_money_enabled=True,
        stripe_enabled=False,
        escrow_enabled=True,
        payout_delay_minutes=720,
        feature_flags_defaults={**_BASE_FLAGS, "mobile_money": True, "escrow": True, "wallet": True},
        timezone="Africa/Nairobi",
        emergency_numbers={"police": "999", "medical": "999", "fire": "999"},
    ),
    "FR": CountryConfig(
        country_code="FR", currency="EUR",
        payment_methods=["card", "apple_pay", "google_pay"],
        payment_providers=["stripe"],
        kyc_provider="veriff",
        sms_gateway="brevo_smtp",
        mobile_money_enabled=False,
        stripe_enabled=True,
        escrow_enabled=True,
        payout_delay_minutes=4320,
        feature_flags_defaults={**_BASE_FLAGS, "apple_pay": True, "google_pay": True, "escrow": True, "kyc_required": True},
        timezone="Europe/Paris",
        emergency_numbers={"police": "17", "medical": "15", "fire": "18", "europe": "112"},
    ),
    "BE": CountryConfig(
        country_code="BE", currency="EUR",
        payment_methods=["card", "apple_pay", "google_pay"],
        payment_providers=["stripe"],
        kyc_provider="veriff",
        sms_gateway="brevo_smtp",
        mobile_money_enabled=False,
        stripe_enabled=True,
        escrow_enabled=True,
        payout_delay_minutes=4320,
        feature_flags_defaults={**_BASE_FLAGS, "apple_pay": True, "google_pay": True, "escrow": True, "kyc_required": True},
        timezone="Europe/Brussels",
        emergency_numbers={"police": "101", "medical": "100", "fire": "100", "europe": "112"},
    ),
    "US": CountryConfig(
        country_code="US", currency="USD",
        payment_methods=["card", "apple_pay", "google_pay"],
        payment_providers=["stripe"],
        kyc_provider="veriff",
        sms_gateway="brevo_smtp",
        mobile_money_enabled=False,
        stripe_enabled=True,
        escrow_enabled=True,
        payout_delay_minutes=2880,
        feature_flags_defaults={**_BASE_FLAGS, "apple_pay": True, "google_pay": True, "escrow": True},
        timezone="America/New_York",
        emergency_numbers={"emergency": "911"},
    ),
    "DEFAULT": CountryConfig(
        country_code="DEFAULT", currency="EUR",
        payment_methods=["card"],
        payment_providers=["stripe"],
        kyc_provider="manual",
        sms_gateway="brevo_smtp",
        mobile_money_enabled=False,
        stripe_enabled=True,
        escrow_enabled=False,
        payout_delay_minutes=4320,
        feature_flags_defaults={**_BASE_FLAGS, "escrow": False},
        timezone="UTC",
        emergency_numbers={"europe": "112"},
    ),
}


def get_config(country_code: str) -> CountryConfig:
    return COUNTRY_REGISTRY.get(country_code.upper(), COUNTRY_REGISTRY["DEFAULT"])
