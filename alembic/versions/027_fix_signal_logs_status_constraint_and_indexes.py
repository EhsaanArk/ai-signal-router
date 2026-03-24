"""Fix signal_logs status CHECK constraint + add missing indexes.

- Add 'queued' to signal_logs status CHECK constraint (needed for two-stage dispatch)
- Add index on signal_logs.routing_rule_id (missing — full table scan on rule queries)
- Add index on marketplace_subscriptions.user_id (standalone — improves My Subs page)

Revision ID: 027
Revises: 026
"""

from alembic import op


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Fix CHECK constraint to include 'queued' status
    op.drop_constraint("ck_signal_logs_status", "signal_logs", type_="check")
    op.create_check_constraint(
        "ck_signal_logs_status",
        "signal_logs",
        "status IN ('success', 'failed', 'ignored', 'queued')",
    )

    # 2. Add missing index on signal_logs.routing_rule_id
    op.create_index(
        "idx_signal_logs_routing_rule",
        "signal_logs",
        ["routing_rule_id"],
    )

    # 3. Add standalone index on marketplace_subscriptions.user_id
    op.create_index(
        "idx_marketplace_sub_user",
        "marketplace_subscriptions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_marketplace_sub_user", table_name="marketplace_subscriptions")
    op.drop_index("idx_signal_logs_routing_rule", table_name="signal_logs")
    op.drop_constraint("ck_signal_logs_status", "signal_logs", type_="check")
    op.create_check_constraint(
        "ck_signal_logs_status",
        "signal_logs",
        "status IN ('success', 'failed', 'ignored')",
    )
