"""virtual_cards table

Revision ID: 20260508_0021
Revises: 20260508_0020
Create Date: 2026-05-08
"""

from alembic import op

revision = "20260508_0021"
down_revision = "20260508_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS virtual_cards (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            card_type VARCHAR(12) NOT NULL,
            card_number_masked VARCHAR(24) NOT NULL,
            card_number_hash VARCHAR(64) NOT NULL,
            expiry_month INTEGER NOT NULL,
            expiry_year INTEGER NOT NULL,
            cvv_hash VARCHAR(64) NOT NULL,
            status VARCHAR(12) NOT NULL DEFAULT 'active',
            wallet_currency VARCHAR(8) NOT NULL DEFAULT 'USD',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_virtual_cards_user_id ON virtual_cards(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_virtual_cards_user_id")
    op.execute("DROP TABLE IF EXISTS virtual_cards")
