"""Utility for listing a user's Telegram channels and supergroups.

Uses a Redis cache to avoid opening a second Telegram connection while
the Listener service is already connected — which would trigger
AuthKeyDuplicatedError from Telegram.
"""

from __future__ import annotations

import json
import logging

from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError
from telethon.sessions import StringSession
from telethon.tl.types import Channel

logger = logging.getLogger(__name__)

# Cache channels for 10 minutes — avoids re-connecting to Telegram
# on every page load while the Listener holds the session.
CHANNEL_CACHE_TTL = 600


async def get_user_channels(
    api_id: int,
    api_hash: str,
    session_string: str,
    proxy: dict | None = None,
    cache=None,
    user_id: str | None = None,
) -> list[dict]:
    """Return a list of channels and supergroups the session user has joined.

    Each entry is a dict with ``channel_id`` (str) and ``channel_name`` (str).

    When *cache* is provided, returns cached results if available (avoids
    opening a competing Telegram connection while the Listener is active).
    """
    # Try cache first — avoids AuthKeyDuplicatedError when Listener is connected
    cache_key = f"channels:{user_id}" if user_id else None
    if cache and cache_key:
        try:
            cached = await cache.get(cache_key)
            if cached:
                logger.debug("Returning cached channels for user %s", user_id)
                return json.loads(cached)
        except Exception:
            pass

    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        proxy=proxy,
    )

    try:
        await client.connect()
    except AuthKeyDuplicatedError:
        logger.info(
            "AuthKeyDuplicatedError for user %s — Listener is active. "
            "Returning empty channel list (user should see channels after cache populates).",
            user_id,
        )
        # The Listener is connected with this session — we can't open a
        # second connection. Return empty list; the frontend will show
        # channels from routing rules instead.
        return []

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("Session is not authorised. Re-authenticate first.")

    channels: list[dict] = []
    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            # Only include channels and supergroups (megagroups)
            if isinstance(entity, Channel) and (entity.broadcast or entity.megagroup):
                channels.append(
                    {
                        "channel_id": str(entity.id),
                        "channel_name": entity.title or "",
                    }
                )
    finally:
        await client.disconnect()

    # Cache the result so subsequent page loads don't hit Telegram
    if cache and cache_key and channels:
        try:
            await cache.set(cache_key, json.dumps(channels), ttl_seconds=CHANNEL_CACHE_TTL)
        except Exception:
            pass

    return channels
