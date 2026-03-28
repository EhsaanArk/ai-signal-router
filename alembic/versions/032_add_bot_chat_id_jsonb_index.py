"""Add functional indexes on notification_preferences for bot lookups.

Revision ID: 032
Revises: 031
"""

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_tg_bot_chat "
        "ON users ((notification_preferences->>'telegram_bot_chat_id'));"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_tg_user_id "
        "ON users ((notification_preferences->>'telegram_user_id'));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_tg_user_id;")
    op.execute("DROP INDEX IF EXISTS idx_users_tg_bot_chat;")
