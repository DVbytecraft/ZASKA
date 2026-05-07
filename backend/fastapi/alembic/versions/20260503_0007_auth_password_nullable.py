"""auth — password_hash nullable pour le nouveau flow d'inscription

Revision ID: 20260503_0007
Revises: 20260503_0006
Create Date: 2026-05-03
"""

from alembic import op

revision = "20260503_0007"
down_revision = "20260503_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")


def downgrade() -> None:
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL")
