"""Initial schema — users, telegram_sessions, routing_rules, signal_logs.

Revision ID: 001
Revises: None
Create Date: 2026-03-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ------------------------------------------------------------------
    # telegram_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "telegram_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone_number", sa.String(50), nullable=False),
        sa.Column("session_string_encrypted", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "phone_number", name="uq_session_user_phone"),
    )

    op.create_index(
        "idx_telegram_sessions_active",
        "telegram_sessions",
        ["is_active"],
    )

    # ------------------------------------------------------------------
    # routing_rules
    # ------------------------------------------------------------------
    op.create_table(
        "routing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_channel_id", sa.String(255), nullable=False),
        sa.Column("source_channel_name", sa.String(255), nullable=True),
        sa.Column("destination_webhook_url", sa.Text, nullable=False),
        sa.Column(
            "payload_version",
            sa.String(10),
            nullable=False,
        ),
        sa.Column("symbol_mappings", JSONB, server_default="{}"),
        sa.Column("risk_overrides", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("payload_version IN ('V1', 'V2')", name="ck_routing_rules_payload_version"),
    )

    op.create_index(
        "idx_routing_rules_lookup",
        "routing_rules",
        ["user_id", "source_channel_id"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    # ------------------------------------------------------------------
    # signal_logs
    # ------------------------------------------------------------------
    op.create_table(
        "signal_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("routing_rule_id", UUID(as_uuid=True), sa.ForeignKey("routing_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("raw_message", sa.Text, nullable=False),
        sa.Column("parsed_data", JSONB, nullable=True),
        sa.Column("webhook_payload", JSONB, nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('success', 'failed', 'ignored')", name="ck_signal_logs_status"),
    )

    op.create_index(
        "idx_signal_logs_user_date",
        "signal_logs",
        ["user_id", sa.text("processed_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("signal_logs")
    op.drop_table("routing_rules")
    op.drop_table("telegram_sessions")
    op.drop_table("users")
