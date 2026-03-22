"""Add terms_acceptance_log table for fintech compliance audit trail.

Revision ID: 025
Revises: 024
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "terms_acceptance_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),  # 'tos', 'privacy', 'risk_waiver'
        sa.Column("document_version", sa.String(20), nullable=False),  # e.g. '2026-03-22'
        sa.Column("ip_address", sa.String(45), nullable=True),  # IPv4 or IPv6
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_terms_acceptance_user_doc", "terms_acceptance_log", ["user_id", "document_type"])

    # Add current_tos_version to users table for quick re-acceptance checks
    op.add_column(
        "users",
        sa.Column("accepted_tos_version", sa.String(20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("accepted_risk_waiver", sa.Boolean, server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "accepted_risk_waiver")
    op.drop_column("users", "accepted_tos_version")
    op.drop_index("ix_terms_acceptance_user_doc", table_name="terms_acceptance_log")
    op.drop_table("terms_acceptance_log")
