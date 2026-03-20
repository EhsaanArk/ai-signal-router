"""Add token_lookup_hash columns for O(1) reset/verify token lookup.

Revision ID: 023
Revises: 022
"""

from alembic import op
import sqlalchemy as sa


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "password_reset_tokens",
        sa.Column("token_lookup_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_password_reset_tokens_token_lookup_hash",
        "password_reset_tokens",
        ["token_lookup_hash"],
        unique=False,
    )

    op.add_column(
        "email_verification_tokens",
        sa.Column("token_lookup_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_email_verification_tokens_token_lookup_hash",
        "email_verification_tokens",
        ["token_lookup_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_verification_tokens_token_lookup_hash",
        table_name="email_verification_tokens",
    )
    op.drop_column("email_verification_tokens", "token_lookup_hash")

    op.drop_index(
        "ix_password_reset_tokens_token_lookup_hash",
        table_name="password_reset_tokens",
    )
    op.drop_column("password_reset_tokens", "token_lookup_hash")
