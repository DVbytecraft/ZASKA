"""KYC expiration: add approved_at and expires_at to kyc_submissions

Revision ID: 20260508_0016
Revises: 20260507_0015
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = "20260508_0016"
down_revision = "20260507_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kyc_submissions",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kyc_submissions",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Back-fill existing approved submissions with a 1-year window from reviewed_at.
    # Submissions without reviewed_at keep NULL (they are pending/rejected, not expired).
    op.execute(
        """
        UPDATE kyc_submissions
        SET
            approved_at = reviewed_at,
            expires_at  = reviewed_at + INTERVAL '365 days'
        WHERE status = 'approved'
          AND reviewed_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("kyc_submissions", "expires_at")
    op.drop_column("kyc_submissions", "approved_at")
