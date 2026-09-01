"""enable the current EU registration countries

Revision ID: 20260901_0068
Revises: 20260616_0067
Create Date: 2026-09-01
"""

from alembic import op


revision = "20260901_0068"
down_revision = "20260616_0067"
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
        WHERE iso_code IN ('DE', 'EE', 'ES', 'LT', 'LV')
        """
    )


def downgrade() -> None:
    pass
