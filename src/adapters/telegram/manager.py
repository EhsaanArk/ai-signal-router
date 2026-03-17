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
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from telethon.errors import FloodWaitError

from src.adapters.db.models import RoutingRuleModel, TelegramSessionModel, UserModel
from src.adapters.telegram.listener import TelegramListener
from src.core.interfaces import QueuePort
from src.core.notifications import NotificationPreference
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

# Max concurrent listener startups (limits parallel get_dialogs() calls).
MAX_CONCURRENT_STARTUPS = 3


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
        email_notifier: object | None = None,
        proxy: dict | None = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._queue_port = queue_port
        self._engine = engine
        self._enc_key = enc_key
        self._proxy = proxy
        self._email_notifier = email_notifier

        self._listeners: dict[UUID, TelegramListener] = {}
        self._monitored_channels: dict[UUID, set[str]] = {}
        self._failure_counts: dict[UUID, int] = {}
        self._refresh_task: asyncio.Task | None = None
        self._running = False
        self._startup_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STARTUPS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Load all active sessions and start a listener for each user."""
        self._running = True

        sessions = await self._load_active_sessions()
        all_channels = await self._load_all_monitored_channels()
        logger.info(
            "Found %d active Telegram session(s) in database", len(sessions),
        )

        async def _bounded_start(user_id: UUID, session_string: str) -> None:
            async with self._startup_semaphore:
                channels = all_channels.get(user_id, set())
                await self._start_listener_for_user(
                    user_id, session_string, channels,
                )

        await asyncio.gather(
            *[_bounded_start(uid, ss) for uid, ss in sessions],
            return_exceptions=True,
        )

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
                if l.is_connected
            ),
            "total_monitored_channels": sum(
                len(ch) for ch in self._monitored_channels.values()
            ),
            "users": {
                str(uid): {
                    "connected": l.is_connected,
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
        self,
        user_id: UUID,
        session_string: str,
        channels: set[str] | None = None,
    ) -> bool:
        """Create, start, and register a listener for a single user.

        Parameters
        ----------
        channels:
            Pre-loaded monitored channels.  When ``None`` (e.g. during a
            single-user restart) the channels are fetched from the database.

        Returns True on success, False on failure.
        """
        if user_id in self._listeners:
            logger.debug("Listener already active for user %s, skipping", user_id)
            return True

        listener = TelegramListener(
            api_id=self._api_id,
            api_hash=self._api_hash,
            queue_port=self._queue_port,
            proxy=self._proxy,
        )

        # Load channels if not pre-loaded (e.g. restart scenario)
        if channels is None:
            channels = await self._load_monitored_channels(user_id)

        try:
            await listener.start(user_id, session_string, monitored_channels=channels)
        except FloodWaitError as e:
            logger.warning(
                "User %s: flood-wait %ds on startup, retrying after delay",
                user_id, e.seconds,
            )
            await asyncio.sleep(e.seconds + 1)
            try:
                await listener.start(user_id, session_string, monitored_channels=channels)
            except Exception as retry_exc:
                logger.error(
                    "User %s: retry after flood-wait failed: %s",
                    user_id, retry_exc,
                )
                # Deactivate session if permanently invalid
                if isinstance(retry_exc, RuntimeError) and "not authorised" in str(retry_exc).lower():
                    await self._deactivate_session(user_id)
                _capture_user_exception(retry_exc, user_id)
                return False
        except RuntimeError as exc:
            if "not authorised" in str(exc).lower():
                logger.warning(
                    "Session expired for user %s — deactivating in DB",
                    user_id,
                )
                await self._deactivate_session(user_id)
            else:
                logger.error(
                    "Failed to start listener for user %s: %s", user_id, exc,
                )
            _capture_user_exception(exc, user_id)
            return False
        except Exception as exc:
            logger.error(
                "Failed to start listener for user %s: %s", user_id, exc,
            )
            _capture_user_exception(exc, user_id)
            return False

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

    async def _deactivate_session(
        self, user_id: UUID, reason: str = "session_expired",
    ) -> None:
        """Mark a user's Telegram session as inactive in the database.

        Called when a session is permanently invalid (e.g. revoked by the
        user in Telegram settings).  The user must re-authenticate via the
        frontend to create a new session.

        Parameters
        ----------
        reason:
            Why the session was deactivated.  Stored in the DB so the
            frontend can display a user-friendly explanation.  Valid values:
            ``session_expired``, ``flood_wait_exhausted``, ``decrypt_failed``,
            ``user_disconnected``.
        """
        try:
            async with AsyncSession(self._engine, expire_on_commit=False) as db:
                await db.execute(
                    update(TelegramSessionModel)
                    .where(TelegramSessionModel.user_id == user_id)
                    .values(
                        is_active=False,
                        disconnected_reason=reason,
                        disconnected_at=func.now(),
                    )
                )
                await db.commit()
            logger.warning(
                "Deactivated session for user %s (reason=%s) — user must re-authenticate",
                user_id, reason,
            )
        except Exception as exc:
            logger.error(
                "Failed to deactivate session for user %s: %s", user_id, exc,
            )
            return

        # Send email notification if configured
        if reason != "user_disconnected":
            asyncio.create_task(
                self._notify_disconnect(user_id, reason),
                name=f"notify-disconnect-{user_id}",
            )

    async def _notify_disconnect(self, user_id: UUID, reason: str) -> None:
        """Send a disconnect notification email if the user opted in."""
        if self._email_notifier is None:
            return
        try:
            async with AsyncSession(self._engine, expire_on_commit=False) as db:
                user = (
                    await db.execute(
                        select(UserModel).where(UserModel.id == user_id)
                    )
                ).scalar_one_or_none()
            if user is None:
                return

            prefs = NotificationPreference.model_validate(
                user.notification_preferences or {}
            )
            if not prefs.email_on_disconnect:
                return

            await self._email_notifier.send_disconnect_alert(
                user_email=user.email,
                reason=reason,
            )
        except Exception as exc:
            logger.error(
                "Failed to send disconnect notification for user %s: %s",
                user_id, exc,
            )

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

        # Start listeners for new users (bounded concurrency)
        new_users = active_user_ids - current_user_ids
        if new_users:
            new_sessions = [
                (uid, ss) for uid, ss in sessions if uid in new_users
            ]

            async def _bounded_start(uid: UUID, ss: str) -> None:
                async with self._startup_semaphore:
                    logger.info("New active session detected for user %s", uid)
                    await self._start_listener_for_user(uid, ss)

            await asyncio.gather(
                *[_bounded_start(uid, ss) for uid, ss in new_sessions],
                return_exceptions=True,
            )

        # Stop listeners for removed/deactivated users
        removed_users = current_user_ids - active_user_ids
        for user_id in removed_users:
            logger.info("Session deactivated for user %s", user_id)
            await self._stop_listener_for_user(user_id)

    async def _refresh_all_channels(self) -> None:
        """Refresh monitored channels for all active listeners (batch query)."""
        try:
            all_channels = await self._load_all_monitored_channels()
        except Exception as exc:
            logger.error("Failed to batch-load monitored channels: %s", exc)
            return

        for user_id, listener in list(self._listeners.items()):
            updated = all_channels.get(user_id, set())
            if updated != self._monitored_channels.get(user_id, set()):
                listener.update_monitored_channels(updated)
                self._monitored_channels[user_id] = updated

    async def _heartbeat(self) -> None:
        """Check connectivity and attempt reconnect for disconnected clients."""
        connected = 0
        total = len(self._listeners)

        for user_id, listener in list(self._listeners.items()):
            if listener.is_connected:
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
                # Re-prime entity cache for monitored channels only (lightweight)
                for ch_id in self._monitored_channels.get(user_id, set()):
                    try:
                        await listener._client.get_entity(int(ch_id))
                    except Exception:
                        pass
                self._failure_counts[user_id] = 0
                connected += 1
                logger.info("Reconnected user %s successfully", user_id)
            except FloodWaitError as e:
                logger.warning(
                    "User %s: flood-wait %ds during heartbeat reconnect",
                    user_id, e.seconds,
                )
                # Don't count as failure — Telegram is just rate-limiting
                self._failure_counts[user_id] = max(
                    self._failure_counts.get(user_id, 1) - 1, 0,
                )
                _capture_user_exception(e, user_id)
            except RuntimeError as exc:
                if "not authorised" in str(exc).lower():
                    logger.warning(
                        "User %s: session expired during reconnect — deactivating",
                        user_id,
                    )
                    await self._deactivate_session(user_id)
                    await self._stop_listener_for_user(user_id)
                else:
                    logger.error("Reconnect failed for user %s: %s", user_id, exc)
                _capture_user_exception(exc, user_id)
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

    async def _load_all_monitored_channels(self) -> dict[UUID, set[str]]:
        """Load monitored channels for ALL users in a single query.

        Returns a mapping of ``{user_id: {channel_id, ...}}``.
        """
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(
                    RoutingRuleModel.user_id,
                    RoutingRuleModel.source_channel_id,
                ).where(
                    RoutingRuleModel.is_active.is_(True),
                )
            )
            channels_map: dict[UUID, set[str]] = {}
            for user_id, channel_id in result.all():
                channels_map.setdefault(user_id, set()).add(channel_id)
            return channels_map
