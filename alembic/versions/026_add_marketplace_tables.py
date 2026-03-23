"""Add marketplace tables and source_type to signal_logs.

Revision ID: 026
Revises: 025
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- marketplace_providers ---
    op.create_table(
        "marketplace_providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("telegram_channel_id", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("total_pnl_pips", sa.Float, nullable=True),
        sa.Column("max_drawdown_pips", sa.Float, nullable=True),
        sa.Column("signal_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("subscriber_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("track_record_days", sa.Integer, server_default="0", nullable=False),
        sa.Column("stats_last_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "asset_class IN ('forex', 'crypto', 'both')",
            name="ck_marketplace_providers_asset_class",
        ),
    )
    op.create_index("idx_marketplace_providers_active", "marketplace_providers", ["is_active"])
    op.create_index("idx_marketplace_providers_channel", "marketplace_providers", ["telegram_channel_id"])

    # --- marketplace_subscriptions ---
    op.create_table(
        "marketplace_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "provider_id", UUID(as_uuid=True),
            sa.ForeignKey("marketplace_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "routing_rule_id", UUID(as_uuid=True),
            sa.ForeignKey("routing_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "provider_id", name="uq_marketplace_sub_user_provider"),
    )
    op.create_index("idx_marketplace_sub_user_active", "marketplace_subscriptions", ["user_id", "is_active"])
    op.create_index("idx_marketplace_sub_provider_active", "marketplace_subscriptions", ["provider_id", "is_active"])

    # --- marketplace_consent_log ---
    op.create_table(
        "marketplace_consent_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "provider_id", UUID(as_uuid=True),
            sa.ForeignKey("marketplace_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("disclaimer_version", sa.String(20), server_default="1.0", nullable=False),
    )
    op.create_index("idx_marketplace_consent_user", "marketplace_consent_log", ["user_id", "provider_id"])

    # --- Add source_type to signal_logs ---
    op.add_column(
        "signal_logs",
        sa.Column("source_type", sa.String(50), server_default="telegram", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signal_logs", "source_type")
    op.drop_index("idx_marketplace_consent_user", table_name="marketplace_consent_log")
    op.drop_table("marketplace_consent_log")
    op.drop_index("idx_marketplace_sub_provider_active", table_name="marketplace_subscriptions")
    op.drop_index("idx_marketplace_sub_user_active", table_name="marketplace_subscriptions")
    op.drop_table("marketplace_subscriptions")
    op.drop_index("idx_marketplace_providers_channel", table_name="marketplace_providers")
    op.drop_index("idx_marketplace_providers_active", table_name="marketplace_providers")
    op.drop_table("marketplace_providers")
