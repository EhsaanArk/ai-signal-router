"""Add missing indexes for common query patterns.

Revision ID: 007
Revises: 006
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "CREATE INDEX idx_routing_rules_user_created "
        "ON routing_rules (user_id, created_at DESC)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_signal_logs_user_status_date "
        "ON signal_logs (user_id, status, processed_at DESC)"
    ))
    op.create_index(
        "idx_telegram_sessions_user_active",
        "telegram_sessions",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_telegram_sessions_user_active", table_name="telegram_sessions")
    op.drop_index("idx_signal_logs_user_status_date", table_name="signal_logs")
    op.drop_index("idx_routing_rules_user_created", table_name="routing_rules")
