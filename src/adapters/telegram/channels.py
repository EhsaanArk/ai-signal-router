"""Utility for listing a user's Telegram channels and supergroups."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel


async def get_user_channels(
    api_id: int,
    api_hash: str,
    session_string: str,
    proxy: dict | None = None,
) -> list[dict]:
    """Return a list of channels and supergroups the session user has joined.

    Each entry is a dict with ``channel_id`` (str) and ``channel_name`` (str).

    Parameters
    ----------
    api_id:
        Telegram application API ID.
    api_hash:
        Telegram application API hash.
    session_string:
        A Telethon ``StringSession`` token for an authenticated user.
    """
    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        proxy=proxy,
    )
    await client.connect()

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

    return channels
