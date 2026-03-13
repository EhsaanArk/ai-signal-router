"""Telegram listener adapter implementing the ``SignalSource`` protocol.

Connects to Telegram via Telethon's MTProto API and forwards every new
channel/supergroup message to the processing pipeline through a ``QueuePort``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable
from uuid import UUID

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from src.core.interfaces import QueuePort
from src.core.models import RawSignal

logger = logging.getLogger(__name__)


class TelegramListener:
    """Real-time Telegram message listener.

    Parameters
    ----------
    api_id:
        Telegram application API ID.
    api_hash:
        Telegram application API hash.
    queue_port:
        A ``QueuePort`` implementation used to enqueue intercepted messages.
    get_session:
        An async callable that returns a mapping of ``{user_id: session_string}``
        pairs.  Used when starting the listener in standalone mode.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        queue_port: QueuePort,
        get_session: Callable[[], Awaitable[dict[UUID, str]]] | None = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._queue_port = queue_port
        self._get_session = get_session
        self._client: TelegramClient | None = None
        self._user_id: UUID | None = None

    async def start(self, user_id: UUID, session_string: str) -> None:
        """Connect to Telegram and start listening for new messages.

        Parameters
        ----------
        user_id:
            The application user who owns this Telegram session.
        session_string:
            A Telethon ``StringSession`` token.
        """
        self._user_id = user_id
        self._client = TelegramClient(
            StringSession(session_string),
            self._api_id,
            self._api_hash,
        )
        await self._client.connect()

        if not await self._client.is_user_authorized():
            raise RuntimeError(
                f"Session for user {user_id} is not authorised. "
                "Re-authenticate via the auth flow."
            )

        # Register the new-message event handler
        self._client.add_event_handler(
            self._on_new_message,
            events.NewMessage(incoming=True),
        )

        logger.info("Telegram listener started for user %s", user_id)

    async def _on_new_message(self, event: events.NewMessage.Event) -> None:
        """Handle an incoming Telegram message."""
        if self._user_id is None:
            return

        message = event.message
        if not message.text:
            return

        # Build the channel identifier — use the chat ID as a string
        chat = await event.get_chat()
        channel_id = str(chat.id) if chat else str(event.chat_id)

        raw_signal = RawSignal(
            user_id=self._user_id,
            channel_id=channel_id,
            raw_message=message.text,
            message_id=message.id,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            await self._queue_port.enqueue(raw_signal)
            logger.debug(
                "Enqueued message %d from channel %s",
                message.id,
                channel_id,
            )
        except Exception:
            logger.exception(
                "Failed to enqueue message %d from channel %s",
                message.id,
                channel_id,
            )

    async def stop(self) -> None:
        """Disconnect from Telegram and stop listening."""
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
            logger.info("Telegram listener stopped for user %s", self._user_id)


# ---------------------------------------------------------------------------
# Standalone entrypoint (for docker-compose listener service)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from src.adapters.qstash.publisher import QStashPublisher, LocalQueueAdapter

    async def _main() -> None:
        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        local_mode = os.environ.get("LOCAL_MODE", "false").lower() == "true"

        # In production, publish to QStash; locally, process in-process.
        if local_mode:
            # Import inline to avoid circular deps in production path
            from src.adapters.openai.parser import OpenAISignalParser

            parser = OpenAISignalParser(api_key=os.environ["OPENAI_API_KEY"])

            async def _process(signal: RawSignal) -> None:
                result = await parser.parse(signal)
                logger.info("Parsed signal (local): %s", result)

            queue: QueuePort = LocalQueueAdapter(callback=_process)
        else:
            queue = QStashPublisher(
                qstash_token=os.environ["QSTASH_TOKEN"],
                workflow_url=os.environ["QSTASH_WORKFLOW_URL"],
            )

        listener = TelegramListener(
            api_id=api_id,
            api_hash=api_hash,
            queue_port=queue,
        )

        # For standalone mode, read session from env (single-user)
        user_id = UUID(os.environ["LISTENER_USER_ID"])
        session_string = os.environ["TELEGRAM_SESSION_STRING"]

        await listener.start(user_id, session_string)

        logger.info("Listener running. Press Ctrl+C to stop.")
        try:
            # Keep the event loop alive — Telethon handles events internally
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            await listener.stop()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
