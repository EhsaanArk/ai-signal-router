"""Multi-user Telegram listener manager.

Orchestrates one ``TelegramListener`` per active user session so that
all registered users receive signals simultaneously within a single
Railway worker process.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import sentry_sdk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.adapters.db.models import RoutingRuleModel, TelegramSessionModel
from src.adapters.telegram.listener import TelegramListener
from src.core.interfaces import QueuePort
from src.core.security import decrypt_session_auto

logger = logging.getLogger(__name__)


def _capture_user_exception(exc: Exception, user_id: UUID) -> None:
    """Capture an exception to Sentry with per-user context.

    Uses ``new_scope`` so that user tags don't leak between concurrent
    listeners on the same event loop.
    """
    with sentry_sdk.new_scope() as scope:
        scope.set_user({"id": str(user_id)})
        scope.set_tag("user_id", str(user_id))
        scope.capture_exception(exc)


# After this many consecutive heartbeat failures the client is fully restarted.
MAX_CONSECUTIVE_FAILURES = 5

# How often (seconds) to refresh sessions, channels, and run heartbeat.
REFRESH_INTERVAL = 30

# Delay between starting individual user clients to avoid Telegram flood-wait.
STARTUP_STAGGER_SECONDS = 1.0


class MultiUserListenerManager:
    """Manage one :class:`TelegramListener` per active user session.

    Parameters
    ----------
    api_id:
        Telegram application API ID.
    api_hash:
        Telegram application API hash.
    queue_port:
        Shared ``QueuePort`` implementation for enqueuing intercepted messages.
    engine:
        SQLAlchemy async engine for database access.
    enc_key:
        Encryption key (bytes) for decrypting stored session strings.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        queue_port: QueuePort,
        engine: AsyncEngine,
        enc_key: bytes,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._queue_port = queue_port
        self._engine = engine
        self._enc_key = enc_key

        self._listeners: dict[UUID, TelegramListener] = {}
        self._monitored_channels: dict[UUID, set[str]] = {}
        self._failure_counts: dict[UUID, int] = {}
        self._refresh_task: asyncio.Task | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Load all active sessions and start a listener for each user."""
        self._running = True

        sessions = await self._load_active_sessions()
        logger.info(
            "Found %d active Telegram session(s) in database", len(sessions),
        )

        for i, (user_id, session_string) in enumerate(sessions):
            if i > 0:
                await asyncio.sleep(STARTUP_STAGGER_SECONDS)
            await self._start_listener_for_user(user_id, session_string)

        logger.info(
            "Multi-user listener manager started: %d listener(s) active",
            len(self._listeners),
        )

        self._refresh_task = asyncio.create_task(
            self._refresh_loop(), name="listener-manager-refresh",
        )

    async def stop(self) -> None:
        """Gracefully stop all listeners and the refresh loop."""
        self._running = False

        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        if self._listeners:
            logger.info("Stopping %d listener(s)...", len(self._listeners))
            await asyncio.gather(
                *[l.stop() for l in self._listeners.values()],
                return_exceptions=True,
            )
            self._listeners.clear()
            self._monitored_channels.clear()
            self._failure_counts.clear()

        logger.info("Multi-user listener manager stopped.")

    def get_status(self) -> dict:
        """Return a health summary dict (useful for admin endpoints)."""
        return {
            "total_listeners": len(self._listeners),
            "connected_listeners": sum(
                1 for l in self._listeners.values()
                if l._client and l._client.is_connected()
            ),
            "total_monitored_channels": sum(
                len(ch) for ch in self._monitored_channels.values()
            ),
            "users": {
                str(uid): {
                    "connected": (
                        l._client is not None and l._client.is_connected()
                    ),
                    "channels": len(self._monitored_channels.get(uid, set())),
                    "failure_count": self._failure_counts.get(uid, 0),
                }
                for uid, l in self._listeners.items()
            },
        }

    # ------------------------------------------------------------------
    # Internal: per-user lifecycle
    # ------------------------------------------------------------------

    async def _start_listener_for_user(
        self, user_id: UUID, session_string: str,
    ) -> bool:
        """Create, start, and register a listener for a single user.

        Returns True on success, False on failure.
        """
        if user_id in self._listeners:
            logger.debug("Listener already active for user %s, skipping", user_id)
            return True

        listener = TelegramListener(
            api_id=self._api_id,
            api_hash=self._api_hash,
            queue_port=self._queue_port,
        )

        try:
            await listener.start(user_id, session_string)
        except Exception as exc:
            logger.error(
                "Failed to start listener for user %s: %s", user_id, exc,
            )
            _capture_user_exception(exc, user_id)
            return False

        # Load monitored channels for this user
        channels = await self._load_monitored_channels(user_id)
        listener.update_monitored_channels(channels)

        self._listeners[user_id] = listener
        self._monitored_channels[user_id] = channels
        self._failure_counts[user_id] = 0

        logger.info(
            "Listener started for user %s — monitoring %d channel(s)",
            user_id, len(channels),
        )
        return True

    async def _stop_listener_for_user(self, user_id: UUID) -> None:
        """Stop and remove the listener for a single user."""
        listener = self._listeners.pop(user_id, None)
        self._monitored_channels.pop(user_id, None)
        self._failure_counts.pop(user_id, None)

        if listener:
            try:
                await listener.stop()
            except Exception as exc:
                logger.error(
                    "Error stopping listener for user %s: %s", user_id, exc,
                )
                _capture_user_exception(exc, user_id)

        logger.info("Listener stopped for user %s", user_id)

    async def _restart_listener_for_user(self, user_id: UUID) -> None:
        """Stop and restart a listener from scratch (re-reads session from DB)."""
        logger.warning("Restarting listener for user %s", user_id)
        await self._stop_listener_for_user(user_id)

        # Re-load the session from DB
        try:
            async with AsyncSession(self._engine, expire_on_commit=False) as db:
                row = (
                    await db.execute(
                        select(TelegramSessionModel).where(
                            TelegramSessionModel.user_id == user_id,
                            TelegramSessionModel.is_active.is_(True),
                        ).limit(1)
                    )
                ).scalar_one_or_none()

            if row is None:
                logger.warning(
                    "No active session for user %s after restart attempt", user_id,
                )
                return

            session_string = decrypt_session_auto(
                row.session_string_encrypted, self._enc_key,
            )
            await self._start_listener_for_user(user_id, session_string)
        except Exception as exc:
            logger.error("Restart failed for user %s: %s", user_id, exc)
            _capture_user_exception(exc, user_id)

    # ------------------------------------------------------------------
    # Internal: refresh loop (sessions, channels, heartbeat)
    # ------------------------------------------------------------------

    async def _refresh_loop(self) -> None:
        """Periodically sync sessions, refresh channels, and check heartbeats."""
        while self._running:
            await asyncio.sleep(REFRESH_INTERVAL)
            if not self._running:
                break

            try:
                await self._sync_sessions()
            except Exception as exc:
                logger.exception("Error during session sync")
                sentry_sdk.capture_exception(exc)

            try:
                await self._refresh_all_channels()
            except Exception as exc:
                logger.exception("Error refreshing monitored channels")
                sentry_sdk.capture_exception(exc)

            await self._heartbeat()

    async def _sync_sessions(self) -> None:
        """Detect newly added or removed user sessions."""
        sessions = await self._load_active_sessions()
        active_user_ids = {uid for uid, _ in sessions}
        current_user_ids = set(self._listeners.keys())

        # Start listeners for new users
        new_users = active_user_ids - current_user_ids
        for user_id, session_string in sessions:
            if user_id in new_users:
                logger.info("New active session detected for user %s", user_id)
                await self._start_listener_for_user(user_id, session_string)
                await asyncio.sleep(STARTUP_STAGGER_SECONDS)

        # Stop listeners for removed/deactivated users
        removed_users = current_user_ids - active_user_ids
        for user_id in removed_users:
            logger.info("Session deactivated for user %s", user_id)
            await self._stop_listener_for_user(user_id)

    async def _refresh_all_channels(self) -> None:
        """Refresh monitored channels for all active listeners."""
        for user_id, listener in list(self._listeners.items()):
            try:
                updated = await self._load_monitored_channels(user_id)
                if updated != self._monitored_channels.get(user_id, set()):
                    listener.update_monitored_channels(updated)
                    self._monitored_channels[user_id] = updated
            except Exception as exc:
                logger.error(
                    "Failed to refresh channels for user %s: %s", user_id, exc,
                )

    async def _heartbeat(self) -> None:
        """Check connectivity and attempt reconnect for disconnected clients."""
        connected = 0
        total = len(self._listeners)

        for user_id, listener in list(self._listeners.items()):
            if listener._client and listener._client.is_connected():
                connected += 1
                self._failure_counts[user_id] = 0
                continue

            # Client is disconnected
            self._failure_counts[user_id] = self._failure_counts.get(user_id, 0) + 1
            failures = self._failure_counts[user_id]

            if failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "User %s: %d consecutive failures — full restart",
                    user_id, failures,
                )
                await self._restart_listener_for_user(user_id)
                continue

            logger.warning(
                "User %s: client disconnected (failure %d/%d), attempting reconnect",
                user_id, failures, MAX_CONSECUTIVE_FAILURES,
            )
            try:
                await listener._client.connect()
                await listener._client.get_dialogs()
                self._failure_counts[user_id] = 0
                connected += 1
                logger.info("Reconnected user %s successfully", user_id)
            except Exception as exc:
                logger.error("Reconnect failed for user %s: %s", user_id, exc)
                _capture_user_exception(exc, user_id)

        logger.info(
            "Heartbeat: %d/%d listeners connected, %d total channels monitored",
            connected,
            total,
            sum(len(ch) for ch in self._monitored_channels.values()),
        )

    # ------------------------------------------------------------------
    # Internal: database helpers
    # ------------------------------------------------------------------

    async def _load_active_sessions(self) -> list[tuple[UUID, str]]:
        """Load and decrypt all active Telegram sessions from the database.

        Returns a list of ``(user_id, decrypted_session_string)`` tuples.
        """
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(TelegramSessionModel).where(
                    TelegramSessionModel.is_active.is_(True),
                )
            )
            rows = result.scalars().all()

        sessions: list[tuple[UUID, str]] = []
        for row in rows:
            try:
                plain = decrypt_session_auto(
                    row.session_string_encrypted, self._enc_key,
                )
                sessions.append((row.user_id, plain))
            except Exception as exc:
                logger.error(
                    "Failed to decrypt session for user %s: %s",
                    row.user_id, exc,
                )
                _capture_user_exception(exc, row.user_id)

        return sessions

    async def _load_monitored_channels(self, user_id: UUID) -> set[str]:
        """Load distinct monitored channel IDs for a single user."""
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(RoutingRuleModel.source_channel_id).where(
                    RoutingRuleModel.user_id == user_id,
                    RoutingRuleModel.is_active.is_(True),
                ).distinct()
            )
            return {row[0] for row in result.all()}
