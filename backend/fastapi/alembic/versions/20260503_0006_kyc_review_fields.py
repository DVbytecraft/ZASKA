"""kyc_submissions — add reviewed_by, reviewed_at, reviewer note

Revision ID: 20260503_0006
Revises: 20260503_0005
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "20260503_0006"
down_revision = "20260503_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(36)")
    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP")
    op.execute("ALTER TABLE kyc_submissions ADD COLUMN IF NOT EXISTS reviewer_note TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS reviewer_note")
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS reviewed_at")
    op.execute("ALTER TABLE kyc_submissions DROP COLUMN IF EXISTS reviewed_by")
