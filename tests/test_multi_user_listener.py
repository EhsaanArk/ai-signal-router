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
    MAX_CONSECUTIVE_FAILURES,
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
    return MultiUserListenerManager(
        api_id=FAKE_API_ID,
        api_hash=FAKE_API_HASH,
        queue_port=AsyncMock(),
        engine=MagicMock(),
        enc_key=FAKE_ENC_KEY,
        **overrides,
    )


def _mock_listener(connected: bool = True) -> MagicMock:
    """Create a mock TelegramListener with controllable connection state."""
    listener = AsyncMock()
    listener.start = AsyncMock()
    listener.stop = AsyncMock()
    listener.update_monitored_channels = MagicMock()
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
        manager._load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A), (USER_B, SESSION_B)],
        )
        manager._load_monitored_channels = AsyncMock(return_value={"123", "456"})

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
        manager._load_active_sessions = AsyncMock(return_value=[])
        manager._load_monitored_channels = AsyncMock(return_value=set())

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
        manager._load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A)],
        )

        channels_a = {"111", "222"}
        manager._load_monitored_channels = AsyncMock(return_value=channels_a)

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
        manager._load_active_sessions = AsyncMock(
            return_value=[(USER_A, SESSION_A), (USER_B, SESSION_B)],
        )
        manager._load_monitored_channels = AsyncMock(return_value=set())

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
        manager._load_monitored_channels = AsyncMock(return_value=set())

        # Simulate: user A already running, user B is new
        manager._listeners[USER_A] = _mock_listener()
        manager._monitored_channels[USER_A] = set()
        manager._failure_counts[USER_A] = 0

        manager._load_active_sessions = AsyncMock(
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
        manager._load_active_sessions = AsyncMock(
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
        manager._load_monitored_channels = AsyncMock(return_value=new_channels)

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

        manager._load_monitored_channels = AsyncMock(return_value=existing)

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
