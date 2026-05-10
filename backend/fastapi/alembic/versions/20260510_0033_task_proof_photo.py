"""tasks: add proof_photo_url for completion evidence

Revision ID: 20260510_0033
Revises: 20260510_0032
Create Date: 2026-05-10
"""

revision = "20260510_0033"
down_revision = "20260510_0032"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column("tasks", sa.Column("proof_photo_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "proof_photo_url")
