"""
Seed script: Create sample marketplace providers for testing.

Usage:
  python3 scripts/seed_marketplace.py

Requires: DATABASE_URL env var or running PostgreSQL via docker compose.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/sgm_copier",
)

SAMPLE_PROVIDERS = [
    {
        "id": str(uuid4()),
        "name": "Gold Signals Pro",
        "description": "Professional XAUUSD and forex major pairs. Swing trading with strict risk management.",
        "asset_class": "forex",
        "telegram_channel_id": "-1001234567890",
        "is_active": True,
        "win_rate": 72.3,
        "total_pnl_pips": 1428.5,
        "max_drawdown_pips": 82.0,
        "signal_count": 142,
        "subscriber_count": 32,
        "track_record_days": 94,
        "stats_last_computed_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": str(uuid4()),
        "name": "Crypto Alpha Calls",
        "description": "BTC/ETH/SOL spot and futures signals. Scalping and day trading focused.",
        "asset_class": "crypto",
        "telegram_channel_id": "-1001234567891",
        "is_active": True,
        "win_rate": 58.1,
        "total_pnl_pips": -23.0,
        "max_drawdown_pips": 151.0,
        "signal_count": 89,
        "subscriber_count": 18,
        "track_record_days": 62,
        "stats_last_computed_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": str(uuid4()),
        "name": "Precision FX",
        "description": "EUR/USD, GBP/USD, USD/JPY. Conservative entries with 1:2 R:R minimum.",
        "asset_class": "forex",
        "telegram_channel_id": "-1001234567892",
        "is_active": True,
        "win_rate": 65.8,
        "total_pnl_pips": 547.0,
        "max_drawdown_pips": 45.0,
        "signal_count": 234,
        "subscriber_count": 47,
        "track_record_days": 128,
        "stats_last_computed_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": str(uuid4()),
        "name": "Altcoin Sniper",
        "description": "Altcoin gems and early entries. Higher risk, higher reward.",
        "asset_class": "crypto",
        "telegram_channel_id": "-1001234567893",
        "is_active": True,
        "win_rate": 41.2,
        "total_pnl_pips": 890.0,
        "max_drawdown_pips": 320.0,
        "signal_count": 67,
        "subscriber_count": 12,
        "track_record_days": 45,
        "stats_last_computed_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": str(uuid4()),
        "name": "Multi-Asset Elite",
        "description": "Forex + crypto cross-market opportunities. Institutional-grade analysis.",
        "asset_class": "both",
        "telegram_channel_id": "-1001234567894",
        "is_active": True,
        "win_rate": 68.9,
        "total_pnl_pips": 2105.0,
        "max_drawdown_pips": 95.0,
        "signal_count": 312,
        "subscriber_count": 63,
        "track_record_days": 183,
        "stats_last_computed_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": str(uuid4()),
        "name": "New Provider (No Data)",
        "description": "Recently added — performance tracking has just started.",
        "asset_class": "forex",
        "telegram_channel_id": "-1001234567895",
        "is_active": True,
        "win_rate": None,
        "total_pnl_pips": None,
        "max_drawdown_pips": None,
        "signal_count": 3,
        "subscriber_count": 1,
        "track_record_days": 5,
        "stats_last_computed_at": None,
    },
]


def seed():
    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
    engine = create_engine(sync_url)

    with engine.begin() as conn:
        # Check if table exists
        result = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'marketplace_providers')")
        )
        if not result.scalar():
            print("ERROR: marketplace_providers table does not exist. Run alembic upgrade head first.")
            sys.exit(1)

        # Check if already seeded
        result = conn.execute(text("SELECT COUNT(*) FROM marketplace_providers"))
        count = result.scalar()
        if count > 0:
            print(f"marketplace_providers already has {count} rows. Skipping seed.")
            return

        # Insert sample providers
        for p in SAMPLE_PROVIDERS:
            conn.execute(
                text("""
                    INSERT INTO marketplace_providers
                    (id, name, description, asset_class, telegram_channel_id, is_active,
                     win_rate, total_pnl_pips, max_drawdown_pips, signal_count,
                     subscriber_count, track_record_days, stats_last_computed_at, created_at)
                    VALUES
                    (:id, :name, :description, :asset_class, :telegram_channel_id, :is_active,
                     :win_rate, :total_pnl_pips, :max_drawdown_pips, :signal_count,
                     :subscriber_count, :track_record_days, :stats_last_computed_at, NOW())
                """),
                p,
            )

        print(f"Seeded {len(SAMPLE_PROVIDERS)} marketplace providers.")


if __name__ == "__main__":
    seed()
