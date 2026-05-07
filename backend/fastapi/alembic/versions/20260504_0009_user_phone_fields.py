"""users — add phone, first_name, last_name; make email nullable

Revision ID: 20260504_0009
Revises: 20260504_0008
Create Date: 2026-05-04
"""

from alembic import op

revision = "20260504_0009"
down_revision = "20260504_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(32)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(64)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(64)")
    # Partial unique index: plusieurs NULL autorisés (NULL != NULL en PostgreSQL)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone_unique "
        "ON users (phone) WHERE phone IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_phone_unique")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS first_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS phone")
    # Patch les lignes sans email avant de remettre NOT NULL
    op.execute(
        "UPDATE users SET email = 'legacy_' || id || '@placeholder.invalid' WHERE email IS NULL"
    )
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
