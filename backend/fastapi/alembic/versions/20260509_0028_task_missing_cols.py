"""tasks: add missing columns (completion_percent, negotiation fields)

These columns exist in the SQLAlchemy model but were never migrated to DB,
causing a 500 on all task queries in production.

Revision ID: 20260509_0028
Revises: 20260509_0027
Create Date: 2026-05-09
"""
from alembic import op

revision = "20260509_0028"
down_revision = "20260509_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS completion_percent INTEGER NOT NULL DEFAULT 100
    """)
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS negotiation_status VARCHAR(16) NOT NULL DEFAULT 'none'
    """)
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS negotiated_price NUMERIC(20, 6)
    """)
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS negotiated_by VARCHAR(36)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS completion_percent")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS negotiation_status")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS negotiated_price")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS negotiated_by")
