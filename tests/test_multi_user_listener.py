"""Tests for MultiUserListenerManager.

Verifies multi-user session orchestration, dynamic session sync,
channel refresh, heartbeat, error isolation, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.adapters.telegram.manager import (
    AUTH_CHECK_INTERVAL,
    MAX_CONSECUTIVE_FAILURES,
    MAX_STARTUP_RETRIES,
    MultiUserListenerManager,
)

FAKE_API_ID = 12345
FAKE_API_HASH = "abcdef1234567890abcdef1234567890"
FAKE_ENC_KEY = b"dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXk="  # 32 bytes b64

USER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_C = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

SESSION_A = "session_string_a"
SESSION_B = "session_string_b"
SESSION_C = "session_string_c"


def _make_manager(**overrides) -> MultiUserListenerManager:
    """Create a manager with mocked engine and default settings."""
    manager = MultiUserListenerManager(
        api_id=FAKE_API_ID,
        api_hash=FAKE_API_HASH,
        queue_port=AsyncMock(),
        engine=MagicMock(),
        enc_key=FAKE_ENC_KEY,
        **overrides,
    )
    # Replace the real repo with a mock so tests control DB responses
    manager._repo = MagicMock()
    manager._repo.load_active_sessions = AsyncMock(return_value=[])
    manager._repo.load_all_monitored_channels = AsyncMock(return_value={})
    manager._repo.load_monitored_channels = AsyncMock(return_value=set())
    manager._repo.load_session_for_user = AsyncMock(return_value=None)
    manager._repo.deactivate_session = AsyncMock()
    manager._repo.log_connection_event = AsyncMock()
    manager._repo.get_user_notification_prefs = AsyncMock(return_value=(None, MagicMock(email_on_disconnect=False)))
    return manager


def _mock_listener(connected: bool = True) -> MagicMock:
    """Create a mock TelegramListener with controllable connection state."""
    listener = AsyncMock()
    listener.start = AsyncMock()
    listener.stop = AsyncMock()
    listener.update_monitored_channels = MagicMock()
    # Expose the public is_connected property used by the manager
    listener.is_connected = connected
    # Keep _client for tests that verify reconnect behaviour
    listener._client = MagicMock()
    listener._client.is_connected.return_value = connected
    listener._client.connect = AsyncMock()
    listener._client.get_dialogs = AsyncMock()
    return listener


# =========================================================================
# Start — loads all active sessions
# =========================================================================


class TestManagerStart:
    """Tests for ``MultiUserListenerManager.start()``."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_starts_listener_for_each_active_session(self, MockListener):
        """Manager should create and start one listener per active session."""
        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A), (USER_B, SESSION_B)],
        )
        manager._repo.load_all_monitored_channels = AsyncMock(
            return_value={USER_A: {"123"}, USER_B: {"456"}},
        )

        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        await manager.start()

        assert len(manager._listeners) == 2
        assert USER_A in manager._listeners
        assert USER_B in manager._listeners
        assert mock_listener.start.await_count == 2

        # Cleanup
        manager._running = False
        if manager._refresh_task:
            manager._refresh_task.cancel()
            try:
                await manager._refresh_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_start_with_no_sessions(self, MockListener):
        """Manager should start gracefully with zero active sessions."""
        manager = _make_manager()

        await manager.start()

        assert len(manager._listeners) == 0
        MockListener.assert_not_called()

        manager._running = False
        if manager._refresh_task:
            manager._refresh_task.cancel()
            try:
                await manager._refresh_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_start_loads_monitored_channels_per_user(self, MockListener):
        """Each listener should receive its user's monitored channels."""
        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A)],
        )

        channels_a = {"111", "222"}
        manager._repo.load_all_monitored_channels = AsyncMock(
            return_value={USER_A: channels_a},
        )

        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        await manager.start()

        mock_listener.update_monitored_channels.assert_called_with(channels_a)
        assert manager._monitored_channels[USER_A] == channels_a

        manager._running = False
        if manager._refresh_task:
            manager._refresh_task.cancel()
            try:
                await manager._refresh_task
            except asyncio.CancelledError:
                pass


# =========================================================================
# Error isolation
# =========================================================================


class TestErrorIsolation:
    """One user's failure should not prevent others from starting."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_one_user_failure_does_not_block_others(self, MockListener):
        """If user A's session fails, user B should still start."""
        call_count = 0

        def _create_listener(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            listener = _mock_listener()
            if call_count == 1:
                # First listener (user A) fails to start
                listener.start = AsyncMock(
                    side_effect=RuntimeError("Session expired"),
                )
            return listener

        MockListener.side_effect = _create_listener

        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A), (USER_B, SESSION_B)],
        )

        await manager.start()

        # Only user B should be active (user A failed)
        assert USER_A not in manager._listeners
        assert USER_B in manager._listeners
        assert len(manager._listeners) == 1

        manager._running = False
        if manager._refresh_task:
            manager._refresh_task.cancel()
            try:
                await manager._refresh_task
            except asyncio.CancelledError:
                pass


# =========================================================================
# Session sync — detect new / removed sessions
# =========================================================================


class TestSessionSync:
    """Tests for ``_sync_sessions()``."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_detects_new_session(self, MockListener):
        """A newly active session should trigger listener creation."""
        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        manager = _make_manager()

        # Simulate: user A already running, user B is new
        manager._listeners[USER_A] = _mock_listener()
        manager._monitored_channels[USER_A] = set()
        manager._failure_counts[USER_A] = 0

        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A), (USER_B, SESSION_B)],
        )

        await manager._sync_sessions()

        assert USER_B in manager._listeners
        assert len(manager._listeners) == 2

    @pytest.mark.asyncio
    async def test_detects_removed_session(self):
        """A deactivated session should trigger listener removal."""
        manager = _make_manager()

        mock_listener_a = _mock_listener()
        mock_listener_b = _mock_listener()
        manager._listeners = {USER_A: mock_listener_a, USER_B: mock_listener_b}
        manager._monitored_channels = {USER_A: set(), USER_B: set()}
        manager._failure_counts = {USER_A: 0, USER_B: 0}

        # Only user A remains active
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A)],
        )

        await manager._sync_sessions()

        assert USER_A in manager._listeners
        assert USER_B not in manager._listeners
        mock_listener_b.stop.assert_awaited_once()


# =========================================================================
# Channel refresh
# =========================================================================


class TestChannelRefresh:
    """Tests for ``_refresh_all_channels()``."""

    @pytest.mark.asyncio
    async def test_updates_channels_when_changed(self):
        """Listener channels should be updated when routing rules change."""
        manager = _make_manager()

        mock_listener = _mock_listener()
        manager._listeners = {USER_A: mock_listener}
        manager._monitored_channels = {USER_A: {"old_channel"}}

        new_channels = {"new_channel_1", "new_channel_2"}
        manager._repo.load_all_monitored_channels = AsyncMock(
            return_value={USER_A: new_channels},
        )

        await manager._refresh_all_channels()

        mock_listener.update_monitored_channels.assert_called_with(new_channels)
        assert manager._monitored_channels[USER_A] == new_channels

    @pytest.mark.asyncio
    async def test_no_update_when_unchanged(self):
        """Listener should not be notified if channels haven't changed."""
        manager = _make_manager()

        mock_listener = _mock_listener()
        existing = {"ch1", "ch2"}
        manager._listeners = {USER_A: mock_listener}
        manager._monitored_channels = {USER_A: existing}

        manager._repo.load_all_monitored_channels = AsyncMock(
            return_value={USER_A: existing},
        )

        await manager._refresh_all_channels()

        mock_listener.update_monitored_channels.assert_not_called()


# =========================================================================
# Heartbeat
# =========================================================================


class TestHeartbeat:
    """Tests for ``_heartbeat()``."""

    @pytest.mark.asyncio
    async def test_connected_client_resets_failure_count(self):
        """A connected client should reset its failure counter to 0."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=True)
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 3}
        manager._monitored_channels = {USER_A: set()}

        await manager._heartbeat()

        assert manager._failure_counts[USER_A] == 0

    @pytest.mark.asyncio
    async def test_disconnected_client_increments_failure(self):
        """A disconnected client should have its failure count incremented."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=False)
        mock_listener._client.connect = AsyncMock()
        mock_listener._client.get_dialogs = AsyncMock()
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: set()}

        await manager._heartbeat()

        # After successful reconnect, failure count resets
        mock_listener._client.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_max_failures_triggers_restart(self):
        """Exceeding MAX_CONSECUTIVE_FAILURES should trigger a full restart."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=False)
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: MAX_CONSECUTIVE_FAILURES}
        manager._monitored_channels = {USER_A: set()}

        manager._restart_listener_for_user = AsyncMock()

        await manager._heartbeat()

        manager._restart_listener_for_user.assert_awaited_once_with(USER_A)

    @pytest.mark.asyncio
    async def test_heartbeat_flood_wait_handled_gracefully(self):
        """FloodWaitError during heartbeat reconnect should not crash or increment failures."""
        from telethon.errors import FloodWaitError

        manager = _make_manager()

        mock_listener = _mock_listener(connected=False)
        mock_listener._client.connect = AsyncMock(
            side_effect=FloodWaitError(request=None, capture=30),
        )
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: {"ch1"}}

        # Should not raise
        await manager._heartbeat()

        # Failure count should be decremented (or stay at 0), not incremented
        assert manager._failure_counts[USER_A] == 0

    @pytest.mark.asyncio
    async def test_heartbeat_not_authorised_deactivates_session(self):
        """Expired session during heartbeat should deactivate and stop listener."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=False)
        mock_listener._client.connect = AsyncMock(
            side_effect=RuntimeError(
                "Session for user xxx is not authorised. "
                "Re-authenticate via the auth flow."
            ),
        )
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: {"ch1"}}

        await manager._heartbeat()

        manager._repo.deactivate_session.assert_awaited_once_with(USER_A, "session_expired")

    @pytest.mark.asyncio
    async def test_parallel_heartbeat_handles_mixed_states(self):
        """Heartbeat should process multiple users in parallel correctly:
        connected, disconnected (reconnects), and max-failures (restarts)."""
        manager = _make_manager()

        # User A: connected (should reset failure count)
        listener_a = _mock_listener(connected=True)
        # User B: disconnected, will reconnect successfully
        listener_b = _mock_listener(connected=False)
        listener_b._client.connect = AsyncMock()
        # User C: at max failures, should trigger restart
        listener_c = _mock_listener(connected=False)

        manager._listeners = {
            USER_A: listener_a,
            USER_B: listener_b,
            USER_C: listener_c,
        }
        manager._failure_counts = {
            USER_A: 2,
            USER_B: 1,
            USER_C: MAX_CONSECUTIVE_FAILURES,
        }
        manager._monitored_channels = {
            USER_A: {"ch1"},
            USER_B: {"ch2"},
            USER_C: {"ch3"},
        }

        manager._restart_listener_for_user = AsyncMock()

        await manager._heartbeat()

        # User A: failure count reset
        assert manager._failure_counts[USER_A] == 0
        # User B: reconnected
        listener_b._client.connect.assert_awaited_once()
        # User C: full restart triggered
        manager._restart_listener_for_user.assert_awaited_once_with(USER_C)


# =========================================================================
# Proactive auth check
# =========================================================================


class TestProactiveAuthCheck:
    """Tests for proactive is_user_authorized() check in heartbeat.

    Auth checks are staggered per user: each user is assigned a slot
    based on ``hash(user_id) % AUTH_CHECK_INTERVAL``.
    """

    @staticmethod
    def _auth_check_heartbeat(user_id: UUID) -> int:
        """Return heartbeat_count that triggers auth check for this user."""
        slot = hash(user_id) % AUTH_CHECK_INTERVAL
        # _heartbeat() increments first, so set to (target - 1)
        return slot - 1 if slot > 0 else AUTH_CHECK_INTERVAL - 1

    @pytest.mark.asyncio
    async def test_detects_revoked_session(self):
        """A connected client whose session was revoked (is_user_authorized
        returns False) should be deactivated and stopped."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=True)
        mock_listener._client.is_user_authorized = AsyncMock(return_value=False)
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: {"ch1"}}

        # Set heartbeat count so auth check fires
        manager._heartbeat_count = self._auth_check_heartbeat(USER_A)

        await manager._heartbeat()

        manager._repo.deactivate_session.assert_awaited_once_with(USER_A, "session_expired")

    @pytest.mark.asyncio
    async def test_skips_on_non_check_cycle(self):
        """Auth check should NOT run when it's not this user's slot."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=True)
        mock_listener._client.is_user_authorized = AsyncMock(return_value=False)
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: {"ch1"}}

        # Set heartbeat count so auth check does NOT fire for USER_A
        # Use a slot that's offset from USER_A's slot
        user_slot = hash(USER_A) % AUTH_CHECK_INTERVAL
        other_slot = (user_slot + 1) % AUTH_CHECK_INTERVAL
        manager._heartbeat_count = other_slot - 1 if other_slot > 0 else AUTH_CHECK_INTERVAL - 1

        await manager._heartbeat()

        # Auth check should not have been called
        mock_listener._client.is_user_authorized.assert_not_awaited()
        # Session should NOT be deactivated
        manager._repo.deactivate_session.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_auth_key_error(self):
        """Permanent AuthKeyError during proactive auth check should deactivate."""
        from telethon.errors import AuthKeyUnregisteredError

        manager = _make_manager()

        mock_listener = _mock_listener(connected=True)
        mock_listener._client.is_user_authorized = AsyncMock(
            side_effect=AuthKeyUnregisteredError(request=None),
        )
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: {"ch1"}}

        manager._heartbeat_count = self._auth_check_heartbeat(USER_A)

        await manager._heartbeat()

        manager._repo.deactivate_session.assert_awaited_once_with(USER_A, "session_expired")

    @pytest.mark.asyncio
    async def test_transient_error_does_not_deactivate(self):
        """A transient error during auth check (e.g., network timeout)
        should NOT deactivate the session — just log and continue."""
        manager = _make_manager()

        mock_listener = _mock_listener(connected=True)
        mock_listener._client.is_user_authorized = AsyncMock(
            side_effect=ConnectionError("timeout"),
        )
        manager._listeners = {USER_A: mock_listener}
        manager._failure_counts = {USER_A: 0}
        manager._monitored_channels = {USER_A: {"ch1"}}

        manager._heartbeat_count = self._auth_check_heartbeat(USER_A)

        await manager._heartbeat()

        # Should NOT deactivate — transient error
        manager._repo.deactivate_session.assert_not_awaited()


# =========================================================================
# Startup backoff
# =========================================================================


class TestStartupBackoff:
    """Tests for exponential startup backoff on persistent failures."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_skips_user_after_max_retries(self, MockListener):
        """A user with >MAX_STARTUP_RETRIES failures should be skipped
        on non-backoff cycles."""
        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A)],
        )
        # User A has failed 4 times (beyond MAX_STARTUP_RETRIES=3)
        manager._startup_failures = {USER_A: MAX_STARTUP_RETRIES + 1}
        # Heartbeat count does NOT align with backoff cycle
        manager._heartbeat_count = 1

        await manager._sync_sessions()

        # Listener should NOT have been created
        MockListener.assert_not_called()
        assert USER_A not in manager._listeners

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_retries_on_backoff_cycle(self, MockListener):
        """A user with >MAX_STARTUP_RETRIES failures should be retried
        when the heartbeat count aligns with the backoff schedule."""
        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A)],
        )
        # User A has failed 4 times — skip_cycles = (4-3+1)*10 = 20
        manager._startup_failures = {USER_A: MAX_STARTUP_RETRIES + 1}
        # Set heartbeat count to align with backoff cycle (divisible by 20)
        manager._heartbeat_count = 20

        await manager._sync_sessions()

        # Listener SHOULD have been created (retry on backoff cycle)
        assert mock_listener.start.await_count == 1

        # Cleanup
        manager._listeners.clear()

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_resets_on_success(self, MockListener):
        """Successful start should clear the startup failure count."""
        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        manager = _make_manager()
        manager._startup_failures = {USER_A: 5}

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels={"ch1"},
        )

        assert result is True
        assert USER_A not in manager._startup_failures

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_increments_on_failure(self, MockListener):
        """Failed start should increment the startup failure count."""
        mock_listener = _mock_listener()
        mock_listener.start = AsyncMock(side_effect=Exception("network error"))
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels=set(),
        )

        assert result is False
        assert manager._startup_failures[USER_A] == 1

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_no_backoff_within_max_retries(self, MockListener):
        """Users with fewer than MAX_STARTUP_RETRIES failures should
        always be retried (no backoff)."""
        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A)],
        )
        # 2 failures — below threshold
        manager._startup_failures = {USER_A: 2}
        manager._heartbeat_count = 1

        await manager._sync_sessions()

        # Should still attempt startup
        assert mock_listener.start.await_count == 1


# =========================================================================
# Graceful shutdown
# =========================================================================


class TestManagerStop:
    """Tests for ``MultiUserListenerManager.stop()``."""

    @pytest.mark.asyncio
    async def test_stop_disconnects_all_listeners(self):
        """stop() should call stop() on every active listener."""
        manager = _make_manager()
        manager._running = True

        mock_a = _mock_listener()
        mock_b = _mock_listener()
        manager._listeners = {USER_A: mock_a, USER_B: mock_b}
        manager._monitored_channels = {USER_A: set(), USER_B: set()}
        manager._failure_counts = {USER_A: 0, USER_B: 0}

        await manager.stop()

        mock_a.stop.assert_awaited_once()
        mock_b.stop.assert_awaited_once()
        assert len(manager._listeners) == 0
        assert not manager._running

    @pytest.mark.asyncio
    async def test_stop_cancels_refresh_task(self):
        """stop() should cancel the background refresh task."""
        manager = _make_manager()
        manager._running = True
        manager._refresh_task = asyncio.create_task(asyncio.sleep(9999))

        await manager.stop()

        assert manager._refresh_task.cancelled() or manager._refresh_task.done()


# =========================================================================
# get_status
# =========================================================================


class TestGetStatus:
    """Tests for ``get_status()``."""

    def test_status_reflects_current_state(self):
        """get_status() should accurately report listener state."""
        manager = _make_manager()

        connected_listener = _mock_listener(connected=True)
        disconnected_listener = _mock_listener(connected=False)

        manager._listeners = {USER_A: connected_listener, USER_B: disconnected_listener}
        manager._monitored_channels = {USER_A: {"ch1", "ch2"}, USER_B: {"ch3"}}
        manager._failure_counts = {USER_A: 0, USER_B: 2}

        status = manager.get_status()

        assert status["total_listeners"] == 2
        assert status["connected_listeners"] == 1
        assert status["total_monitored_channels"] == 3
        assert status["users"][str(USER_A)]["connected"] is True
        assert status["users"][str(USER_B)]["connected"] is False
        assert status["users"][str(USER_B)]["failure_count"] == 2


# =========================================================================
# Expired session deactivation
# =========================================================================


class TestExpiredSessionDeactivation:
    """Tests for auto-deactivating expired Telegram sessions."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_expired_session_is_deactivated(self, MockListener):
        """A 'not authorised' failure should trigger session deactivation."""
        mock_listener = _mock_listener()
        mock_listener.start = AsyncMock(
            side_effect=RuntimeError(
                "Session for user xxx is not authorised. Re-authenticate via the auth flow."
            ),
        )
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels=set(),
        )

        assert result is False
        manager._repo.deactivate_session.assert_awaited_once_with(USER_A, "session_expired")
        assert USER_A not in manager._listeners

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_non_auth_runtime_error_does_not_deactivate(self, MockListener):
        """A RuntimeError that isn't about auth should NOT deactivate the session."""
        mock_listener = _mock_listener()
        mock_listener.start = AsyncMock(
            side_effect=RuntimeError("Some other error"),
        )
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels=set(),
        )

        assert result is False
        manager._repo.deactivate_session.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_auth_key_duplicated_error_does_not_deactivate(
        self, MockListener, mock_sleep,
    ):
        """AuthKeyDuplicatedError is transient — should NOT deactivate.
        It increments startup_failures for backoff retry, not permanent kill."""
        from telethon.errors import AuthKeyDuplicatedError

        mock_listener = _mock_listener()
        mock_listener.start = AsyncMock(
            side_effect=AuthKeyDuplicatedError(request=None),
        )
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels=set(),
        )

        assert result is False
        # Should NOT deactivate — AuthKeyDuplicatedError is transient
        manager._repo.deactivate_session.assert_not_awaited()
        assert USER_A not in manager._listeners


# =========================================================================
# _is_session_dead helper
# =========================================================================


class TestIsSessionDead:
    """Tests for the _is_session_dead() helper function."""

    def test_auth_key_duplicated_is_transient(self):
        """AuthKeyDuplicatedError is transient — NOT a dead session."""
        from telethon.errors import AuthKeyDuplicatedError
        from src.adapters.telegram.manager import _is_session_dead

        assert _is_session_dead(AuthKeyDuplicatedError(request=None)) is False

    def test_not_authorised_runtime_error_is_dead(self):
        """RuntimeError with 'not authorised' message should be dead."""
        from src.adapters.telegram.manager import _is_session_dead

        exc = RuntimeError("Session for user xxx is not authorised.")
        assert _is_session_dead(exc) is True

    def test_other_runtime_error_is_not_dead(self):
        """RuntimeError without auth message should NOT be dead."""
        from src.adapters.telegram.manager import _is_session_dead

        assert _is_session_dead(RuntimeError("Some other error")) is False

    def test_generic_exception_is_not_dead(self):
        """Regular exceptions should NOT be treated as dead sessions."""
        from src.adapters.telegram.manager import _is_session_dead

        assert _is_session_dead(ConnectionError("timeout")) is False
        assert _is_session_dead(ValueError("bad input")) is False


# =========================================================================
# FloodWaitError handling
# =========================================================================


class TestFloodWaitHandling:
    """Tests for explicit FloodWaitError catch and retry."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_flood_wait_retries_successfully(self, MockListener, mock_sleep):
        """FloodWaitError should trigger a sleep then successful retry."""
        from telethon.errors import FloodWaitError

        mock_listener = _mock_listener()
        # First call raises FloodWaitError, second succeeds
        mock_listener.start = AsyncMock(
            side_effect=[FloodWaitError(request=None, capture=10), None],
        )
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels={"ch1"},
        )

        assert result is True
        assert USER_A in manager._listeners
        assert mock_listener.start.await_count == 2
        # Should have slept for flood_wait_seconds + 1
        mock_sleep.assert_awaited_once_with(11)

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_flood_wait_retry_fails(self, MockListener, mock_sleep):
        """If retry after flood-wait also fails, user should not be started."""
        from telethon.errors import FloodWaitError

        mock_listener = _mock_listener()
        mock_listener.start = AsyncMock(
            side_effect=[
                FloodWaitError(request=None, capture=5),
                RuntimeError("Still failing"),
            ],
        )
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels=set(),
        )

        assert result is False
        assert USER_A not in manager._listeners

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_flood_wait_retry_not_authorised_deactivates(
        self, MockListener, mock_sleep,
    ):
        """If flood-wait retry raises 'not authorised', session must be deactivated."""
        from telethon.errors import FloodWaitError

        mock_listener = _mock_listener()
        mock_listener.start = AsyncMock(
            side_effect=[
                FloodWaitError(request=None, capture=5),
                RuntimeError(
                    "Session for user xxx is not authorised. "
                    "Re-authenticate via the auth flow."
                ),
            ],
        )
        MockListener.return_value = mock_listener

        manager = _make_manager()

        result = await manager._start_listener_for_user(
            USER_A, SESSION_A, channels=set(),
        )

        assert result is False
        assert USER_A not in manager._listeners
        manager._repo.deactivate_session.assert_awaited_once_with(USER_A, "session_expired")


# =========================================================================
# Batch channel loading
# =========================================================================


class TestBatchChannelLoading:
    """Tests for batch channel loading via repository."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.manager.TelegramListener")
    async def test_start_uses_batch_channel_loading(self, MockListener):
        """start() should use repo.load_all_monitored_channels instead of per-user."""
        mock_listener = _mock_listener()
        MockListener.return_value = mock_listener

        manager = _make_manager()
        manager._repo.load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A), (USER_B, SESSION_B)],
        )
        manager._repo.load_all_monitored_channels = AsyncMock(
            return_value={USER_A: {"ch1"}, USER_B: {"ch2", "ch3"}},
        )

        await manager.start()

        manager._repo.load_all_monitored_channels.assert_awaited_once()
        assert manager._monitored_channels[USER_A] == {"ch1"}
        assert manager._monitored_channels[USER_B] == {"ch2", "ch3"}

        manager._running = False
        if manager._refresh_task:
            manager._refresh_task.cancel()
            try:
                await manager._refresh_task
            except asyncio.CancelledError:
                pass
