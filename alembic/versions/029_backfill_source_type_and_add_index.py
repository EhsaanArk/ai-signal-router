"""Backfill signal_logs.source_type NULLs and add composite index.

Existing rows from before migration 026 have source_type=NULL.
compute_provider_stats() queries WHERE source_type='telegram',
so NULLs are missed — provider stats show 0 for historical data.

Revision ID: 029
Revises: 028
"""

from alembic import op


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill NULLs — all pre-marketplace signals are 'telegram'
    op.execute("UPDATE signal_logs SET source_type = 'telegram' WHERE source_type IS NULL")

    # Composite index for marketplace stats queries
    op.create_index(
        "idx_signal_logs_channel_source_type",
        "signal_logs",
        ["channel_id", "source_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_signal_logs_channel_source_type", table_name="signal_logs")
    # Cannot un-backfill — leave values as-is
