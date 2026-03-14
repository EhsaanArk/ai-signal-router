"""Add destination_type and custom_ai_instructions to routing_rules.

Revision ID: 009
Revises: 008
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column(
            "destination_type",
            sa.String(20),
            nullable=False,
            server_default="sagemaster_forex",
        ),
    )
    op.add_column(
        "routing_rules",
        sa.Column("custom_ai_instructions", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("routing_rules", "custom_ai_instructions")
    op.drop_column("routing_rules", "destination_type")
