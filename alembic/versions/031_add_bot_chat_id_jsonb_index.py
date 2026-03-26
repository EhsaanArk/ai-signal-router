"""Add functional index on notification_preferences->>'telegram_bot_chat_id'.

Revision ID: 031
Revises: 030
"""

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_tg_bot_chat "
        "ON users ((notification_preferences->>'telegram_bot_chat_id'));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_tg_bot_chat;")
