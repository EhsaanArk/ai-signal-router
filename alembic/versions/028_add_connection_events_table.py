"""Add connection_events table for historical disconnect tracking.

Revision ID: 028
Revises: 027
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connection_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_connection_events_user_time",
        "connection_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_connection_events_type_time",
        "connection_events",
        ["event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_connection_events_type_time", table_name="connection_events")
    op.drop_index("idx_connection_events_user_time", table_name="connection_events")
    op.drop_table("connection_events")
