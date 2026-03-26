"""Add is_marketplace_template flag to routing_rules.

Marks routing rules created as webhook destination templates via the
marketplace subscribe inline form. These rules are hidden from the
user's routing rules list and exempt from tier limits.

Revision ID: 030
Revises: 029
"""

from alembic import op
import sqlalchemy as sa


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routing_rules",
        sa.Column("is_marketplace_template", sa.Boolean, server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("routing_rules", "is_marketplace_template")
