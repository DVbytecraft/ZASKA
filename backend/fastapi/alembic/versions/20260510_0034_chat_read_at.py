"""chat_messages: add read_at for message read receipts

Revision ID: 20260510_0034
Revises: 20260510_0033
Create Date: 2026-05-10
"""

revision = "20260510_0034"
down_revision = "20260510_0033"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    # read_at: NULL = not yet read by recipient; timestamp = when it was read.
    # Allows the sender to display a "read" double-checkmark indicator.
    op.add_column(
        "chat_messages",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "read_at")
