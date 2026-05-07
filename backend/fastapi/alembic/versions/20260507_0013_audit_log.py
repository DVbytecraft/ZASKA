"""financial_audit_logs table

Revision ID: 20260507_0013
Revises: 20260506_0012
Create Date: 2026-05-07
"""

from alembic import op

revision = "20260507_0013"
down_revision = "20260506_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS financial_audit_logs (
            id              VARCHAR(36)     PRIMARY KEY,
            action          VARCHAR(64)     NOT NULL,
            user_id         VARCHAR(36)     NOT NULL,
            payment_id      VARCHAR(255)    NOT NULL DEFAULT '',
            transaction_id  VARCHAR(255)    NOT NULL DEFAULT '',
            amount          NUMERIC(20, 8)  NOT NULL,
            currency        VARCHAR(10)     NOT NULL,
            provider        VARCHAR(64)     NOT NULL DEFAULT '',
            status          VARCHAR(32)     NOT NULL,
            state_before    VARCHAR(255)    NOT NULL DEFAULT '',
            state_after     VARCHAR(255)    NOT NULL DEFAULT '',
            idempotency_key VARCHAR(255)    NOT NULL DEFAULT '',
            country_code    VARCHAR(10)     NOT NULL DEFAULT '',
            request_id      VARCHAR(64)     NOT NULL DEFAULT '',
            extra           TEXT,
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_user_id ON financial_audit_logs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_action  ON financial_audit_logs(action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_created ON financial_audit_logs(created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS financial_audit_logs")
