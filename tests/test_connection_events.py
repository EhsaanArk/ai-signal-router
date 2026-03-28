"""Tests for AuthKeyDuplicatedError fix and connection event logging."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import AuthKeyDuplicatedError, AuthKeyError

from src.adapters.telegram.manager import (
    MAX_AUTH_DUP_RETRIES,
    MultiUserListenerManager,
    _is_session_dead,
)


# ---------------------------------------------------------------------------
# _is_session_dead — pure function tests
# ---------------------------------------------------------------------------


class TestIsSessionDead:
    """Verify _is_session_dead correctly classifies exceptions."""

    def _make_auth_key_duplicated(self) -> AuthKeyDuplicatedError:
        return AuthKeyDuplicatedError.__new__(AuthKeyDuplicatedError)

    def _make_auth_key_error(self) -> AuthKeyError:
        return AuthKeyError.__new__(AuthKeyError)

    def test_auth_key_duplicated_is_transient(self):
        """AuthKeyDuplicatedError should NOT be treated as dead."""
        exc = self._make_auth_key_duplicated()
        assert _is_session_dead(exc) is False

    def test_auth_key_error_is_dead(self):
        """AuthKeyError (non-duplicated) should be treated as dead."""
        exc = self._make_auth_key_error()
        assert _is_session_dead(exc) is True

    def test_runtime_not_authorised_is_dead(self):
        """RuntimeError with 'not authorised' is a dead session."""
        assert _is_session_dead(RuntimeError("not authorised")) is True

    def test_runtime_other_is_not_dead(self):
        """RuntimeError without 'not authorised' is not dead."""
        assert _is_session_dead(RuntimeError("some other error")) is False

    def test_generic_exception_is_not_dead(self):
        """Generic exceptions are not dead sessions."""
        assert _is_session_dead(Exception("random")) is False

    def test_auth_key_duplicated_is_subclass_of_auth_key_error(self):
        """Verify our isinstance ordering matters — dup IS a subclass."""
        exc = self._make_auth_key_duplicated()
        assert isinstance(exc, AuthKeyError)
        assert isinstance(exc, AuthKeyDuplicatedError)
        # But _is_session_dead must check subclass first
        assert _is_session_dead(exc) is False

    def test_session_revoked_is_dead(self):
        """SessionRevokedError (UnauthorizedError subclass) is permanent."""
        from telethon.errors import SessionRevokedError
        exc = SessionRevokedError.__new__(SessionRevokedError)
        assert _is_session_dead(exc) is True

    def test_session_expired_is_dead(self):
        """SessionExpiredError (UnauthorizedError subclass) is permanent."""
        from telethon.errors import SessionExpiredError
        exc = SessionExpiredError.__new__(SessionExpiredError)
        assert _is_session_dead(exc) is True

    def test_auth_key_unregistered_is_dead(self):
        """AuthKeyUnregisteredError (UnauthorizedError subclass) is permanent."""
        from telethon.errors import AuthKeyUnregisteredError
        exc = AuthKeyUnregisteredError.__new__(AuthKeyUnregisteredError)
        assert _is_session_dead(exc) is True


# ---------------------------------------------------------------------------
# _handle_auth_key_duplicated — retry logic tests
# ---------------------------------------------------------------------------


@pytest.fixture
def manager():
    """Create a MultiUserListenerManager with mocked dependencies."""
    mgr = MultiUserListenerManager.__new__(MultiUserListenerManager)
    mgr._api_id = 12345
    mgr._api_hash = "test"
    mgr._queue_port = MagicMock()
    mgr._engine = MagicMock()
    mgr._proxy = None
    mgr._email_notifier = None
    mgr._proxy_provider = MagicMock()
    mgr._repo = MagicMock()
    mgr._repo.log_connection_event = AsyncMock()
    mgr._repo.deactivate_session = AsyncMock()
    mgr._listeners = {}
    mgr._monitored_channels = {}
    mgr._failure_counts = {}
    mgr._startup_failures = {}
    mgr._auth_dup_retries = {}
    mgr._user_locks = {}
    mgr._heartbeat_count = 0
    mgr._refresh_task = None
    mgr._running = False
    mgr._startup_semaphore = asyncio.Semaphore(3)
    mgr._heartbeat_semaphore = asyncio.Semaphore(10)
    return mgr


@pytest.fixture
def mock_listener():
    """Create a mock TelegramListener."""
    listener = MagicMock()
    listener._client = AsyncMock()
    listener._client.disconnect = AsyncMock()
    listener.is_connected = False
    return listener


class TestHandleAuthKeyDuplicated:
    """Test the _handle_auth_key_duplicated retry + escalation logic."""

    @pytest.mark.asyncio
    async def test_first_retry_restarts(self, manager, mock_listener):
        """First AuthKeyDuplicatedError should disconnect + restart."""
        user_id = uuid.uuid4()
        manager._listeners[user_id] = mock_listener

        with patch.object(manager, "_restart_listener_for_user", new_callable=AsyncMock) as restart:
            await manager._handle_auth_key_duplicated(
                user_id, mock_listener, "reconnect",
            )

        assert manager._auth_dup_retries[user_id] == 1
        mock_listener._client.disconnect.assert_awaited_once()
        restart.assert_awaited_once_with(user_id)
        manager._repo.log_connection_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exhaust_retries_deactivates(self, manager, mock_listener):
        """After MAX_AUTH_DUP_RETRIES, session should be deactivated."""
        user_id = uuid.uuid4()
        manager._listeners[user_id] = mock_listener
        manager._auth_dup_retries[user_id] = MAX_AUTH_DUP_RETRIES  # Already at limit

        with patch.object(manager, "_deactivate_and_notify", new_callable=AsyncMock) as deactivate, \
             patch.object(manager, "_stop_listener_for_user", new_callable=AsyncMock) as stop:
            await manager._handle_auth_key_duplicated(
                user_id, mock_listener, "reconnect",
            )

        deactivate.assert_awaited_once_with(user_id, "auth_key_duplicated_permanent")
        stop.assert_awaited_once_with(user_id)
        # Counter should be cleaned up
        assert user_id not in manager._auth_dup_retries

    @pytest.mark.asyncio
    async def test_lock_held_restart_uses_inner(self, manager, mock_listener):
        """When lock_held=True (startup path), should call _inner variant."""
        user_id = uuid.uuid4()
        manager._listeners[user_id] = mock_listener

        with patch.object(manager, "_restart_listener_for_user_inner", new_callable=AsyncMock) as restart_inner, \
             patch.object(manager, "_restart_listener_for_user", new_callable=AsyncMock) as restart_outer:
            await manager._handle_auth_key_duplicated(
                user_id, mock_listener, "startup", lock_held=True,
            )

        restart_inner.assert_awaited_once_with(user_id)
        restart_outer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lock_held_escalation_uses_inner_stop(self, manager, mock_listener):
        """When lock_held=True and retries exhausted, should call _stop_inner."""
        user_id = uuid.uuid4()
        manager._listeners[user_id] = mock_listener
        manager._auth_dup_retries[user_id] = MAX_AUTH_DUP_RETRIES

        with patch.object(manager, "_deactivate_and_notify", new_callable=AsyncMock), \
             patch.object(manager, "_stop_listener_for_user_inner", new_callable=AsyncMock) as stop_inner, \
             patch.object(manager, "_stop_listener_for_user", new_callable=AsyncMock) as stop_outer:
            await manager._handle_auth_key_duplicated(
                user_id, mock_listener, "startup", lock_held=True,
            )

        stop_inner.assert_awaited_once_with(user_id)
        stop_outer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_counter_resets_on_successful_start(self, manager):
        """_auth_dup_retries should be cleared when a listener starts successfully."""
        user_id = uuid.uuid4()
        manager._auth_dup_retries[user_id] = 2

        mock_listener = MagicMock()
        mock_listener.start = AsyncMock()
        mock_listener.update_monitored_channels = MagicMock()

        with patch(
            "src.adapters.telegram.manager.TelegramListener",
            return_value=mock_listener,
        ), patch.object(
            manager._proxy_provider, "get_proxy_for_user", return_value=None,
        ):
            result = await manager._start_listener_for_user(
                user_id, "fake_session_string", set(),
            )

        assert result is True
        assert user_id not in manager._auth_dup_retries


# ---------------------------------------------------------------------------
# log_connection_event — graceful failure
# ---------------------------------------------------------------------------


class TestLogConnectionEvent:
    """Test that connection event logging doesn't crash on failure."""

    @pytest.mark.asyncio
    async def test_log_event_succeeds(self):
        """Verify basic event logging flow with mock DB."""
        from src.adapters.telegram.repository import TelegramSessionRepository

        repo = TelegramSessionRepository.__new__(TelegramSessionRepository)
        repo._engine = MagicMock()
        repo._enc_key = b"fake"

        user_id = uuid.uuid4()

        # Mock the AsyncSession context manager
        mock_session = AsyncMock()
        with patch(
            "src.adapters.telegram.repository.AsyncSession",
            return_value=mock_session,
        ):
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            await repo.log_connection_event(
                user_id, "connected", reason="startup",
            )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_event_fails_gracefully(self):
        """DB failure should be swallowed, not propagated."""
        from src.adapters.telegram.repository import TelegramSessionRepository

        repo = TelegramSessionRepository.__new__(TelegramSessionRepository)
        repo._engine = MagicMock()
        repo._enc_key = b"fake"

        user_id = uuid.uuid4()

        with patch(
            "src.adapters.telegram.repository.AsyncSession",
            side_effect=Exception("DB down"),
        ):
            # Should not raise
            await repo.log_connection_event(
                user_id, "connected", reason="startup",
            )


# ---------------------------------------------------------------------------
# Startup guard — post-deploy delay
# ---------------------------------------------------------------------------


class TestStartupGuard:
    """Test the deploy startup guard that prevents auth key overlap."""

    @pytest.mark.asyncio
    async def test_waits_when_recent_shutdown(self):
        """Should sleep when previous container shut down recently."""
        from src.adapters.telegram.deploy_snapshot import wait_for_previous_shutdown

        recent_ts = datetime.now(timezone.utc).isoformat()
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=json.dumps({
            "timestamp": recent_ts,
            "active_sessions": 3,
        }))

        with patch("src.adapters.telegram.deploy_snapshot.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await wait_for_previous_shutdown(mock_cache, guard_seconds=5.0)

        # Should have slept (shutdown was just now, need ~5s guard)
        mock_sleep.assert_awaited_once()
        slept = mock_sleep.call_args[0][0]
        assert 4.0 < slept <= 5.0  # ~5s minus tiny elapsed time

    @pytest.mark.asyncio
    async def test_skips_when_old_shutdown(self):
        """Should not sleep when previous container shut down long ago."""
        from src.adapters.telegram.deploy_snapshot import wait_for_previous_shutdown

        old_ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=json.dumps({
            "timestamp": old_ts,
            "active_sessions": 3,
        }))

        with patch("src.adapters.telegram.deploy_snapshot.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await wait_for_previous_shutdown(mock_cache, guard_seconds=5.0)

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_no_snapshot(self):
        """Should return immediately when no snapshot exists."""
        from src.adapters.telegram.deploy_snapshot import wait_for_previous_shutdown

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)

        with patch("src.adapters.telegram.deploy_snapshot.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await wait_for_previous_shutdown(mock_cache, guard_seconds=5.0)

        mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# Client configuration constants
# ---------------------------------------------------------------------------


class TestClientConstants:
    """Verify hardened client configuration values."""

    def test_connection_retries_increased(self):
        from src.adapters.telegram.listener import CLIENT_CONNECTION_RETRIES
        assert CLIENT_CONNECTION_RETRIES >= 10

    def test_retry_delay_increased(self):
        from src.adapters.telegram.listener import CLIENT_RETRY_DELAY
        assert CLIENT_RETRY_DELAY >= 2

    def test_timeout_increased(self):
        from src.adapters.telegram.listener import CLIENT_TIMEOUT
        assert CLIENT_TIMEOUT >= 15

    def test_flood_threshold_increased(self):
        from src.adapters.telegram.listener import CLIENT_FLOOD_SLEEP_THRESHOLD
        assert CLIENT_FLOOD_SLEEP_THRESHOLD >= 120

    def test_device_fingerprint_set(self):
        from src.adapters.telegram.listener import DEVICE_MODEL, SYSTEM_VERSION, APP_VERSION
        assert DEVICE_MODEL == "Sage Radar Server"
        assert SYSTEM_VERSION  # not empty
        assert APP_VERSION  # not empty
