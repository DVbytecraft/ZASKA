"""country rollout, welcome email, tasker security foundations

Revision ID: 20260606_0040
Revises: 20260531_0039
Create Date: 2026-06-06
"""

from alembic import op


revision = "20260606_0040"
down_revision = "20260531_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS iso_code VARCHAR(2)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS display_name_en VARCHAR(120)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS display_name_fr VARCHAR(120)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS phone_prefix VARCHAR(16)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS currency_code VARCHAR(8)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS currency_symbol VARCHAR(8)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS timezone VARCHAR(64)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS payment_providers_json TEXT")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS tax_rate NUMERIC(8,4) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS aml_reporting_threshold NUMERIC(20,6) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS aml_authority_name VARCHAR(128)")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS signup_enabled BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS launch_status VARCHAR(16) NOT NULL DEFAULT 'PLANNED'")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS mobile_money_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS stripe_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS fedapay_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS flutterwave_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS paystack_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS food_delivery_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS food_delivery_escrow_minutes INTEGER NOT NULL DEFAULT 20")
    op.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS restaurant_payment_split BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_countries_iso_code ON countries(iso_code)")

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tasker_security_verified BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS biometric_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS criminal_record_status VARCHAR(24) NOT NULL DEFAULT 'pending'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS welcome_email_sent_at TIMESTAMPTZ")

    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS id_document_back_url VARCHAR(500)")
    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS biometric_selfie_url VARCHAR(500)")
    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS criminal_record_url VARCHAR(500)")
    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS criminal_record_status VARCHAR(24) NOT NULL DEFAULT 'pending'")

    op.execute("""
        UPDATE countries
        SET iso_code = CASE UPPER(name)
            WHEN 'TOGO' THEN 'TG'
            WHEN 'BENIN' THEN 'BJ'
            WHEN 'GHANA' THEN 'GH'
            WHEN 'ESTONIA' THEN 'EE'
            WHEN 'PORTUGAL' THEN 'PT'
            WHEN 'FRANCE' THEN 'FR'
            WHEN 'SPAIN' THEN 'ES'
            WHEN 'CÔTE D''IVOIRE' THEN 'CI'
            WHEN 'COTE D''IVOIRE' THEN 'CI'
            WHEN 'IVORY COAST' THEN 'CI'
            WHEN 'SENEGAL' THEN 'SN'
            WHEN 'NIGERIA' THEN 'NG'
            WHEN 'UNITED STATES' THEN 'US'
            ELSE CASE WHEN LENGTH(name) = 2 THEN UPPER(name) ELSE iso_code END
        END
        WHERE iso_code IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_countries_iso_code")
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS criminal_record_status")
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS criminal_record_url")
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS biometric_selfie_url")
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS id_document_back_url")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS welcome_email_sent_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS criminal_record_status")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS biometric_enabled")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS tasker_security_verified")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS restaurant_payment_split")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS food_delivery_escrow_minutes")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS food_delivery_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS paystack_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS flutterwave_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS fedapay_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS stripe_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS mobile_money_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS launch_status")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS signup_enabled")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS is_active")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS aml_authority_name")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS aml_reporting_threshold")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS tax_rate")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS payment_providers_json")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS timezone")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS currency_symbol")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS currency_code")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS phone_prefix")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS display_name_fr")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS display_name_en")
    op.execute("ALTER TABLE countries DROP COLUMN IF EXISTS iso_code")
