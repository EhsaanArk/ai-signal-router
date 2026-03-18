"""Database helpers for the Telegram listener subsystem.

Centralises all SQL queries used by the multi-user listener manager so
that the manager itself stays focused on orchestration logic.
"""

from __future__ import annotations

import logging
from uuid import UUID

import sentry_sdk
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.adapters.db.models import (
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.core.notifications import NotificationPreference
from src.core.security import decrypt_session_auto

logger = logging.getLogger(__name__)


def _capture_user_exception(exc: Exception, user_id: UUID) -> None:
    """Capture an exception to Sentry with per-user context."""
    with sentry_sdk.new_scope() as scope:
        scope.set_user({"id": str(user_id)})
        scope.set_tag("user_id", str(user_id))
        scope.capture_exception(exc)


class TelegramSessionRepository:
    """Read/write operations for Telegram sessions and related queries.

    Parameters
    ----------
    engine:
        SQLAlchemy async engine.
    enc_key:
        Encryption key (bytes) for decrypting stored session strings.
    """

    def __init__(self, engine: AsyncEngine, enc_key: bytes) -> None:
        self._engine = engine
        self._enc_key = enc_key

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def load_active_sessions(self) -> list[tuple[UUID, str]]:
        """Load and decrypt all active Telegram sessions.

        Returns a list of ``(user_id, decrypted_session_string)`` tuples.
        Sessions that fail decryption are logged and skipped.
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

    async def load_session_for_user(self, user_id: UUID) -> str | None:
        """Load and decrypt a single user's active session string.

        Returns ``None`` if no active session exists.
        """
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
            return None

        return decrypt_session_auto(
            row.session_string_encrypted, self._enc_key,
        )

    async def deactivate_session(
        self, user_id: UUID, reason: str = "session_expired",
    ) -> None:
        """Mark a user's Telegram session as inactive.

        Parameters
        ----------
        reason:
            Why the session was deactivated.  Valid values:
            ``session_expired``, ``flood_wait_exhausted``,
            ``decrypt_failed``, ``user_disconnected``.
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
                "Deactivated session for user %s (reason=%s)",
                user_id, reason,
            )
        except Exception as exc:
            logger.error(
                "Failed to deactivate session for user %s: %s",
                user_id, exc,
            )

    # ------------------------------------------------------------------
    # Monitored channels
    # ------------------------------------------------------------------

    async def load_monitored_channels(self, user_id: UUID) -> set[str]:
        """Load distinct monitored channel IDs for a single user."""
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(RoutingRuleModel.source_channel_id).where(
                    RoutingRuleModel.user_id == user_id,
                    RoutingRuleModel.is_active.is_(True),
                ).distinct()
            )
            return {row[0] for row in result.all()}

    async def load_all_monitored_channels(self) -> dict[UUID, set[str]]:
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

    # ------------------------------------------------------------------
    # Signal logs (for backfill dedup)
    # ------------------------------------------------------------------

    async def get_last_message_id(
        self, user_id: UUID, channel_id: str,
    ) -> int | None:
        """Return the highest processed message_id for a channel+user."""
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(func.max(SignalLogModel.message_id)).where(
                    SignalLogModel.channel_id == channel_id,
                    SignalLogModel.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_processed_message_ids(
        self,
        user_id: UUID,
        channel_id: str,
        candidate_ids: list[int],
    ) -> set[int]:
        """Return the subset of *candidate_ids* already in signal_logs."""
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(SignalLogModel.message_id).where(
                    SignalLogModel.channel_id == channel_id,
                    SignalLogModel.user_id == user_id,
                    SignalLogModel.message_id.in_(candidate_ids),
                )
            )
            return {row[0] for row in result.all()}

    async def log_stale_signal(
        self,
        user_id: UUID,
        message_id: int,
        channel_id: str,
        raw_message: str,
        error_message: str,
    ) -> None:
        """Record a stale signal that was filtered during backfill."""
        try:
            async with AsyncSession(self._engine, expire_on_commit=False) as db:
                db.add(SignalLogModel(
                    user_id=user_id,
                    message_id=message_id,
                    channel_id=channel_id,
                    raw_message=raw_message,
                    status="ignored",
                    error_message=error_message,
                ))
                await db.commit()
        except Exception as exc:
            logger.debug(
                "Failed to log stale signal %d: %s", message_id, exc,
            )

    # ------------------------------------------------------------------
    # User queries (for notifications)
    # ------------------------------------------------------------------

    async def get_user_notification_prefs(
        self, user_id: UUID,
    ) -> tuple[str | None, NotificationPreference]:
        """Return ``(email, prefs)`` for a user, or ``(None, defaults)``."""
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            user = (
                await db.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
            ).scalar_one_or_none()

        if user is None:
            return None, NotificationPreference()

        prefs = NotificationPreference.model_validate(
            user.notification_preferences or {}
        )
        return user.email, prefs
