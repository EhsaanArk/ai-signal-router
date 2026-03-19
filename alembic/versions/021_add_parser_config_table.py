"""Add parser_config table for admin-managed parser settings.

Revision ID: 021
Revises: 020
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parser_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("config_key", sa.String(50), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("model_name", sa.String(50), nullable=True),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column("changed_by_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_parser_config_active", "parser_config", ["is_active"])
    op.create_index("idx_parser_config_key", "parser_config", ["config_key"])


def downgrade() -> None:
    op.drop_index("idx_parser_config_key", table_name="parser_config")
    op.drop_index("idx_parser_config_active", table_name="parser_config")
    op.drop_table("parser_config")
