"""outbox_events: transactional outbox for reliable async side-effects

Layer 2.5 of the hardening overlay.

Any critical mutation (escrow release, payout, notification) writes an outbox event
in the SAME DB transaction as the business state change.  A background processor
then delivers the side-effect (Redis publish, push, retry).

This makes side-effects:
  - Exactly-once (idempotency_key)
  - Retry-safe (status + retry_count)
  - Crash-safe (survives API restart between write and delivery)
  - Observable (full audit trail in DB)

Revision ID: 0036
Revises: 0035
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0036"
down_revision = "20260510_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False,
                  comment="ID of the related entity (task_id, escrow_id, call_id…)"),
        sa.Column("aggregate_type", sa.String(32), nullable=False,
                  comment="Entity type: task, escrow, wallet, call, notification"),
        sa.Column("payload", sa.Text, nullable=False,
                  comment="JSON payload for the side-effect processor"),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True,
                  comment="Globally unique key — prevents duplicate delivery"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending",
                  comment="pending | processing | delivered | failed | dead_letter"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime, nullable=True,
                  comment="Null = ready immediately; set by exponential backoff"),
        sa.Column("error", sa.Text, nullable=True,
                  comment="Last error message for debugging"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("delivered_at", sa.DateTime, nullable=True),
    )

    # Index for the processor: pick up pending events in creation order
    op.create_index(
        "ix_outbox_events_status_next",
        "outbox_events",
        ["status", "next_attempt_at"],
    )
    # Index for lookup by aggregate (for debugging / admin)
    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_next", table_name="outbox_events")
    op.drop_table("outbox_events")
