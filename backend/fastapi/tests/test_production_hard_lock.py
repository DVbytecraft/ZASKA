import pytest

from app.core.config import Settings


TEST_DB_URL = "sqlite:///./test_production_hard_lock.db"
TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdef0123456789"


def test_production_requires_provider_keys():
    with pytest.raises(ValueError, match="provider key"):
        Settings(
            database_url=TEST_DB_URL,
            jwt_secret=TEST_JWT_SECRET,
            payment_mode="production",
            stripe_secret_key="",
            fedapay_api_key="",
            flutterwave_secret_key="",
        )


def test_production_requires_webhook_secret():
    with pytest.raises(ValueError, match="webhook"):
        Settings(
            database_url=TEST_DB_URL,
            jwt_secret=TEST_JWT_SECRET,
            payment_mode="production",
            stripe_secret_key="sk_live_x",
            fedapay_api_key="sk_live_feda",
            stripe_webhook_secret="",
            fedapay_webhook_secret="",
            flutterwave_hash="",
        )


def test_production_with_requirements_passes():
    settings = Settings(
        env="production",
        database_url=TEST_DB_URL,
        jwt_secret=TEST_JWT_SECRET,
        payment_mode="production",
        stripe_secret_key="sk_live_x",
        stripe_webhook_secret="whsec_x",
        fedapay_api_key="sk_live_feda",
        fedapay_webhook_secret="whsec_feda",
        payment_webhook_base_url="https://api.zaska.app",
        payment_redirect_url="https://app.zaska.app/payment/success",
        otp_provider="smtp",
        brevo_api_key="xkeysib-prod",
        email_from_address="noreply@zaska.app",
        kyc_provider_enabled=True,
        otp_provider_enabled=True,
    )
    assert settings.payment_mode == "production"
    assert settings.is_production is True
