"""system_events: append-only immutable event ledger (Layer 2 - forensic audit)

Purpose:
  - Immutable audit trail of all critical system events
  - Forensic analysis and incident reconstruction
  - Reconciliation source for financial operations
  - Replay support for debugging
  - Never updated, never deleted

Differs from outbox_events (which tracks delivery status):
  system_events are the permanent historical record.
  outbox_events are ephemeral delivery queue entries.

Revision ID: 20260510_0037
Revises: 20260510_0036
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0037"
down_revision = "20260510_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False,
                  comment="Category: wallet.credit, escrow.released, task.accepted, call.started, auth.login, admin.action…"),
        sa.Column("actor_id", sa.String(36), nullable=True,
                  comment="User or system process that triggered the event"),
        sa.Column("actor_type", sa.String(16), nullable=False, server_default="user",
                  comment="user | system | admin | worker | webhook"),
        sa.Column("aggregate_id", sa.String(36), nullable=False,
                  comment="Primary entity affected: task_id, escrow_id, wallet_id, call_id"),
        sa.Column("aggregate_type", sa.String(32), nullable=False,
                  comment="task | escrow | wallet | transaction | call | user | payout"),
        sa.Column("payload", sa.Text, nullable=False,
                  comment="Full JSON context — amounts, references, old/new state, IP, user-agent"),
        sa.Column("request_id", sa.String(64), nullable=True,
                  comment="HTTP request ID for distributed tracing correlation"),
        sa.Column("correlation_id", sa.String(64), nullable=True,
                  comment="Business flow correlation (e.g. escrow_id links release + credit events)"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()"),
                  comment="Immutable — set once at insert, never updated"),
    )

    # Partition-friendly index for time-range queries (reconciliation jobs)
    op.create_index("ix_system_events_created_at", "system_events", ["created_at"])
    # Fast lookup by aggregate (all events for a specific task / escrow / wallet)
    op.create_index("ix_system_events_aggregate", "system_events", ["aggregate_type", "aggregate_id", "created_at"])
    # Correlation ID lookup (chain all events in a business flow)
    op.create_index("ix_system_events_correlation", "system_events", ["correlation_id"])
    # Request tracing
    op.create_index("ix_system_events_request", "system_events", ["request_id"])
    # Event type queries (e.g. all wallet.credit events for reconciliation)
    op.create_index("ix_system_events_type", "system_events", ["event_type", "created_at"])

    # Prevent accidental UPDATEs at DB level (append-only guarantee)
    op.execute(
        """
        CREATE RULE system_events_no_update AS ON UPDATE TO system_events DO INSTEAD NOTHING
        """
    )
    op.execute(
        """
        CREATE RULE system_events_no_delete AS ON DELETE TO system_events DO INSTEAD NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP RULE IF EXISTS system_events_no_delete ON system_events")
    op.execute("DROP RULE IF EXISTS system_events_no_update ON system_events")
    op.drop_index("ix_system_events_type", table_name="system_events")
    op.drop_index("ix_system_events_request", table_name="system_events")
    op.drop_index("ix_system_events_correlation", table_name="system_events")
    op.drop_index("ix_system_events_aggregate", table_name="system_events")
    op.drop_index("ix_system_events_created_at", table_name="system_events")
    op.drop_table("system_events")
