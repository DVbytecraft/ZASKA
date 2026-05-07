from app.core.config import Settings


def test_production_requires_provider_keys():
    try:
        Settings(payment_mode="production", stripe_secret_key="", fedapay_api_key="", flutterwave_secret_key="")
        assert False, "should fail"
    except ValueError as exc:
        assert "provider key" in str(exc).lower()


def test_production_requires_webhook_secret():
    try:
        Settings(payment_mode="production", stripe_secret_key="sk_live_x", stripe_webhook_secret="")
        assert False, "should fail"
    except ValueError as exc:
        assert "webhook" in str(exc).lower()


def test_production_with_requirements_passes():
    s = Settings(
        payment_mode="production",
        jwt_secret="super-strong-jwt-secret",
        stripe_secret_key="sk_live_x",
        stripe_webhook_secret="whsec_x",
        fedapay_api_key="sk_live_feda",
        fedapay_webhook_secret="whsec_feda",
        otp_provider="smtp",
        smtp_host="smtp-relay.brevo.com",
        smtp_login="apikey",
        smtp_password="xkeysib-prod",
        smtp_from_email="noreply@zaska.app",
        kyc_provider_enabled=True,
        otp_provider_enabled=True,
    )
    assert s.payment_mode == "production"
