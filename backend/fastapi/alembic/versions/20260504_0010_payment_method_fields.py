"""payment_methods — add provider, phone_number, country_code, nickname, created_at

Revision ID: 20260504_0010
Revises: 20260504_0009
Create Date: 2026-05-04
"""

from alembic import op

revision = "20260504_0010"
down_revision = "20260504_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS provider VARCHAR(64)")
    op.execute("ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32)")
    op.execute("ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS country_code VARCHAR(4)")
    op.execute("ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS nickname VARCHAR(64)")
    op.execute("ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
    # Migrer les anciens ids string vers uuid format si besoin
    op.execute(
        "UPDATE payment_methods SET id = gen_random_uuid()::text WHERE id NOT LIKE '________-____-____-____-____________'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE payment_methods DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE payment_methods DROP COLUMN IF EXISTS nickname")
    op.execute("ALTER TABLE payment_methods DROP COLUMN IF EXISTS country_code")
    op.execute("ALTER TABLE payment_methods DROP COLUMN IF EXISTS phone_number")
    op.execute("ALTER TABLE payment_methods DROP COLUMN IF EXISTS provider")
