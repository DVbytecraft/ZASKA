"""tasks: idempotency_key for double-submit prevention

Revision ID: 20260509_0025
Revises: 20260509_0024
Create Date: 2026-05-09
"""

from alembic import op

revision = "20260509_0025"
down_revision = "20260509_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_tasks_idempotency_key")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS idempotency_key")
