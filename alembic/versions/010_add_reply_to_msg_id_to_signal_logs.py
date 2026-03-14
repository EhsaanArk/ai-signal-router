"""Add reply_to_msg_id to signal_logs.

Revision ID: 010
Revises: 009
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "signal_logs",
        sa.Column("reply_to_msg_id", sa.BigInteger, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signal_logs", "reply_to_msg_id")
