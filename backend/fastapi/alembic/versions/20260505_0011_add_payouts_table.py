"""add payouts table with payout lifecycle states

Revision ID: 20260505_0011
Revises: 20260504_0010
Create Date: 2026-05-05
"""

from alembic import op

revision = "20260505_0011"
down_revision = "20260504_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id              VARCHAR(36)    PRIMARY KEY,
            user_id         VARCHAR(36)    NOT NULL REFERENCES users(id),
            transaction_id  VARCHAR(36)    REFERENCES transactions(id),
            amount          NUMERIC(20,6)  NOT NULL,
            currency        VARCHAR(8)     NOT NULL,
            provider        VARCHAR(32)    NOT NULL,
            phone_number    VARCHAR(32)    NOT NULL,
            country_code    VARCHAR(4)     NOT NULL,
            reference       VARCHAR(120)   NOT NULL,
            status          VARCHAR(16)    NOT NULL DEFAULT 'pending',
            provider_tx_id  VARCHAR(120),
            failure_reason  TEXT,
            retry_count     INTEGER        NOT NULL DEFAULT 0,
            admin_notes     TEXT,
            created_at      TIMESTAMP      NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP      NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_user_id      ON payouts (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_transaction_id ON payouts (transaction_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_reference    ON payouts (reference)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_provider_tx  ON payouts (provider_tx_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_status       ON payouts (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payouts")
