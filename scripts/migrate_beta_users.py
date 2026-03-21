#!/usr/bin/env python3
"""One-time migration script: copy beta users and routing rules from staging DB to production DB.

Migrates:
  - users (accounts, password hashes, tiers, admin flags, preferences)
  - routing_rules (all route config, templates, mappings, actions)

Skips:
  - telegram_sessions (encryption-key dependent — users re-connect on prod)
  - signal_logs (historical data, not critical)
  - email_verification_tokens / password_reset_tokens (ephemeral)

Conflict handling:
  - If a user's email already exists in production, that user is SKIPPED.

Usage:
  # Dry run (report only, no writes):
  python scripts/migrate_beta_users.py --dry-run

  # Live migration:
  python scripts/migrate_beta_users.py

Environment variables required:
  STAGING_DATABASE_URL  — staging PostgreSQL connection string
  PROD_DATABASE_URL     — production PostgreSQL connection string
  RESEND_API_KEY        — (optional) to send migration notification emails
  PROD_FRONTEND_URL     — production frontend URL (default: https://app.radar.sagemaster.com)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROD_FRONTEND_URL = os.getenv("PROD_FRONTEND_URL", "https://app.radar.sagemaster.com")


def get_connection(url: str, label: str):
    """Create a psycopg2 connection from an async-style URL."""
    # Convert asyncpg URL to psycopg2 format
    sync_url = url.replace("postgresql+asyncpg://", "postgresql://")
    logger.info("Connecting to %s DB...", label)
    conn = psycopg2.connect(sync_url)
    conn.autocommit = False
    return conn


def fetch_staging_users(staging_conn) -> list[dict]:
    """Fetch all non-admin users from staging (admin accounts stay on staging)."""
    with staging_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, email, password_hash, subscription_tier,
                   notification_preferences, is_admin, is_disabled,
                   email_verified, created_at, updated_at
            FROM users
            WHERE is_admin = false
            ORDER BY created_at
        """)
        return cur.fetchall()


def fetch_routing_rules(staging_conn, user_id: str) -> list[dict]:
    """Fetch all routing rules for a given user."""
    with staging_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, user_id, source_channel_id, source_channel_name,
                   destination_webhook_url, payload_version, symbol_mappings,
                   risk_overrides, webhook_body_template, rule_name,
                   destination_label, destination_type, custom_ai_instructions,
                   enabled_actions, keyword_blacklist, is_active,
                   created_at, updated_at
            FROM routing_rules
            WHERE user_id = %s
        """, (str(user_id),))
        return cur.fetchall()


def email_exists_in_prod(prod_conn, email: str) -> bool:
    """Check if an email already exists in the production DB."""
    with prod_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        return cur.fetchone() is not None


def insert_user(prod_conn, user: dict):
    """Insert a user into the production DB."""
    with prod_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users (
                id, email, password_hash, subscription_tier,
                notification_preferences, is_admin, is_disabled,
                email_verified, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            str(user["id"]),
            user["email"],
            user["password_hash"],
            user["subscription_tier"],
            json.dumps(user["notification_preferences"] or {}),
            user["is_admin"],
            user["is_disabled"],
            user["email_verified"],
            user["created_at"],
            user["updated_at"],
        ))


def insert_routing_rule(prod_conn, rule: dict):
    """Insert a routing rule into the production DB."""
    with prod_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO routing_rules (
                id, user_id, source_channel_id, source_channel_name,
                destination_webhook_url, payload_version, symbol_mappings,
                risk_overrides, webhook_body_template, rule_name,
                destination_label, destination_type, custom_ai_instructions,
                enabled_actions, keyword_blacklist, is_active,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            str(rule["id"]),
            str(rule["user_id"]),
            rule["source_channel_id"],
            rule["source_channel_name"],
            rule["destination_webhook_url"],
            rule["payload_version"],
            json.dumps(rule["symbol_mappings"] or {}),
            json.dumps(rule["risk_overrides"] or {}),
            json.dumps(rule["webhook_body_template"]) if rule["webhook_body_template"] else None,
            rule["rule_name"],
            rule["destination_label"],
            rule["destination_type"],
            rule["custom_ai_instructions"],
            json.dumps(rule["enabled_actions"]) if rule["enabled_actions"] else None,
            json.dumps(rule["keyword_blacklist"] or []),
            rule["is_active"],
            rule["created_at"],
            rule["updated_at"],
        ))


def send_migration_emails(migrated_users: list[dict]):
    """Send migration notification emails to all migrated users."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping migration emails")
        return

    import resend
    resend.api_key = api_key

    for user in migrated_users:
        try:
            resend.Emails.send({
                "from": "Sage Radar AI <noreply@radar.sagemaster.com>",
                "to": [user["email"]],
                "subject": "Sage Radar AI has moved to production!",
                "html": (
                    '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
                    'max-width:480px;margin:0 auto;padding:20px">'
                    "<p>Hi there,</p>"
                    "<p>Thank you for being a beta tester of Sage Radar AI! "
                    "We've officially launched production and <strong>your account "
                    "has been migrated</strong>.</p>"
                    "<p><strong>What you need to do:</strong></p>"
                    '<ol style="line-height:1.8">'
                    f'<li>Visit <a href="{PROD_FRONTEND_URL}" target="_blank" '
                    f'style="color:#2563eb">{PROD_FRONTEND_URL}</a></li>'
                    "<li>Sign in with your existing email and password</li>"
                    "<li>Re-connect your Telegram account (takes ~2 minutes)</li>"
                    "</ol>"
                    "<p>Your routing rules and configuration have been preserved. "
                    "The staging environment is now reserved for development only.</p>"
                    '<p style="text-align:center;margin:24px 0">'
                    f'<a href="{PROD_FRONTEND_URL}" target="_blank" '
                    'style="display:inline-block;background:#2563eb;color:#fff;'
                    'padding:12px 24px;border-radius:6px;text-decoration:none;'
                    f'font-weight:600">Go to Production</a></p>'
                    '<p style="font-size:13px;color:#666">Questions? Reply to this email.</p>'
                    "</body></html>"
                ),
            })
            logger.info("  Sent migration email to %s", user["email"])
        except Exception as exc:
            logger.error("  Failed to send email to %s: %s", user["email"], exc)


def main():
    parser = argparse.ArgumentParser(description="Migrate beta users from staging to production")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    staging_url = os.getenv("STAGING_DATABASE_URL")
    prod_url = os.getenv("PROD_DATABASE_URL")

    if not staging_url:
        logger.error("STAGING_DATABASE_URL not set")
        sys.exit(1)
    if not prod_url:
        logger.error("PROD_DATABASE_URL not set")
        sys.exit(1)

    staging_conn = get_connection(staging_url, "staging")
    prod_conn = get_connection(prod_url, "production")

    try:
        users = fetch_staging_users(staging_conn)
        logger.info("Found %d non-admin users on staging", len(users))

        if not users:
            logger.info("No users to migrate. Done.")
            return

        migrated = []
        skipped = []

        for user in users:
            email = user["email"]

            if email_exists_in_prod(prod_conn, email):
                logger.info("  SKIP: %s (already exists in production)", email)
                skipped.append(user)
                continue

            rules = fetch_routing_rules(staging_conn, user["id"])

            if args.dry_run:
                logger.info("  [DRY RUN] Would migrate: %s (%d rules)", email, len(rules))
                migrated.append(user)
                continue

            # Insert user
            insert_user(prod_conn, user)
            logger.info("  MIGRATED: %s", email)

            # Insert their routing rules
            for rule in rules:
                insert_routing_rule(prod_conn, rule)
                logger.info("    + Rule: %s (%s → %s)",
                            rule["rule_name"] or rule["source_channel_id"],
                            rule["source_channel_name"] or "unknown",
                            rule["destination_type"])

            migrated.append(user)

        if not args.dry_run:
            prod_conn.commit()
            logger.info("Production DB committed.")

        # Summary
        logger.info("")
        logger.info("=" * 50)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 50)
        logger.info("  Migrated: %d users", len(migrated))
        logger.info("  Skipped:  %d users (already in prod)", len(skipped))
        logger.info("  Mode:     %s", "DRY RUN" if args.dry_run else "LIVE")
        logger.info("=" * 50)

        # Send notification emails (only in live mode)
        if not args.dry_run and migrated:
            logger.info("")
            logger.info("Sending migration notification emails...")
            send_migration_emails(migrated)

    except Exception:
        logger.exception("Migration failed — rolling back production DB")
        prod_conn.rollback()
        sys.exit(1)
    finally:
        staging_conn.close()
        prod_conn.close()


if __name__ == "__main__":
    main()
