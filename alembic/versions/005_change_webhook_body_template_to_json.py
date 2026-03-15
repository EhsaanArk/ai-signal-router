"""Change webhook_body_template column from JSONB to JSON to preserve key order.

Revision ID: 005
Revises: 004
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE routing_rules "
        "ALTER COLUMN webhook_body_template "
        "TYPE JSON USING webhook_body_template::text::json"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE routing_rules "
        "ALTER COLUMN webhook_body_template "
        "TYPE JSONB USING webhook_body_template::text::jsonb"
    )
