"""Tests for Telegram adapters (auth, channels, listener).

All Telethon interactions are fully mocked — no real API calls are made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.telegram.auth import TelegramAuth
from src.adapters.telegram.channels import get_user_channels
from src.adapters.telegram.listener import TelegramListener
from src.core.models import RawSignal

FAKE_API_ID = 12345
FAKE_API_HASH = "abcdef1234567890abcdef1234567890"
FAKE_PHONE = "+14155551234"
FAKE_CODE_HASH = "abc123hash"
FAKE_CODE = "54321"
FAKE_PASSWORD = "hunter2"
FAKE_SESSION_STRING = "1BVtsOKABu..."
SAMPLE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")

# Shared patch targets for StringSession in each adapter module
_CHANNELS_STRING_SESSION = "src.adapters.telegram.channels.StringSession"
_LISTENER_STRING_SESSION = "src.adapters.telegram.listener.StringSession"


# =========================================================================
# Helpers
# =========================================================================

def _make_mock_client() -> AsyncMock:
    """Return an ``AsyncMock`` that behaves like a ``TelegramClient``."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.send_code_request = AsyncMock()
    client.sign_in = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=True)
    client.iter_dialogs = MagicMock()  # __aiter__ configured per test
    client.add_event_handler = MagicMock()

    # session.save() returns a session string
    session_mock = MagicMock()
    session_mock.save.return_value = FAKE_SESSION_STRING
    client.session = session_mock

    return client


# =========================================================================
# TelegramAuth — send_code
# =========================================================================


class TestTelegramAuthSendCode:
    """Tests for ``TelegramAuth.send_code()``."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_send_code_connects_and_returns_hash(self, mock_client_cls):
        """send_code should connect the client, request a code, and return the hash."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        sent_code_result = MagicMock()
        sent_code_result.phone_code_hash = FAKE_CODE_HASH
        mock_client.send_code_request.return_value = sent_code_result

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        result = await auth.send_code(FAKE_PHONE)

        mock_client.connect.assert_awaited_once()
        mock_client.send_code_request.assert_awaited_once_with(FAKE_PHONE)
        assert result == {"phone_code_hash": FAKE_CODE_HASH}

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_send_code_stores_pending_client(self, mock_client_cls):
        """The client should be stored so verify_code can reuse it."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        sent_code_result = MagicMock()
        sent_code_result.phone_code_hash = FAKE_CODE_HASH
        mock_client.send_code_request.return_value = sent_code_result

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        assert FAKE_PHONE in auth._pending_clients
        assert auth._pending_clients[FAKE_PHONE] is mock_client


# =========================================================================
# TelegramAuth — verify_code
# =========================================================================


class TestTelegramAuthVerifyCode:
    """Tests for ``TelegramAuth.verify_code()``."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_verify_code_returns_session_string(self, mock_client_cls):
        """verify_code should sign in and return the serialised session."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        sent_code_result = MagicMock()
        sent_code_result.phone_code_hash = FAKE_CODE_HASH
        mock_client.send_code_request.return_value = sent_code_result

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        session = await auth.verify_code(
            phone_number=FAKE_PHONE,
            code=FAKE_CODE,
            phone_code_hash=FAKE_CODE_HASH,
        )

        mock_client.sign_in.assert_awaited_once_with(
            phone=FAKE_PHONE,
            code=FAKE_CODE,
            phone_code_hash=FAKE_CODE_HASH,
        )
        assert session == FAKE_SESSION_STRING
        # Pending client should be cleaned up
        assert FAKE_PHONE not in auth._pending_clients

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_verify_code_with_2fa_password(self, mock_client_cls):
        """When sign_in raises SessionPasswordNeededError, the password is used."""
        from telethon.errors import SessionPasswordNeededError

        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        sent_code_result = MagicMock()
        sent_code_result.phone_code_hash = FAKE_CODE_HASH
        mock_client.send_code_request.return_value = sent_code_result

        # First sign_in call raises SessionPasswordNeededError, second succeeds
        mock_client.sign_in = AsyncMock(
            side_effect=[SessionPasswordNeededError(request=None), None]
        )

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        session = await auth.verify_code(
            phone_number=FAKE_PHONE,
            code=FAKE_CODE,
            phone_code_hash=FAKE_CODE_HASH,
            password=FAKE_PASSWORD,
        )

        # sign_in should have been called twice: first with code, then with password
        assert mock_client.sign_in.await_count == 2
        mock_client.sign_in.assert_awaited_with(password=FAKE_PASSWORD)
        assert session == FAKE_SESSION_STRING

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_verify_code_2fa_no_password_raises(self, mock_client_cls):
        """When 2FA is required but no password is provided, the error propagates."""
        from telethon.errors import SessionPasswordNeededError

        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        sent_code_result = MagicMock()
        sent_code_result.phone_code_hash = FAKE_CODE_HASH
        mock_client.send_code_request.return_value = sent_code_result

        mock_client.sign_in = AsyncMock(
            side_effect=SessionPasswordNeededError(request=None)
        )

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        with pytest.raises(SessionPasswordNeededError):
            await auth.verify_code(
                phone_number=FAKE_PHONE,
                code=FAKE_CODE,
                phone_code_hash=FAKE_CODE_HASH,
                password=None,
            )

    @pytest.mark.asyncio
    async def test_verify_code_without_send_code_raises(self):
        """verify_code should raise ValueError if send_code was not called first."""
        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)

        with pytest.raises(ValueError, match="No pending authentication"):
            await auth.verify_code(
                phone_number=FAKE_PHONE,
                code=FAKE_CODE,
                phone_code_hash=FAKE_CODE_HASH,
            )

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_verify_code_invalid_code_raises(self, mock_client_cls):
        """When sign_in raises a non-2FA error, it propagates."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        sent_code_result = MagicMock()
        sent_code_result.phone_code_hash = FAKE_CODE_HASH
        mock_client.send_code_request.return_value = sent_code_result

        mock_client.sign_in = AsyncMock(
            side_effect=RuntimeError("Invalid code")
        )

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        with pytest.raises(RuntimeError, match="Invalid code"):
            await auth.verify_code(
                phone_number=FAKE_PHONE,
                code=FAKE_CODE,
                phone_code_hash=FAKE_CODE_HASH,
            )


# =========================================================================
# Channel listing — get_user_channels
# =========================================================================


def _make_channel_entity(
    *, id: int, title: str, broadcast: bool = False, megagroup: bool = False
) -> MagicMock:
    """Create a mock ``Channel`` entity."""
    entity = MagicMock()
    entity.id = id
    entity.title = title
    entity.broadcast = broadcast
    entity.megagroup = megagroup
    # Make isinstance(..., Channel) return True
    entity.__class__ = MagicMock()
    return entity


def _make_user_entity(*, id: int, first_name: str) -> MagicMock:
    """Create a mock user entity (not a channel)."""
    entity = MagicMock()
    entity.id = id
    entity.first_name = first_name
    return entity


class TestGetUserChannels:
    """Tests for ``get_user_channels()``."""

    @pytest.mark.asyncio
    @patch(_CHANNELS_STRING_SESSION)
    @patch("src.adapters.telegram.channels.TelegramClient")
    async def test_returns_only_channels_and_supergroups(
        self, mock_client_cls, _mock_ss
    ):
        """Only Channel entities with broadcast=True or megagroup=True should be returned."""
        from telethon.tl.types import Channel

        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        # Build mock dialogs — use the real Channel class as spec so that
        # ``isinstance(entity, Channel)`` returns True inside channels.py.
        broadcast_channel = MagicMock(spec=Channel)
        broadcast_channel.id = 1001
        broadcast_channel.title = "News Channel"
        broadcast_channel.broadcast = True
        broadcast_channel.megagroup = False

        supergroup = MagicMock(spec=Channel)
        supergroup.id = 1002
        supergroup.title = "Trading Group"
        supergroup.broadcast = False
        supergroup.megagroup = True

        regular_user = MagicMock()  # Not a Channel — should be filtered out
        regular_user.id = 9999
        regular_user.first_name = "Alice"

        private_group = MagicMock(spec=Channel)
        private_group.id = 1003
        private_group.title = "Small Chat"
        private_group.broadcast = False
        private_group.megagroup = False

        dialog_broadcast = MagicMock()
        dialog_broadcast.entity = broadcast_channel

        dialog_supergroup = MagicMock()
        dialog_supergroup.entity = supergroup

        dialog_user = MagicMock()
        dialog_user.entity = regular_user

        dialog_private = MagicMock()
        dialog_private.entity = private_group

        # Configure async iteration over dialogs
        async def _mock_iter_dialogs():
            for d in [dialog_broadcast, dialog_supergroup, dialog_user, dialog_private]:
                yield d

        mock_client.iter_dialogs.return_value = _mock_iter_dialogs()

        channels = await get_user_channels(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            session_string=FAKE_SESSION_STRING,
        )

        assert len(channels) == 2
        ids = {ch["channel_id"] for ch in channels}
        assert ids == {"1001", "1002"}

        mock_client.connect.assert_awaited_once()
        mock_client.is_user_authorized.assert_awaited_once()
        mock_client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_CHANNELS_STRING_SESSION)
    @patch("src.adapters.telegram.channels.TelegramClient")
    async def test_returned_dict_structure(self, mock_client_cls, _mock_ss):
        """Each returned dict should have channel_id and channel_name keys."""
        from telethon.tl.types import Channel

        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        channel = MagicMock(spec=Channel)
        channel.id = 5555
        channel.title = "Forex Signals VIP"
        channel.broadcast = True
        channel.megagroup = False

        dialog = MagicMock()
        dialog.entity = channel

        async def _mock_iter_dialogs():
            yield dialog

        mock_client.iter_dialogs.return_value = _mock_iter_dialogs()

        channels = await get_user_channels(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            session_string=FAKE_SESSION_STRING,
        )

        assert len(channels) == 1
        entry = channels[0]
        assert entry["channel_id"] == "5555"
        assert entry["channel_name"] == "Forex Signals VIP"

    @pytest.mark.asyncio
    @patch(_CHANNELS_STRING_SESSION)
    @patch("src.adapters.telegram.channels.TelegramClient")
    async def test_unauthorized_session_raises(self, mock_client_cls, _mock_ss):
        """An unauthorised session should raise RuntimeError."""
        mock_client = _make_mock_client()
        mock_client.is_user_authorized = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="not authorised"):
            await get_user_channels(
                api_id=FAKE_API_ID,
                api_hash=FAKE_API_HASH,
                session_string=FAKE_SESSION_STRING,
            )

        mock_client.disconnect.assert_awaited_once()


# =========================================================================
# TelegramListener
# =========================================================================


class TestTelegramListenerStart:
    """Tests for ``TelegramListener.start()``."""

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_start_registers_event_handler(self, mock_client_cls, _mock_ss):
        """start() should connect, verify auth, and register a NewMessage handler."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )

        await listener.start(user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING)

        mock_client.connect.assert_awaited_once()
        mock_client.is_user_authorized.assert_awaited_once()
        # Should register both NewMessage and MessageEdited handlers
        assert mock_client.add_event_handler.call_count == 2

        # Verify both handlers point to _on_new_message
        for call in mock_client.add_event_handler.call_args_list:
            assert call[0][0] == listener._on_new_message

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_start_with_channels_uses_get_entity(self, mock_client_cls, _mock_ss):
        """start() with monitored_channels should use get_entity instead of get_dialogs."""
        mock_client = _make_mock_client()
        mock_client.get_entity = AsyncMock()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )

        await listener.start(
            user_id=SAMPLE_USER_ID,
            session_string=FAKE_SESSION_STRING,
            monitored_channels={"12345", "67890"},
        )

        # get_entity should be called for each channel
        assert mock_client.get_entity.await_count == 2
        mock_client.get_entity.assert_any_await(12345)
        mock_client.get_entity.assert_any_await(67890)
        # get_dialogs should NOT be called
        mock_client.get_dialogs.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_start_without_channels_falls_back_to_get_dialogs(self, mock_client_cls, _mock_ss):
        """start() without monitored_channels should fall back to get_dialogs."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )

        await listener.start(
            user_id=SAMPLE_USER_ID,
            session_string=FAKE_SESSION_STRING,
        )

        mock_client.get_dialogs.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_start_unauthorized_raises(self, mock_client_cls, _mock_ss):
        """start() should raise RuntimeError if the session is not authorised."""
        mock_client = _make_mock_client()
        mock_client.is_user_authorized = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )

        with pytest.raises(RuntimeError, match="not authorised"):
            await listener.start(
                user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING
            )


class TestTelegramListenerOnNewMessage:
    """Tests for ``TelegramListener._on_new_message()``."""

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_on_new_message_enqueues_raw_signal(self, mock_client_cls, _mock_ss):
        """_on_new_message should build a RawSignal and enqueue it via QueuePort."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
            monitored_channels={str(-1001234567890)},
        )
        await listener.start(user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING)

        # Build a mock event
        event = AsyncMock()
        event.message = MagicMock()
        event.message.text = "EURUSD BUY @ 1.1000"
        event.message.id = 42
        event.chat_id = -1001234567890

        mock_chat = MagicMock()
        mock_chat.id = -1001234567890
        event.get_chat = AsyncMock(return_value=mock_chat)

        await listener._on_new_message(event)

        queue_port.enqueue.assert_awaited_once()
        enqueued_signal: RawSignal = queue_port.enqueue.call_args[0][0]

        assert isinstance(enqueued_signal, RawSignal)
        assert enqueued_signal.user_id == SAMPLE_USER_ID
        assert enqueued_signal.channel_id == str(-1001234567890)
        assert enqueued_signal.raw_message == "EURUSD BUY @ 1.1000"
        assert enqueued_signal.message_id == 42

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_on_new_message_skips_empty_text(self, mock_client_cls, _mock_ss):
        """Messages with no text (e.g. images) should be silently skipped."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )
        await listener.start(user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING)

        event = AsyncMock()
        event.message = MagicMock()
        event.message.text = ""  # Empty text

        await listener._on_new_message(event)

        queue_port.enqueue.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_on_new_message_uses_chat_id_fallback(self, mock_client_cls, _mock_ss):
        """When get_chat() returns None, event.chat_id should be used as fallback."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
            monitored_channels={str(abs(-1009876543210))},
        )
        await listener.start(user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING)

        event = AsyncMock()
        event.message = MagicMock()
        event.message.text = "GBPUSD SELL"
        event.message.id = 99
        event.chat_id = -1009876543210
        event.get_chat = AsyncMock(return_value=None)

        await listener._on_new_message(event)

        enqueued_signal: RawSignal = queue_port.enqueue.call_args[0][0]
        # When get_chat() returns None, the listener uses abs(event.chat_id)
        # to strip the -100 prefix and match channels.py format
        assert enqueued_signal.channel_id == str(abs(-1009876543210))

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_on_new_message_handles_enqueue_failure(self, mock_client_cls, _mock_ss):
        """If enqueue raises, the error should be caught (not crash the listener)."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        queue_port.enqueue = AsyncMock(side_effect=RuntimeError("queue down"))

        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )
        await listener.start(user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING)

        event = AsyncMock()
        event.message = MagicMock()
        event.message.text = "EURUSD BUY"
        event.message.id = 77
        event.chat_id = -100111

        mock_chat = MagicMock()
        mock_chat.id = -100111
        event.get_chat = AsyncMock(return_value=mock_chat)

        # Should NOT raise — the exception is caught internally
        await listener._on_new_message(event)


class TestTelegramListenerStop:
    """Tests for ``TelegramListener.stop()``."""

    @pytest.mark.asyncio
    @patch(_LISTENER_STRING_SESSION)
    @patch("src.adapters.telegram.listener.TelegramClient")
    async def test_stop_disconnects_client(self, mock_client_cls, _mock_ss):
        """stop() should disconnect the underlying TelegramClient."""
        mock_client = _make_mock_client()
        mock_client_cls.return_value = mock_client

        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )
        await listener.start(user_id=SAMPLE_USER_ID, session_string=FAKE_SESSION_STRING)

        await listener.stop()

        mock_client.disconnect.assert_awaited_once()
        assert listener._client is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(self):
        """stop() on a listener that was never started should be a no-op."""
        queue_port = AsyncMock()
        listener = TelegramListener(
            api_id=FAKE_API_ID,
            api_hash=FAKE_API_HASH,
            queue_port=queue_port,
        )

        # Should not raise
        await listener.stop()
        assert listener._client is None


# =========================================================================
# PII Logging Tests — phone numbers must NEVER appear in logs
# =========================================================================


class TestAuthPIIMasking:
    """Verify that phone numbers are masked in all auth log output."""

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_send_code_masks_phone_in_logs(self, MockClient, caplog):
        mock_client = _make_mock_client()
        mock_client.send_code_request.return_value = MagicMock(
            phone_code_hash=FAKE_CODE_HASH,
        )
        MockClient.return_value = mock_client

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        with caplog.at_level("INFO"):
            await auth.send_code(FAKE_PHONE)

        for record in caplog.records:
            assert FAKE_PHONE not in record.getMessage(), (
                f"Raw phone number found in log: {record.getMessage()}"
            )
        # SHA-256 hash prefix should appear (no phone digits)
        import hashlib
        expected_id = hashlib.sha256(FAKE_PHONE.encode()).hexdigest()[:8]
        assert any(expected_id in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_verify_code_masks_phone_in_logs(self, MockClient, caplog):
        mock_client = _make_mock_client()
        mock_client.send_code_request.return_value = MagicMock(
            phone_code_hash=FAKE_CODE_HASH,
        )
        mock_client.session.save.return_value = FAKE_SESSION_STRING
        MockClient.return_value = mock_client

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        with caplog.at_level("INFO"):
            await auth.verify_code(FAKE_PHONE, FAKE_CODE, FAKE_CODE_HASH)

        for record in caplog.records:
            assert FAKE_PHONE not in record.getMessage(), (
                f"Raw phone number found in log: {record.getMessage()}"
            )

    @pytest.mark.asyncio
    @patch("src.adapters.telegram.auth.TelegramClient")
    async def test_disconnect_masks_phone_in_logs(self, MockClient, caplog):
        mock_client = _make_mock_client()
        mock_client.send_code_request.return_value = MagicMock(
            phone_code_hash=FAKE_CODE_HASH,
        )
        MockClient.return_value = mock_client

        auth = TelegramAuth(api_id=FAKE_API_ID, api_hash=FAKE_API_HASH)
        await auth.send_code(FAKE_PHONE)

        with caplog.at_level("DEBUG"):
            await auth.disconnect(FAKE_PHONE)

        for record in caplog.records:
            assert FAKE_PHONE not in record.getMessage(), (
                f"Raw phone number found in log: {record.getMessage()}"
            )
