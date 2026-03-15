"""Add message_id and channel_id columns to signal_logs.

Revision ID: 004
Revises: 003
Create Date: 2026-03-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "signal_logs",
        sa.Column("message_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "signal_logs",
        sa.Column("channel_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "idx_signal_logs_channel_message",
        "signal_logs",
        ["channel_id", "message_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_signal_logs_channel_message", table_name="signal_logs")
    op.drop_column("signal_logs", "channel_id")
    op.drop_column("signal_logs", "message_id")
