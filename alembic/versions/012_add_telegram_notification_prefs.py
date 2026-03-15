"""Add telegram notification preferences to users.

Updates the JSONB notification_preferences column on users to include
telegram_on_success, telegram_on_failure, and telegram_bot_chat_id keys
with sensible defaults.

Revision ID: 012
Revises: 011
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing rows to include telegram keys with defaults
    op.execute(
        sa.text("""
            UPDATE users
            SET notification_preferences = notification_preferences
                || '{"telegram_on_success": false, "telegram_on_failure": false, "telegram_bot_chat_id": null}'::jsonb
            WHERE NOT notification_preferences ? 'telegram_on_success'
        """)
    )


def downgrade() -> None:
    # Remove telegram keys from JSONB
    op.execute(
        sa.text("""
            UPDATE users
            SET notification_preferences = notification_preferences
                - 'telegram_on_success'
                - 'telegram_on_failure'
                - 'telegram_bot_chat_id'
        """)
    )
