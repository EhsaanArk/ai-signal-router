"""Add is_verified flag to marketplace_providers.

Computed by the background stats scheduler: True when
track_record_days >= 30 AND signal_count >= 20.

Revision ID: 031
Revises: 030
"""

from alembic import op
import sqlalchemy as sa


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketplace_providers",
        sa.Column("is_verified", sa.Boolean, server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("marketplace_providers", "is_verified")
