"""One-time migration: create Supabase Auth accounts for existing DB users.

Preserves the same UUID so all routing rules, signal logs, and Telegram
sessions stay linked. Users will need to use "Forgot Password" on first
login to set a Supabase password.

Usage:
    # Set env vars first:
    export DATABASE_URL="postgresql://..."
    export SUPABASE_URL="https://xxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="..."

    python scripts/migrate_users_to_supabase.py

    # Dry run (no changes):
    python scripts/migrate_users_to_supabase.py --dry-run
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate():
    dry_run = "--dry-run" in sys.argv

    # Load settings
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    database_url = os.environ.get("DATABASE_URL", "")

    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)

    if not database_url:
        print("ERROR: DATABASE_URL must be set")
        sys.exit(1)

    # Connect to DB
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Ensure async driver
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Connect to Supabase
    from supabase import create_client
    sb = create_client(supabase_url, supabase_key)

    async with async_session() as db:
        # Fetch all users
        result = await db.execute(
            text("SELECT id, email, email_verified, is_admin, subscription_tier, created_at FROM users ORDER BY created_at")
        )
        users = result.fetchall()

        print(f"Found {len(users)} users to migrate")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print("-" * 60)

        migrated = 0
        skipped = 0
        failed = 0

        for user in users:
            user_id, email, email_verified, is_admin, tier, created_at = user
            print(f"\n  [{user_id}] {email}")
            print(f"    tier={tier}, admin={is_admin}, verified={email_verified}")

            if dry_run:
                print(f"    -> WOULD CREATE in Supabase (same UUID)")
                migrated += 1
                continue

            try:
                # Check if user already exists in Supabase
                try:
                    existing = sb.auth.admin.get_user_by_id(str(user_id))
                    if existing and existing.user:
                        print(f"    -> SKIP: already exists in Supabase")
                        skipped += 1
                        continue
                except Exception:
                    pass  # User doesn't exist — proceed with creation

                # Create user in Supabase with same UUID
                sb.auth.admin.create_user({
                    "id": str(user_id),
                    "email": email,
                    "email_confirm": bool(email_verified),
                    "user_metadata": {
                        "migrated_from": "legacy",
                        "subscription_tier": tier,
                        "is_admin": bool(is_admin),
                    },
                })

                # Update password_hash in DB to mark as Supabase-managed
                await db.execute(
                    text("UPDATE users SET password_hash = '!' WHERE id = :uid"),
                    {"uid": user_id},
                )

                print(f"    -> CREATED in Supabase (same UUID preserved)")
                migrated += 1

            except Exception as exc:
                print(f"    -> FAILED: {exc}")
                failed += 1

        await db.commit()

    await engine.dispose()

    print("\n" + "=" * 60)
    print(f"Migration complete:")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Failed:   {failed}")
    print(f"\nNext steps:")
    print(f"  1. Email users: 'Use Forgot Password to set your new password'")
    print(f"  2. Or users can sign in with Google if they used the same email")


if __name__ == "__main__":
    asyncio.run(migrate())
