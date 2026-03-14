"""Add webhook_body_template column to routing_rules.

Revision ID: 003
Revises: 002
Create Date: 2026-03-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column("webhook_body_template", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("routing_rules", "webhook_body_template")
