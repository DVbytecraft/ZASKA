import pytest

from app.core.config import Settings


TEST_DB_URL = "sqlite:///./test_settings_otp.db"
TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdef0123456789"


def test_production_rejects_mock_otp_provider():
    with pytest.raises(ValueError, match="OTP mock provider"):
        Settings(
            env="production",
            database_url=TEST_DB_URL,
            jwt_secret=TEST_JWT_SECRET,
            payment_mode="production",
            stripe_secret_key="sk_live_x",
            stripe_webhook_secret="whsec_x",
            fedapay_api_key="sk_live_feda",
            fedapay_webhook_secret="whsec_feda",
            otp_provider="mock",
        )


def test_development_defaults_allow_mock_otp_provider():
    settings = Settings(
        env="development",
        database_url=TEST_DB_URL,
        jwt_secret=TEST_JWT_SECRET,
    )
    assert settings.otp_provider == "mock"
    assert settings.is_production is False
