"""disputes and reconciliation_reports tables

Revision ID: 20260506_0012
Revises: 20260505_0011
Create Date: 2026-05-06
"""

from alembic import op

revision = "20260506_0012"
down_revision = "20260505_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS disputes (
            id            VARCHAR(36)  PRIMARY KEY,
            user_id       VARCHAR(36)  NOT NULL REFERENCES users(id),
            transaction_id VARCHAR(36) REFERENCES transactions(id),
            payout_id     VARCHAR(36)  REFERENCES payouts(id),
            dispute_type  VARCHAR(24)  NOT NULL,
            reason        TEXT         NOT NULL,
            status        VARCHAR(16)  NOT NULL DEFAULT 'open',
            admin_notes   TEXT,
            resolution_tx_id VARCHAR(36) REFERENCES transactions(id),
            created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMP    NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_disputes_user_id       ON disputes(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_disputes_transaction_id ON disputes(transaction_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_disputes_payout_id      ON disputes(payout_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_disputes_status         ON disputes(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_reports (
            id                  VARCHAR(36) PRIMARY KEY,
            run_at              TIMESTAMP   NOT NULL DEFAULT NOW(),
            country_code        VARCHAR(4)  NOT NULL DEFAULT 'ALL',
            matched_count       INTEGER     NOT NULL DEFAULT 0,
            missing_count       INTEGER     NOT NULL DEFAULT 0,
            inconsistent_count  INTEGER     NOT NULL DEFAULT 0,
            repaired_count      INTEGER     NOT NULL DEFAULT 0,
            report_json         TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_recon_reports_run_at ON reconciliation_reports(run_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reconciliation_reports")
    op.execute("DROP TABLE IF EXISTS disputes")
