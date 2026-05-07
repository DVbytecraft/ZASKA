"""Config-level checks (no running server required)."""

from app.core.config import Settings


def test_production_settings_never_expose_otp_payload():
    s = Settings(env="production")
    assert s.expose_register_otp is False
    assert s.is_production is True


def test_development_defaults_allow_otp_in_register_response():
    s = Settings(env="development")
    assert s.expose_register_otp is True
