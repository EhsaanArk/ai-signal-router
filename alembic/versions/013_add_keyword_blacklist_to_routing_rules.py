"""Add keyword_blacklist JSONB column to routing_rules.

Revision ID: 013
Revises: 012
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column("keyword_blacklist", JSONB, server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("routing_rules", "keyword_blacklist")
