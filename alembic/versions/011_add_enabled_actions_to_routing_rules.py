"""Add enabled_actions to routing_rules.

Revision ID: 011
Revises: 010
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column("enabled_actions", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("routing_rules", "enabled_actions")
