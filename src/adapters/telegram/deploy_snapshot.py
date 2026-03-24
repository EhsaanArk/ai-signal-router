"""Pre-/post-deploy snapshot for session preservation verification.

On SIGTERM the listener saves a snapshot of connected sessions to Redis.
After restart the manager reads the snapshot and compares it against the
newly connected sessions, logging any regressions.

Redis key: ``deploy:snapshot:{environment}``
TTL: 10 minutes (well above any deploy window)

The snapshot is a JSON dict::

    {
        "active_sessions": 6,
        "connected_listeners": 6,
        "channels_monitored": 13,
        "user_ids": ["uuid-1", "uuid-2", ...],
        "timestamp": "2026-03-19T02:10:00Z"
    }

Security: NEVER store session strings or encrypted keys — only counts
and user IDs (UUIDs are not PII).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

_SNAPSHOT_TTL_SECONDS = 600  # 10 minutes
_ENV = os.environ.get("SENTRY_ENVIRONMENT", "staging")
SNAPSHOT_KEY = f"deploy:snapshot:{_ENV}"


def build_snapshot(
    listeners: dict[UUID, object],
    monitored_channels: dict[UUID, set[str]],
) -> dict:
    """Build a snapshot dict from the current manager state.

    Parameters
    ----------
    listeners:
        Map of user_id → TelegramListener (must have ``.is_connected``).
    monitored_channels:
        Map of user_id → set of channel IDs.
    """
    connected = sum(
        1 for l in listeners.values()
        if getattr(l, "is_connected", False)
    )
    total_channels = sum(len(ch) for ch in monitored_channels.values())

    return {
        "active_sessions": len(listeners),
        "connected_listeners": connected,
        "channels_monitored": total_channels,
        "user_ids": [str(uid) for uid in listeners],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def save_pre_shutdown_snapshot(
    redis_url: str,
    listeners: dict[UUID, object],
    monitored_channels: dict[UUID, set[str]],
) -> bool:
    """Save a pre-shutdown snapshot to Redis.

    Returns True on success, False on failure (graceful degradation).
    """
    try:
        import redis.asyncio as aioredis

        snapshot = build_snapshot(listeners, monitored_channels)
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await client.set(
                SNAPSHOT_KEY,
                json.dumps(snapshot),
                ex=_SNAPSHOT_TTL_SECONDS,
            )
            logger.info(
                "Pre-shutdown snapshot saved: %d sessions, %d connected, %d channels",
                snapshot["active_sessions"],
                snapshot["connected_listeners"],
                snapshot["channels_monitored"],
            )
            return True
        finally:
            close = getattr(client, "aclose", None) or client.close
            await close()
    except Exception as exc:
        logger.warning("Failed to save pre-shutdown snapshot: %s", exc)
        return False


async def read_pre_deploy_snapshot(cache) -> dict | None:
    """Read the pre-deploy snapshot from the cache (Redis or in-memory).

    Parameters
    ----------
    cache:
        A ``CachePort`` implementation (``RedisCacheAdapter`` or
        ``InMemoryCacheAdapter``).

    Returns None if no snapshot exists, expired, or corrupt.
    """
    try:
        raw = await cache.get(SNAPSHOT_KEY)
        if raw is None:
            return None
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Pre-deploy snapshot is corrupt — ignoring")
        return None
    except Exception as exc:
        logger.warning("Failed to read pre-deploy snapshot: %s", exc)
        return None


def compare_snapshots(pre: dict, post: dict) -> dict:
    """Compare pre-deploy and post-deploy snapshots.

    Returns a comparison dict with deltas and a verdict.
    """
    sessions_before = pre.get("active_sessions", 0)
    sessions_after = post.get("active_sessions", 0)
    sessions_delta = sessions_after - sessions_before

    connected_before = pre.get("connected_listeners", 0)
    connected_after = post.get("connected_listeners", 0)

    channels_before = pre.get("channels_monitored", 0)
    channels_after = post.get("channels_monitored", 0)

    # Determine which users were lost
    pre_users = set(pre.get("user_ids", []))
    post_users = set(post.get("user_ids", []))
    lost_users = pre_users - post_users
    new_users = post_users - pre_users

    # Verdict logic
    if sessions_delta < 0:
        verdict = "SESSIONS_LOST"
    elif connected_after < connected_before:
        verdict = "CONNECTIONS_DEGRADED"
    else:
        verdict = "HEALTHY"

    return {
        "verdict": verdict,
        "sessions_before": sessions_before,
        "sessions_after": sessions_after,
        "sessions_delta": sessions_delta,
        "connected_before": connected_before,
        "connected_after": connected_after,
        "channels_before": channels_before,
        "channels_after": channels_after,
        "lost_user_ids": list(lost_users),
        "new_user_ids": list(new_users),
        "pre_deploy_timestamp": pre.get("timestamp"),
    }


async def wait_for_previous_shutdown(cache, guard_seconds: float = 5.0) -> None:
    """Wait until the previous container's shutdown is safely past.

    Reads the pre-deploy snapshot timestamp and sleeps until at least
    ``guard_seconds`` have elapsed since that shutdown.  This prevents
    the new container from connecting while the old one still has active
    Telegram sessions, which would cause AuthKeyDuplicatedError.

    If no snapshot exists (first deploy, or snapshot expired), returns
    immediately — there is no overlap risk.
    """
    pre = await read_pre_deploy_snapshot(cache)
    if pre is None:
        return

    shutdown_ts = pre.get("timestamp")
    if not shutdown_ts:
        return

    try:
        shutdown_time = datetime.fromisoformat(shutdown_ts)
        elapsed = (datetime.now(timezone.utc) - shutdown_time).total_seconds()
        remaining = guard_seconds - elapsed

        if remaining > 0:
            logger.info(
                "Previous container shut down %.1fs ago — waiting %.1fs "
                "for auth keys to fully release on Telegram's side",
                elapsed, remaining,
            )
            await asyncio.sleep(remaining)
            logger.info("Startup guard complete — safe to connect")
        else:
            logger.info(
                "Previous container shut down %.1fs ago (>%.0fs guard) "
                "— safe to connect immediately",
                elapsed, guard_seconds,
            )
    except (ValueError, TypeError) as exc:
        logger.debug("Could not parse snapshot timestamp: %s", exc)


async def run_post_startup_check(
    cache,
    listeners: dict[UUID, object],
    monitored_channels: dict[UUID, set[str]],
) -> dict | None:
    """Run the post-startup self-check.

    Reads the pre-deploy snapshot from cache, compares against current state,
    and logs the result.  Returns the comparison dict, or None if no snapshot
    was found.
    """
    pre = await read_pre_deploy_snapshot(cache)
    if pre is None:
        logger.info(
            "No pre-deploy snapshot found — skipping deploy health comparison"
        )
        return None

    post = build_snapshot(listeners, monitored_channels)
    comparison = compare_snapshots(pre, post)

    if comparison["verdict"] == "HEALTHY":
        logger.info(
            "Deploy health check: %d/%d sessions preserved, %d channels",
            comparison["sessions_after"],
            comparison["sessions_before"],
            comparison["channels_after"],
        )
    elif comparison["verdict"] == "SESSIONS_LOST":
        logger.warning(
            "Deploy health check: %d session(s) LOST (%d → %d). "
            "Lost users: %s",
            abs(comparison["sessions_delta"]),
            comparison["sessions_before"],
            comparison["sessions_after"],
            comparison["lost_user_ids"],
        )
        try:
            import sentry_sdk
            sentry_sdk.add_breadcrumb(
                category="deploy.health",
                message=(
                    f"Sessions lost after deploy: "
                    f"{comparison['sessions_before']} → {comparison['sessions_after']}"
                ),
                level="warning",
                data=comparison,
            )
        except Exception:
            pass
    else:
        logger.warning(
            "Deploy health check: connections degraded (%d → %d connected)",
            comparison["connected_before"],
            comparison["connected_after"],
        )

    return comparison
