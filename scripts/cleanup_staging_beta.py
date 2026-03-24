"""Cleanup staging environment: deactivate old beta Telegram sessions and routing rules.

Usage:
    python scripts/cleanup_staging_beta.py              # Dry run
    python scripts/cleanup_staging_beta.py --execute    # Execute

Requires DATABASE_URL env var pointing to the staging database.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.adapters.db.models import RoutingRuleModel, TelegramSessionModel, UserModel  # noqa: E402


async def run_cleanup(execute: bool) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL env var is required")
        sys.exit(1)

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)

    async with AsyncSession(engine, expire_on_commit=False) as db:
        result = await db.execute(
            select(TelegramSessionModel.id, TelegramSessionModel.user_id,
                   TelegramSessionModel.phone_number, UserModel.email)
            .outerjoin(UserModel, TelegramSessionModel.user_id == UserModel.id)
            .where(TelegramSessionModel.is_active.is_(True))
        )
        active_sessions = result.all()

        print(f"\n{'='*60}")
        print(f"  STAGING CLEANUP — {'DRY RUN' if not execute else 'EXECUTING'}")
        print(f"{'='*60}\n")
        print(f"Active Telegram sessions: {len(active_sessions)}")
        for _, _, phone, email in active_sessions:
            print(f"  - {email} | {phone}")

        if active_sessions and execute:
            await db.execute(
                update(TelegramSessionModel)
                .where(TelegramSessionModel.is_active.is_(True))
                .values(is_active=False, disconnected_reason="staging_cleanup",
                        disconnected_at=func.now())
            )
            print(f"\n  -> Deactivated {len(active_sessions)} session(s)")

        result = await db.execute(
            select(RoutingRuleModel.id, RoutingRuleModel.source_channel_name, UserModel.email)
            .outerjoin(UserModel, RoutingRuleModel.user_id == UserModel.id)
            .where(
                RoutingRuleModel.is_active.is_(True),
                ~RoutingRuleModel.user_id.in_(
                    select(TelegramSessionModel.user_id)
                    .where(TelegramSessionModel.is_active.is_(True))
                ),
            )
        )
        orphaned_rules = result.all()
        print(f"\nOrphaned routing rules: {len(orphaned_rules)}")
        for rule_id, channel_name, email in orphaned_rules:
            print(f"  - {email} | channel: {channel_name}")

        if orphaned_rules and execute:
            await db.execute(
                update(RoutingRuleModel)
                .where(RoutingRuleModel.id.in_([r[0] for r in orphaned_rules]))
                .values(is_active=False)
            )
            print(f"\n  -> Deactivated {len(orphaned_rules)} orphaned rule(s)")

        if execute:
            await db.commit()
            print(f"\n  CLEANUP COMPLETE\n")
        else:
            print(f"\n  DRY RUN — run with --execute to apply\n")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(run_cleanup(parser.parse_args().execute))
