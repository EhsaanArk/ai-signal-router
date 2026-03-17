"""Add partial unique index on phone_number for active sessions.

Prevents two different users from connecting the same Telegram phone
number simultaneously.  Only active sessions are constrained — a user
can reconnect a phone that was previously used by another (now inactive)
session.

Revision ID: 019
Revises: 018
Create Date: 2026-03-17
"""

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_telegram_sessions_active_phone",
        "telegram_sessions",
        ["phone_number"],
        unique=True,
        postgresql_where="is_active = TRUE",
    )


def downgrade() -> None:
    op.drop_index("uq_telegram_sessions_active_phone", table_name="telegram_sessions")
