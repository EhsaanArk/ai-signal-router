"""Add global_settings table for admin-configurable system settings.

Revision ID: 022
Revises: 021
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "global_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed the default backfill staleness setting
    op.execute(
        """
        INSERT INTO global_settings (key, value, description)
        VALUES (
            'backfill_max_age_seconds',
            '60',
            'Max age (seconds) for a signal to be considered fresh during backfill after listener reconnect. Signals older than this are ignored.'
        )
        """
    )


def downgrade() -> None:
    op.drop_table("global_settings")
