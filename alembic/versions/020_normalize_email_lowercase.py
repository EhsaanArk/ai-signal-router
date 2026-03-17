"""Normalize all user emails to lowercase.

Revision ID: 020
Revises: 019
"""

from alembic import op


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize existing emails to lowercase
    op.execute("UPDATE users SET email = LOWER(email) WHERE email != LOWER(email)")


def downgrade() -> None:
    # Cannot restore original casing — no-op
    pass
