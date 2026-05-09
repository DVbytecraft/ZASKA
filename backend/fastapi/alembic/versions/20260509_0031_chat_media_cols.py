"""chat_messages: add media_url and media_type columns

Revision ID: 20260509_0031
Revises: 20260509_0030
Create Date: 2026-05-09
"""

revision = "20260509_0031"
down_revision = "20260509_0030"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chat_messages "
        "ADD COLUMN IF NOT EXISTS media_url VARCHAR(512),"
        "ADD COLUMN IF NOT EXISTS media_type VARCHAR(32)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE chat_messages DROP COLUMN IF EXISTS media_url")
    op.execute("ALTER TABLE chat_messages DROP COLUMN IF EXISTS media_type")
