"""Add rule_name and destination_label to routing_rules.

Revision ID: 008
Revises: 007
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column("rule_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "routing_rules",
        sa.Column("destination_label", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("routing_rules", "destination_label")
    op.drop_column("routing_rules", "rule_name")
