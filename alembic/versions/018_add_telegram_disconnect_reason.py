"""Add disconnected_reason and disconnected_at to telegram_sessions.

Revision ID: 018
Revises: 017
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_sessions",
        sa.Column("disconnected_reason", sa.String(50), nullable=True),
    )
    op.add_column(
        "telegram_sessions",
        sa.Column(
            "disconnected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("telegram_sessions", "disconnected_at")
    op.drop_column("telegram_sessions", "disconnected_reason")
