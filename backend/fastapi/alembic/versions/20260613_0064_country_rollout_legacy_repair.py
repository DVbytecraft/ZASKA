"""repair legacy country rollout activation defaults

Revision ID: 20260613_0064
Revises: 20260608_0063
Create Date: 2026-06-13
"""

from alembic import op


revision = "20260613_0064"
down_revision = "20260608_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE countries
        SET
            is_active = TRUE,
            signup_enabled = TRUE,
            launch_status = 'ACTIVE'
        WHERE
            iso_code IN ('TG', 'BJ', 'GH', 'NG', 'CI', 'SN', 'EE', 'FR', 'ES')
            AND is_active = FALSE
            AND signup_enabled = TRUE
            AND launch_status = 'PLANNED'
            AND (
                display_name_en IS NULL
                OR display_name_fr IS NULL
                OR currency_code IS NULL
                OR payment_providers_json IS NULL
            )
        """
    )


def downgrade() -> None:
    pass
