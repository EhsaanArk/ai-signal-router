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

import sentry_sdk
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from src.adapters.telemetry import get_tracer
from src.core.interfaces import QueuePort
from src.core.models import RawSignal

logger = logging.getLogger(__name__)
tracer = get_tracer("telegram.listener")


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
        proxy: dict | None = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._queue_port = queue_port
        self._get_session = get_session
        self._client: TelegramClient | None = None
        self._user_id: UUID | None = None
        self._monitored_channels: set[str] = monitored_channels or set()
        self._proxy = proxy

    async def start(
        self,
        user_id: UUID,
        session_string: str,
        monitored_channels: set[str] | None = None,
    ) -> None:
        """Connect to Telegram and start listening for new messages.

        Parameters
        ----------
        user_id:
            The application user who owns this Telegram session.
        session_string:
            A Telethon ``StringSession`` token.
        monitored_channels:
            Optional set of channel IDs to pre-fetch into Telethon's entity
            cache.  When provided, only these channels are fetched (lightweight)
            instead of the full dialog list (heavy, triggers flood-wait).
        """
        self._user_id = user_id
        self._client = TelegramClient(
            StringSession(session_string),
            self._api_id,
            self._api_hash,
            connection_retries=5,
            retry_delay=1,
            auto_reconnect=True,
            proxy=self._proxy,
        )
        await self._client.connect()

        if not await self._client.is_user_authorized():
            raise RuntimeError(
                f"Session for user {user_id} is not authorised. "
                "Re-authenticate via the auth flow."
            )

        # Force Telethon to fetch initial state so it can receive updates.
        me = await self._client.get_me()
        logger.info("Authenticated as %s (id=%s)", me.username or me.phone, me.id)

        # Register the new-message event handler.
        # Listen to all messages (not just incoming) because the user's own
        # messages in channels they admin are classified as outgoing by Telethon.
        self._client.add_event_handler(
            self._on_new_message,
            events.NewMessage(),
        )
        self._client.add_event_handler(
            self._on_new_message,
            events.MessageEdited(),
        )

        # Prime Telethon's entity cache so it can deserialise incoming updates.
        # When we know which channels to monitor, fetch only those entities
        # (lightweight) instead of the full dialog list (heavy, flood-wait prone).
        #
        # IMPORTANT: bare integer IDs are ambiguous — Telethon assumes they are
        # user IDs.  For channels/supergroups we must pass PeerChannel(bare_id)
        # so Telethon constructs the correct marked ID (-100XXXXXXXXXX).
        if monitored_channels:
            from telethon.tl.types import PeerChannel

            for ch_id in monitored_channels:
                try:
                    # Try as a channel first (most common for signal sources)
                    await self._client.get_entity(PeerChannel(int(ch_id)))
                except Exception:
                    # Fall back to bare int (might be a user/group chat)
                    try:
                        await self._client.get_entity(int(ch_id))
                    except Exception:
                        logger.warning(
                            "Could not pre-fetch entity for channel %s (user %s) "
                            "— messages will still be processed via ID matching",
                            ch_id, user_id,
                        )
        else:
            await self._client.get_dialogs()

        logger.info("Telegram listener started for user %s (new messages + edits)", user_id)

    async def _on_new_message(self, event: events.NewMessage.Event) -> None:
        """Handle an incoming Telegram message."""
        if self._user_id is None:
            return

        message = event.message
        if not message.text:
            return

        # Build the channel identifier — use the chat ID as a string.
        # get_chat() can fail if the entity cache is stale or the channel
        # was deleted, so we fall back to abs(event.chat_id).
        try:
            chat = await event.get_chat()
        except Exception as exc:
            logger.warning(
                "Could not resolve chat for event (chat_id=%s): %s",
                event.chat_id, exc,
            )
            sentry_sdk.capture_exception(exc)
            chat = None
        # Always use the bare (unmarked) ID to match the DB format.
        # event.chat_id for channels is "marked": -100XXXXXXXXXX.
        # abs() only strips the minus sign, NOT the 100 prefix.
        # Telethon's resolve_id() correctly extracts the bare ID.
        if chat:
            channel_id = str(chat.id)
        else:
            from telethon.utils import resolve_id
            bare_id, _ = resolve_id(event.chat_id)
            channel_id = str(bare_id)

        # Skip channels the user hasn't configured routing rules for.
        # When _monitored_channels is empty no channel should pass through —
        # this prevents processing ALL messages before routing rules exist.
        if channel_id not in self._monitored_channels:
            logger.info(
                "Skipping message from unmonitored channel %s (chat=%s)",
                channel_id,
                getattr(chat, 'title', None)
                or getattr(chat, 'first_name', 'unknown'),
            )
            return
        logger.info("Message from monitored channel %s (msg_id=%s)", channel_id, message.id)

        reply_to_id = None
        if message.reply_to:
            reply_to_id = message.reply_to.reply_to_msg_id

        raw_signal = RawSignal(
            user_id=self._user_id,
            channel_id=channel_id,
            raw_message=message.text,
            message_id=message.id,
            reply_to_msg_id=reply_to_id,
            timestamp=datetime.now(timezone.utc),
        )

        with tracer.start_as_current_span("telegram.enqueue") as span:
            span.set_attribute("telegram.channel_id", channel_id)
            span.set_attribute("telegram.message_id", message.id)
            try:
                await self._queue_port.enqueue(raw_signal)
                logger.debug(
                    "Enqueued message %d from channel %s",
                    message.id,
                    channel_id,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to enqueue message %d from channel %s",
                    message.id,
                    channel_id,
                )
                sentry_sdk.capture_exception(exc)

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the underlying Telethon client is connected."""
        return self._client is not None and self._client.is_connected()

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

    # Initialise Sentry for the listener process
    sentry_dsn = os.environ.get("SENTRY_DSN", "")
    if sentry_dsn:
        import sentry_sdk

        local_mode_env = os.environ.get("LOCAL_MODE", "false").lower() == "true"
        sentry_env = os.environ.get(
            "SENTRY_ENVIRONMENT",
            "development" if local_mode_env else "staging",
        )
        sentry_sdk.init(
            dsn=sentry_dsn,
            send_default_pii=True,
            traces_sample_rate=0.1,
            environment=sentry_env,
            server_name="sgm-listener",
        )
        sentry_sdk.set_tag("service.role", "listener")
        logger.info("Sentry initialised (role=listener)")

    async def _main() -> None:
        from src.adapters.telegram import parse_proxy_url

        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        local_mode = os.environ.get("LOCAL_MODE", "false").lower() == "true"
        proxy = parse_proxy_url(os.environ.get("TELEGRAM_PROXY_URL"))

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
                qstash_url=os.environ.get("QSTASH_URL", ""),
            )

        # -- Resolve session mode -----------------------------------------------
        from src.adapters.db.session import get_engine
        from src.adapters.db.models import TelegramSessionModel, RoutingRuleModel
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession as SASession
        from src.core.security import decrypt_session_auto

        engine = get_engine()

        user_id_env = os.environ.get("LISTENER_USER_ID")
        session_string_env = os.environ.get("TELEGRAM_SESSION_STRING")

        if user_id_env and session_string_env:
            # ── Single-user override mode (backward compatible) ──────────
            user_id = UUID(user_id_env)
            session_string = session_string_env

            async def _load_monitored_channels() -> set[str]:
                async with SASession(engine, expire_on_commit=False) as db:
                    result = await db.execute(
                        select(RoutingRuleModel.source_channel_id).where(
                            RoutingRuleModel.user_id == user_id,
                            RoutingRuleModel.is_active.is_(True),
                        ).distinct()
                    )
                    return {row[0] for row in result.all()}

            monitored = await _load_monitored_channels()
            logger.info("Single-user mode: monitoring %d channel(s): %s", len(monitored), monitored)

            listener = TelegramListener(
                api_id=api_id,
                api_hash=api_hash,
                queue_port=queue,
                monitored_channels=monitored,
                proxy=proxy,
            )

            await listener.start(user_id, session_string)

            logger.info("Listener running (single-user). Press Ctrl+C to stop.")
            try:
                while True:
                    await asyncio.sleep(60)
                    try:
                        updated = await _load_monitored_channels()
                        if updated != listener._monitored_channels:
                            listener.update_monitored_channels(updated)
                    except Exception as exc:
                        logger.exception("Failed to refresh monitored channels")
                        sentry_sdk.capture_exception(exc)

                    if listener._client and listener._client.is_connected():
                        logger.info(
                            "Heartbeat: listener alive, monitoring %d channel(s)",
                            len(listener._monitored_channels),
                        )
                    else:
                        logger.warning("Heartbeat: Telethon client disconnected, attempting reconnect...")
                        try:
                            await listener._client.connect()
                            for ch_id in listener._monitored_channels:
                                try:
                                    await listener._client.get_entity(int(ch_id))
                                except Exception:
                                    pass
                            logger.info("Reconnected successfully")
                        except Exception as exc:
                            logger.exception("Reconnect failed")
                            sentry_sdk.capture_exception(exc)
            except (KeyboardInterrupt, asyncio.CancelledError):
                await listener.stop()
        else:
            # ── Multi-user mode (SaaS) ───────────────────────────────────
            from src.adapters.telegram.manager import MultiUserListenerManager
            from src.adapters.proxy import get_proxy_provider
            import signal

            enc_key = os.environ["ENCRYPTION_KEY"].encode()

            # Optional email notifier for disconnect alerts
            email_notifier = None
            resend_key = os.environ.get("RESEND_API_KEY", "")
            if resend_key:
                from src.adapters.email.sender import ResendNotifier
                email_notifier = ResendNotifier(api_key=resend_key)

            # Per-user proxy provider (IPRoyal) with global proxy fallback
            proxy_provider = get_proxy_provider()

            manager = MultiUserListenerManager(
                api_id=api_id,
                api_hash=api_hash,
                queue_port=queue,
                engine=engine,
                enc_key=enc_key,
                email_notifier=email_notifier,
                proxy=proxy,
                proxy_provider=proxy_provider,
            )

            logger.info("Starting multi-user listener manager...")
            await manager.start()

            # ── Post-startup deploy health self-check ─────────────────────
            # Compare current state against the pre-shutdown snapshot saved
            # by the previous container (if any).  This detects session loss
            # caused by AuthKeyDuplicatedError during rolling deploys.
            redis_url = os.environ.get("REDIS_URL", "")
            if redis_url:
                from src.adapters.redis.client import RedisCacheAdapter
                import redis.asyncio as aioredis
                from src.adapters.telegram.deploy_snapshot import (
                    run_post_startup_check,
                )

                _check_redis = aioredis.from_url(redis_url, decode_responses=True)
                _check_cache = RedisCacheAdapter(_check_redis)
                try:
                    await run_post_startup_check(
                        _check_cache,
                        manager._listeners,
                        manager._monitored_channels,
                    )
                except Exception as exc:
                    logger.warning("Post-startup health check failed: %s", exc)
                finally:
                    _close = getattr(_check_redis, "aclose", None) or _check_redis.close
                    await _close()

            # ── Graceful shutdown on SIGTERM ──────────────────────────────
            # Railway sends SIGTERM before replacing the container.  We must
            # disconnect all Telethon clients BEFORE the process exits so
            # that Telegram session auth keys are cleanly released.  Without
            # this, the new container's connections trigger
            # AuthKeyDuplicatedError and invalidate user sessions.
            #
            #   SIGTERM received
            #     → save pre-shutdown snapshot to Redis
            #     → manager.stop() disconnects all Telethon clients
            #     → sessions released cleanly
            #     → new container connects without conflict
            #     → new container compares snapshot → logs deploy health
            #     → backfill recovers any signals missed during the gap
            shutdown_event = asyncio.Event()
            loop = asyncio.get_running_loop()

            def _on_signal(sig_name: str) -> None:
                logger.info("Received %s — initiating graceful shutdown...", sig_name)
                shutdown_event.set()

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, _on_signal, sig.name)

            logger.info("Multi-user listener running. Press Ctrl+C to stop.")
            try:
                await shutdown_event.wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                # ── Save pre-shutdown snapshot to Redis ────────────────────
                if redis_url:
                    from src.adapters.telegram.deploy_snapshot import (
                        save_pre_shutdown_snapshot,
                    )

                    await save_pre_shutdown_snapshot(
                        redis_url,
                        manager._listeners,
                        manager._monitored_channels,
                    )

                logger.info("Shutting down — disconnecting all Telegram clients...")
                try:
                    # Give manager 23s to disconnect all clients.  Railway
                    # sends SIGKILL after gracefulShutdownTimeoutSeconds (30s
                    # in railway.toml).  The snapshot write + 2s buffer
                    # accounts for the remaining time.
                    await asyncio.wait_for(manager.stop(), timeout=23.0)
                    logger.info("All clients disconnected. Exiting cleanly.")
                except asyncio.TimeoutError:
                    logger.warning(
                        "Shutdown timed out after 23s — "
                        "some clients may not have disconnected cleanly."
                    )

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
