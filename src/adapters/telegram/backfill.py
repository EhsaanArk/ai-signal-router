"""Signal backfill on listener reconnect.

Fetches and enqueues signals that were missed during Telegram listener
downtime (deploys, disconnects, crash recovery).  Operates on a
best-effort basis — no backfill is always safer than wrong backfill.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

import sentry_sdk
from telethon.errors import FloodWaitError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import GlobalSettingModel
from src.adapters.telegram.listener import TelegramListener
from src.adapters.telegram.repository import TelegramSessionRepository, _capture_user_exception
from src.core.interfaces import QueuePort
from src.core.models import RawSignal

logger = logging.getLogger(__name__)

# Backfill: env-var fallback for max age (seconds).  DB setting takes priority.
_BACKFILL_MAX_AGE_SECONDS_DEFAULT = int(os.environ.get("BACKFILL_MAX_AGE_SECONDS", "60"))

# Backfill: max messages to fetch per channel from Telegram history.
BACKFILL_MESSAGE_LIMIT = int(os.environ.get("BACKFILL_MESSAGE_LIMIT", "5"))

# Backfill: delay (seconds) between consecutive enqueue calls to avoid
# overwhelming QStash's daily message limit during burst backfill operations.
BACKFILL_ENQUEUE_DELAY = float(os.environ.get("BACKFILL_ENQUEUE_DELAY", "0.5"))


async def get_backfill_max_age(db: AsyncSession | None) -> int:
    """Read backfill_max_age_seconds from global_settings, fall back to env var."""
    if db is not None:
        try:
            result = await db.execute(
                select(GlobalSettingModel.value).where(
                    GlobalSettingModel.key == "backfill_max_age_seconds"
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                return int(row)
        except Exception:
            logger.debug("Failed to read backfill setting from DB, using env default")
    return _BACKFILL_MAX_AGE_SECONDS_DEFAULT


async def backfill_missed_signals(
    user_id: UUID,
    listener: TelegramListener,
    channels: set[str],
    repo: TelegramSessionRepository,
    queue_port: QueuePort,
    db: AsyncSession | None = None,
) -> None:
    """Fetch and enqueue signals that were missed during downtime.

    For each monitored channel:
    1. Query signal_logs for the highest message_id already processed.
    2. Fetch messages from Telegram with ID > last_seen_id.
    3. Filter out stale messages (older than BACKFILL_MAX_AGE_SECONDS).
    4. Enqueue fresh, unprocessed messages via the queue port.

    Parameters
    ----------
    user_id:
        The user whose channels are being backfilled.
    listener:
        The connected TelegramListener for this user.
    channels:
        Set of channel IDs to backfill.
    repo:
        Repository for DB queries (dedup, stale logging).
    queue_port:
        Queue for enqueuing recovered signals.
    """
    if not listener._client or not listener.is_connected:
        return

    total_backfilled = 0
    total_stale = 0
    total_duplicate = 0
    max_age = await get_backfill_max_age(db)
    cutoff = datetime.now(timezone.utc).timestamp() - max_age

    for channel_id in channels:
        try:
            # 1. Find the last processed message_id for this channel+user
            last_seen_id = await repo.get_last_message_id(user_id, channel_id)

            if last_seen_id is None:
                # No prior signal logs — skip (first-ever startup)
                logger.debug(
                    "Backfill: no prior logs for channel %s (user %s), skipping",
                    channel_id, user_id,
                )
                continue

            # 2. Fetch recent messages from Telegram history
            # Use PeerChannel for channels (bare int is ambiguous — Telethon
            # assumes user IDs).  Fall back to bare int for group chats.
            from telethon.tl.types import PeerChannel
            try:
                entity = await listener._client.get_entity(PeerChannel(int(channel_id)))
            except Exception:
                entity = await listener._client.get_entity(int(channel_id))
            messages = await listener._client.get_messages(
                entity,
                min_id=last_seen_id,
                limit=BACKFILL_MESSAGE_LIMIT,
            )

            if not messages:
                continue

            # 3. Collect message_ids to batch-check for duplicates
            candidate_ids = [
                m.id for m in messages
                if m.text and m.id > last_seen_id
            ]
            if not candidate_ids:
                continue

            already_processed = await repo.get_processed_message_ids(
                user_id, channel_id, candidate_ids,
            )

            # 4. Filter and enqueue
            for msg in messages:
                if not msg.text or msg.id <= last_seen_id:
                    continue

                if msg.id in already_processed:
                    total_duplicate += 1
                    continue

                # Staleness check using Telegram message timestamp
                if msg.date and msg.date.timestamp() < cutoff:
                    total_stale += 1
                    age_seconds = (
                        datetime.now(timezone.utc).timestamp()
                        - msg.date.timestamp()
                    )
                    logger.debug(
                        "Backfill: stale message %d in channel %s "
                        "(age=%.0fs, max=%ds)",
                        msg.id, channel_id, age_seconds,
                        max_age,
                    )
                    await repo.log_stale_signal(
                        user_id=user_id,
                        message_id=msg.id,
                        channel_id=channel_id,
                        raw_message=msg.text,
                        error_message=(
                            f"stale_signal: {age_seconds:.0f}s delay "
                            f"exceeds {max_age}s threshold"
                        ),
                    )
                    continue

                # Build and enqueue the signal
                reply_to_id = None
                if msg.reply_to:
                    reply_to_id = msg.reply_to.reply_to_msg_id

                raw_signal = RawSignal(
                    user_id=user_id,
                    channel_id=channel_id,
                    raw_message=msg.text,
                    message_id=msg.id,
                    reply_to_msg_id=reply_to_id,
                    timestamp=datetime.now(timezone.utc),
                )

                try:
                    await queue_port.enqueue(raw_signal)
                    total_backfilled += 1
                    # Throttle enqueue rate to avoid hitting QStash's daily
                    # message limit during burst backfill across many users.
                    await asyncio.sleep(BACKFILL_ENQUEUE_DELAY)
                except Exception as exc:
                    logger.error(
                        "Backfill: failed to enqueue message %d "
                        "from channel %s: %s",
                        msg.id, channel_id, exc,
                    )
                    sentry_sdk.capture_exception(exc)

        except FloodWaitError as e:
            logger.warning(
                "Backfill: flood-wait %ds for channel %s (user %s), "
                "skipping remaining channels",
                e.seconds, channel_id, user_id,
            )
            _capture_user_exception(e, user_id)
            break  # Stop backfilling to avoid further rate-limiting
        except Exception as exc:
            logger.warning(
                "Backfill: error processing channel %s (user %s): %s",
                channel_id, user_id, exc,
            )
            _capture_user_exception(exc, user_id)
            continue  # Try next channel

    if total_backfilled or total_stale or total_duplicate:
        logger.info(
            "Backfill complete for user %s: "
            "%d enqueued, %d stale-filtered, %d duplicate-filtered",
            user_id, total_backfilled, total_stale, total_duplicate,
        )
