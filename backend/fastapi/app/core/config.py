from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="backend/fastapi/.env", extra="ignore")

    env: str = "development"
    app_name: str = "ZASKA API"
    app_host: str = "0.0.0.0"
    app_port: int = 6969

    database_url: str = ""
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7
    otp_expire_minutes: int = 5
    ws_ticket_ttl_seconds: int = 60

    cors_allowed_origins: str = "http://localhost:3010,http://localhost:5173,http://localhost:5174"
    api_prefix: str = "/api"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    max_upload_bytes: int = 5 * 1024 * 1024

    rate_limit_max_requests: int = 180
    rate_limit_window_seconds: int = 60

    # ── Mode paiement ────────────────────────────────────────────────────
    # dev        : MockProvider — aucun appel externe, simulation locale
    # sandbox    : providers réels avec clés test (sk_test_, sk_sandbox_)
    # production : providers réels avec clés live
    payment_mode: Literal["mock", "sandbox", "production"] = "mock"
    real_money_enabled: bool = False
    payments_disabled: bool = False

    # ── Stripe ────────────────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # ── FedaPay ──────────────────────────────────────────────────────────
    fedapay_api_key: str = ""
    fedapay_env: str = "sandbox"           # sandbox | live
    fedapay_webhook_secret: str = ""

    # ── Flutterwave ───────────────────────────────────────────────────────
    flutterwave_secret_key: str = ""
    flutterwave_hash: str = ""

    # ── Paystack ──────────────────────────────────────────────────────────
    paystack_secret_key: str = ""
    paystack_webhook_secret: str = ""

    # ── Paiements — URLs ─────────────────────────────────────────────────
    payment_webhook_base_url: str = "http://localhost:6969"
    payment_redirect_url: str = "http://localhost:3010/payment/success"
    otp_provider_enabled: bool = True
    kyc_provider_enabled: bool = True
    otp_provider: Literal["mock", "smtp"] = "mock"

    # ── FX — taux fixes configurables ─────────────────────────────────────
    # 1 USD = fx_usd_to_xof XOF  (BCEAO officiel ~655, zone pratique ~600-650)
    fx_usd_to_xof: float = 620.0
    # Frais de conversion en basis points (50 bps = 0.5 %)
    fx_fee_bps: int = 50
    # Hard cap per single FX transaction (USD-equivalent)
    fx_max_per_tx_usd: float = 10_000.0
    # Daily FX cap per user (USD-equivalent)
    fx_max_daily_usd: float = 50_000.0

    # ── Transaction limits (USD-equivalent per day per user) ─────────────
    max_withdrawal_per_day_usd: float = 5_000.0
    max_deposit_per_day_usd: float = 50_000.0

    # ── Fraud detection ───────────────────────────────────────────────────
    # Block payouts after N consecutive failures within 24 h
    payout_fail_block_threshold: int = 3
    # Minimum gap between a confirmed deposit and a withdrawal (minutes)
    rapid_cycle_window_minutes: int = 10

    # ── FX exposure control ───────────────────────────────────────────────
    # Max cumulative USD-equivalent exposure per direction (to_xof | from_xof)
    fx_exposure_limit_usd: float = 100_000.0

    # ── Payout monitoring ─────────────────────────────────────────────────
    # Minutes before a 'processing' payout is treated as stale and polled
    payout_monitor_stale_minutes: int = 15
    # Maximum automatic retry attempts for failed payouts (exponential backoff)
    payout_max_retries: int = 3

    # ── Admin ─────────────────────────────────────────────────────────────
    admin_role: str = "admin"
    # One-time secret to promote first admin via POST /api/admin/bootstrap
    # Set in env, call the endpoint once, then remove the variable.
    admin_bootstrap_secret: str = ""

    # ── Brevo HTTP API (replaces SMTP relay — no IP allowlist required) ──
    brevo_api_key: str = ""
    email_from_address: str = ""
    email_from_name: str = "ZASKA"

    sentry_dsn: str = ""

    # ── PostgreSQL backups ────────────────────────────────────────────────
    backup_dir: str = "/app/backups"
    backup_keep_days: int = 7

    # ── FCM push notifications ────────────────────────────────────────────
    # Path to Firebase service account JSON file (leave empty to disable push)
    fcm_service_account_path: str = ""
    # FCM project ID (extracted from service account if empty)
    fcm_project_id: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_urls(cls, values: dict) -> dict:
        # Render provides postgresql:// — psycopg3 requires postgresql+psycopg://
        url = values.get("database_url", "")
        if isinstance(url, str) and url.startswith("postgresql://"):
            values["database_url"] = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return values

    @model_validator(mode="after")
    def _validate_payment_mode_and_keys(self):
        mode = str(self.payment_mode).strip().lower()
        if mode == "sandbox" and self.stripe_secret_key and not self.stripe_secret_key.startswith("sk_test_"):
            raise ValueError("Sandbox mode requires STRIPE_SECRET_KEY starting with sk_test_")
        if mode == "production" and self.stripe_secret_key and not self.stripe_secret_key.startswith("sk_live_"):
            raise ValueError("Production mode requires STRIPE_SECRET_KEY starting with sk_live_")

        if not self.database_url.strip():
            raise ValueError("DATABASE_URL is required")

        env_norm = str(self.env).strip().lower()
        if env_norm != "development" and mode == "mock":
            raise ValueError("Mock payment mode is allowed only in development")

        if not self.jwt_secret.strip():
            raise ValueError("JWT_SECRET is required")

        if env_norm == "production" and mode != "production":
            raise ValueError("ENV=production requires PAYMENT_MODE=production")

        if mode == "production":
            has_live_provider = bool(
                self.stripe_secret_key.strip()
                or self.fedapay_api_key.strip()
                or self.flutterwave_secret_key.strip()
                or self.paystack_secret_key.strip()
            )
            if not has_live_provider:
                raise ValueError("Production mode requires at least one live provider key (Stripe/FedaPay/Flutterwave/Paystack)")
            if not self.stripe_webhook_secret and not self.fedapay_webhook_secret and not self.flutterwave_hash:
                raise ValueError("Production mode requires webhook secret/hash")
            if not self.kyc_provider_enabled:
                raise ValueError("Production mode requires KYC provider enabled")
            if not self.otp_provider_enabled:
                raise ValueError("Production mode requires OTP provider enabled")
            if not self.stripe_secret_key.strip():
                raise ValueError("Production mode requires STRIPE_SECRET_KEY for EU countries")
            if not (self.fedapay_api_key.strip() or self.flutterwave_secret_key.strip()):
                raise ValueError("Production mode requires FEDAPAY_API_KEY or FLUTTERWAVE_SECRET_KEY for Africa routes")

        if self.otp_provider == "smtp":
            if not self.brevo_api_key.strip():
                raise ValueError("OTP smtp provider requires BREVO_API_KEY")
            if not self.email_from_address.strip():
                raise ValueError("OTP smtp provider requires EMAIL_FROM_ADDRESS")

        if env_norm != "development" and self.otp_provider == "mock":
            raise ValueError("OTP mock provider is allowed only in development")

        # Reject localhost/ngrok URLs in production — enforce a real domain
        _DEV_URL_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "ngrok.io", "ngrok-free.app")
        if env_norm == "production":
            for field_name, url_val in (
                ("payment_webhook_base_url", self.payment_webhook_base_url),
                ("payment_redirect_url", self.payment_redirect_url),
            ):
                if any(m in url_val.lower() for m in _DEV_URL_MARKERS):
                    raise ValueError(
                        f"{field_name} contains a dev/ngrok URL in production env: {url_val!r}. "
                        "Set a real HTTPS domain (e.g. https://api.zaska.app)."
                    )

        return self

    @property
    def is_production(self) -> bool:
        return str(self.env).strip().lower() == "production"


settings = Settings()
