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
        monitored_channels: set[str] | None = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._queue_port = queue_port
        self._get_session = get_session
        self._client: TelegramClient | None = None
        self._user_id: UUID | None = None
        self._monitored_channels: set[str] = monitored_channels or set()

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
            connection_retries=5,
            retry_delay=1,
            auto_reconnect=True,
        )
        await self._client.connect()

        if not await self._client.is_user_authorized():
            raise RuntimeError(
                f"Session for user {user_id} is not authorised. "
                "Re-authenticate via the auth flow."
            )

        # Register the new-message event handler.
        # Listen to all messages (not just incoming) because the user's own
        # messages in channels they admin are classified as outgoing by Telethon.
        self._client.add_event_handler(
            self._on_new_message,
            events.NewMessage(),
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
        # Always use the bare (unmarked) ID to match channels.py format.
        # event.chat_id may include a -100 prefix; abs() strips it.
        channel_id = str(chat.id) if chat else str(abs(event.chat_id))

        # Skip channels the user hasn't configured routing rules for
        if self._monitored_channels and channel_id not in self._monitored_channels:
            logger.info(
                "Skipping message from unmonitored channel %s (chat=%s)",
                channel_id, chat.title if chat else "unknown",
            )
            return
        logger.info("Message from monitored channel %s: %.50s", channel_id, message.text)

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

    def update_monitored_channels(self, channels: set[str]) -> None:
        """Update the set of channel IDs this listener should process."""
        self._monitored_channels = channels
        logger.info("Monitored channels updated: %s", channels)

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

    import httpx

    from src.adapters.qstash.publisher import QStashPublisher, LocalQueueAdapter

    async def _main() -> None:
        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        local_mode = os.environ.get("LOCAL_MODE", "false").lower() == "true"

        # In production, publish to QStash; locally, POST to the co-located
        # API service so the full pipeline (parse → route → dispatch → log)
        # runs exactly as it does in production.
        if local_mode:
            api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
            workflow_endpoint = f"{api_base_url}/api/workflow/process-signal"
            http_client = httpx.AsyncClient(timeout=30.0)

            async def _process(signal: RawSignal) -> None:
                resp = await http_client.post(
                    workflow_endpoint,
                    json=signal.model_dump(mode="json"),
                )
                if resp.is_success:
                    logger.info("Signal processed via workflow: %s", resp.json())
                else:
                    logger.error(
                        "Workflow returned %d: %s", resp.status_code, resp.text
                    )

            queue: QueuePort = LocalQueueAdapter(callback=_process)
        else:
            queue = QStashPublisher(
                qstash_token=os.environ["QSTASH_TOKEN"],
                workflow_url=os.environ["QSTASH_WORKFLOW_URL"],
            )

        # -- Resolve session: prefer env vars, fall back to DB lookup ----------
        from src.adapters.db.session import get_engine
        from src.adapters.db.models import TelegramSessionModel, RoutingRuleModel
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession as SASession
        from cryptography.fernet import Fernet

        engine = get_engine()

        user_id_env = os.environ.get("LISTENER_USER_ID")
        session_string_env = os.environ.get("TELEGRAM_SESSION_STRING")

        if user_id_env and session_string_env:
            user_id = UUID(user_id_env)
            session_string = session_string_env
        else:
            logger.info("No LISTENER_USER_ID / TELEGRAM_SESSION_STRING in env; "
                        "querying DB for active session...")
            fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())
            async with SASession(engine, expire_on_commit=False) as db:
                stmt = select(TelegramSessionModel).where(
                    TelegramSessionModel.is_active.is_(True)
                ).limit(1)
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()
            if row is None:
                raise RuntimeError("No active Telegram session found in database.")
            user_id = row.user_id
            session_string = fernet.decrypt(row.session_string_encrypted.encode()).decode()
            logger.info("Loaded session for user %s from database.", user_id)

        # -- Load monitored channels from routing rules ----------------------
        async def _load_monitored_channels() -> set[str]:
            async with SASession(engine, expire_on_commit=False) as db:
                result = await db.execute(
                    select(RoutingRuleModel.source_channel_id).where(
                        RoutingRuleModel.user_id == user_id,
                        RoutingRuleModel.is_active.is_(True),
                    ).distinct()
                )
                channels = {row[0] for row in result.all()}
            return channels

        monitored = await _load_monitored_channels()
        logger.info("Monitoring %d channel(s): %s", len(monitored), monitored)

        listener = TelegramListener(
            api_id=api_id,
            api_hash=api_hash,
            queue_port=queue,
            monitored_channels=monitored,
        )

        await listener.start(user_id, session_string)

        logger.info("Listener running. Press Ctrl+C to stop.")
        try:
            # Periodically refresh monitored channels (every 60s)
            while True:
                await asyncio.sleep(60)
                try:
                    updated = await _load_monitored_channels()
                    if updated != listener._monitored_channels:
                        listener.update_monitored_channels(updated)
                except Exception:
                    logger.exception("Failed to refresh monitored channels")
        except (KeyboardInterrupt, asyncio.CancelledError):
            await listener.stop()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
