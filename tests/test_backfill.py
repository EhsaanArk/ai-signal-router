"""Tests for signal backfill on reconnect and workflow deduplication.

Verifies that missed signals are backfilled after listener restart,
stale signals are filtered, duplicates are skipped, and errors are
handled gracefully.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.telegram.manager import (
    BACKFILL_MAX_AGE_SECONDS,
    MultiUserListenerManager,
)
from src.core.models import RawSignal

FAKE_API_ID = 12345
FAKE_API_HASH = "abcdef1234567890abcdef1234567890"
FAKE_ENC_KEY = b"dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXk="

USER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CHANNEL_1 = "1234567890"


def _make_manager(**overrides) -> MultiUserListenerManager:
    """Create a manager with mocked engine and default settings."""
    defaults = dict(
        api_id=FAKE_API_ID,
        api_hash=FAKE_API_HASH,
        queue_port=AsyncMock(),
        engine=MagicMock(),
        enc_key=FAKE_ENC_KEY,
    )
    defaults.update(overrides)
    return MultiUserListenerManager(**defaults)


def _make_telegram_message(
    msg_id: int,
    text: str,
    age_seconds: float = 10,
    reply_to_msg_id: int | None = None,
) -> MagicMock:
    """Create a mock Telegram message object."""
    msg = MagicMock()
    msg.id = msg_id
    msg.text = text
    msg.date = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    if reply_to_msg_id:
        msg.reply_to = MagicMock()
        msg.reply_to.reply_to_msg_id = reply_to_msg_id
    else:
        msg.reply_to = None
    return msg


def _mock_listener() -> MagicMock:
    """Create a mock TelegramListener with client for backfill."""
    listener = MagicMock()
    listener.is_connected = True
    listener._client = AsyncMock()
    listener._client.get_entity = AsyncMock(return_value=MagicMock())
    listener._client.get_messages = AsyncMock(return_value=[])
    return listener


# -----------------------------------------------------------------------
# Backfill tests
# -----------------------------------------------------------------------


class TestBackfillMissedSignals:
    """Tests for _backfill_missed_signals()."""

    @pytest.mark.asyncio
    async def test_backfill_enqueues_missed_messages(self):
        """Messages with ID > last_seen_id that are fresh and not yet
        processed should be enqueued."""
        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        # Telegram returns 3 messages, IDs 101, 102, 103
        messages = [
            _make_telegram_message(103, "XAUUSD BUY @ 2350", age_seconds=5),
            _make_telegram_message(102, "EURUSD SELL @ 1.08", age_seconds=10),
            _make_telegram_message(101, "Good morning!", age_seconds=15),
        ]
        listener._client.get_messages = AsyncMock(return_value=messages)

        # Mock DB: last_seen_id = 100, no duplicates
        with patch.object(manager, "_engine") as mock_engine:
            # First DB call: MAX(message_id) returns 100
            mock_session_ctx = AsyncMock()
            mock_session = AsyncMock()

            # Track call count to return different results
            call_count = 0

            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                result = MagicMock()
                if call_count == 1:
                    # MAX(message_id) query
                    result.scalar_one_or_none.return_value = 100
                else:
                    # Dedup IN query — none already processed
                    result.all.return_value = []
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.adapters.telegram.manager.AsyncSession",
                return_value=mock_session,
            ):
                await manager._backfill_missed_signals(
                    USER_A, listener, {CHANNEL_1},
                )

        # All 3 messages should be enqueued (all fresh, all > 100)
        assert queue.enqueue.call_count == 3
        enqueued_signals = [
            call.args[0] for call in queue.enqueue.call_args_list
        ]
        enqueued_ids = {s.message_id for s in enqueued_signals}
        assert enqueued_ids == {101, 102, 103}

    @pytest.mark.asyncio
    async def test_backfill_filters_stale_messages(self):
        """Messages older than BACKFILL_MAX_AGE_SECONDS should be dropped."""
        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        # 1 fresh (10s old), 1 stale (120s old — beyond default 60s)
        messages = [
            _make_telegram_message(102, "EURUSD BUY", age_seconds=10),
            _make_telegram_message(101, "XAUUSD SELL", age_seconds=120),
        ]
        listener._client.get_messages = AsyncMock(return_value=messages)

        with patch(
            "src.adapters.telegram.manager.AsyncSession",
        ) as MockSession:
            mock_session = AsyncMock()
            call_count = 0

            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                result = MagicMock()
                if call_count == 1:
                    result.scalar_one_or_none.return_value = 100
                else:
                    result.all.return_value = []
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value = mock_session

            await manager._backfill_missed_signals(
                USER_A, listener, {CHANNEL_1},
            )

        # Only the fresh message should be enqueued
        assert queue.enqueue.call_count == 1
        assert queue.enqueue.call_args[0][0].message_id == 102

    @pytest.mark.asyncio
    async def test_backfill_skips_already_processed(self):
        """Messages that already exist in signal_logs should be skipped."""
        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        messages = [
            _make_telegram_message(103, "GOLD BUY", age_seconds=5),
            _make_telegram_message(102, "SILVER SELL", age_seconds=10),
            _make_telegram_message(101, "NAS100 BUY", age_seconds=15),
        ]
        listener._client.get_messages = AsyncMock(return_value=messages)

        with patch(
            "src.adapters.telegram.manager.AsyncSession",
        ) as MockSession:
            mock_session = AsyncMock()
            call_count = 0

            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                result = MagicMock()
                if call_count == 1:
                    result.scalar_one_or_none.return_value = 100
                else:
                    # Message 101 and 102 already processed
                    result.all.return_value = [(101,), (102,)]
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value = mock_session

            await manager._backfill_missed_signals(
                USER_A, listener, {CHANNEL_1},
            )

        # Only message 103 should be enqueued
        assert queue.enqueue.call_count == 1
        assert queue.enqueue.call_args[0][0].message_id == 103

    @pytest.mark.asyncio
    async def test_backfill_no_prior_logs_skips(self):
        """When there are no prior signal_logs for a channel (first-ever
        startup), backfill should be skipped for that channel."""
        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        with patch(
            "src.adapters.telegram.manager.AsyncSession",
        ) as MockSession:
            mock_session = AsyncMock()

            async def mock_execute(query):
                result = MagicMock()
                # MAX(message_id) returns None — no prior logs
                result.scalar_one_or_none.return_value = None
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value = mock_session

            await manager._backfill_missed_signals(
                USER_A, listener, {CHANNEL_1},
            )

        # No messages should be fetched or enqueued
        listener._client.get_messages.assert_not_called()
        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_backfill_flood_wait_handled(self):
        """FloodWaitError during iter_messages should be caught and
        remaining channels skipped."""
        from telethon.errors import FloodWaitError

        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        # get_entity raises FloodWaitError
        listener._client.get_entity = AsyncMock(
            side_effect=FloodWaitError(request=None, capture=30),
        )

        with patch(
            "src.adapters.telegram.manager.AsyncSession",
        ) as MockSession:
            mock_session = AsyncMock()

            async def mock_execute(query):
                result = MagicMock()
                result.scalar_one_or_none.return_value = 100
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value = mock_session

            # Should not raise
            await manager._backfill_missed_signals(
                USER_A, listener, {CHANNEL_1, "9999999"},
            )

        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_backfill_channel_deleted_handled(self):
        """If a channel was deleted, get_entity raises an exception.
        Backfill should skip that channel and continue to the next."""
        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        # First channel raises, but we need to test it continues
        call_count = 0

        async def mock_get_entity(channel_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Could not find the input entity")
            return MagicMock()

        listener._client.get_entity = mock_get_entity
        listener._client.get_messages = AsyncMock(return_value=[])

        with patch(
            "src.adapters.telegram.manager.AsyncSession",
        ) as MockSession:
            mock_session = AsyncMock()

            async def mock_execute(query):
                result = MagicMock()
                result.scalar_one_or_none.return_value = 100
                result.all.return_value = []
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value = mock_session

            # Should not raise — graceful skip
            await manager._backfill_missed_signals(
                USER_A, listener, {CHANNEL_1, "9999999"},
            )

    @pytest.mark.asyncio
    async def test_backfill_disconnected_listener_skips(self):
        """If the listener is disconnected, backfill should be a no-op."""
        queue = AsyncMock()
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()
        listener.is_connected = False

        await manager._backfill_missed_signals(
            USER_A, listener, {CHANNEL_1},
        )

        listener._client.get_entity.assert_not_called()
        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_backfill_enqueue_failure_continues(self):
        """If enqueue fails for one message, backfill should continue
        to enqueue remaining messages."""
        queue = AsyncMock()
        # First enqueue call fails, second succeeds
        queue.enqueue = AsyncMock(
            side_effect=[Exception("QStash 500"), None],
        )
        manager = _make_manager(queue_port=queue)
        listener = _mock_listener()

        messages = [
            _make_telegram_message(102, "EURUSD BUY", age_seconds=5),
            _make_telegram_message(101, "XAUUSD SELL", age_seconds=10),
        ]
        listener._client.get_messages = AsyncMock(return_value=messages)

        with patch(
            "src.adapters.telegram.manager.AsyncSession",
        ) as MockSession:
            mock_session = AsyncMock()
            call_count = 0

            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                result = MagicMock()
                if call_count == 1:
                    result.scalar_one_or_none.return_value = 100
                else:
                    result.all.return_value = []
                return result

            mock_session.execute = mock_execute
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            MockSession.return_value = mock_session

            await manager._backfill_missed_signals(
                USER_A, listener, {CHANNEL_1},
            )

        # Both messages should have been attempted
        assert queue.enqueue.call_count == 2


# -----------------------------------------------------------------------
# Workflow deduplication tests
# -----------------------------------------------------------------------


class TestWorkflowDeduplication:
    """Tests for the dedup check at the start of process_signal()."""

    @pytest.mark.asyncio
    async def test_dedup_skips_already_successful(self):
        """If a signal_log with status=success exists for the same
        (channel_id, message_id, user_id), the workflow should return
        early with an empty list."""
        from unittest.mock import patch as _patch

        raw = RawSignal(
            user_id=USER_A,
            channel_id=CHANNEL_1,
            raw_message="EURUSD BUY @ 1.1000",
            message_id=42,
        )

        # Mock the DB session to return an existing successful log
        mock_db = AsyncMock()

        # First query: dedup check — returns existing ID
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = UUID(
            "dddddddd-dddd-dddd-dddd-dddddddddddd"
        )
        mock_db.execute = AsyncMock(return_value=dedup_result)

        mock_request = MagicMock()
        mock_settings = MagicMock()
        mock_dispatcher = MagicMock()

        from src.api.workflow import process_signal

        result = await process_signal(
            raw, mock_request, mock_db, mock_settings, mock_dispatcher,
        )

        assert result == []
        # Only one DB call should have been made (the dedup check)
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_dedup_allows_when_no_prior_success(self):
        """If no successful signal_log exists, processing should proceed."""
        raw = RawSignal(
            user_id=USER_A,
            channel_id=CHANNEL_1,
            raw_message="EURUSD BUY @ 1.1000",
            message_id=42,
        )

        mock_db = AsyncMock()

        # First query: dedup check — returns None (no duplicate)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None

        # Second query: routing rules — return empty (so it exits early after dedup passes)
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[dedup_result, rules_result])

        mock_request = MagicMock()
        mock_settings = MagicMock()
        mock_dispatcher = MagicMock()

        from src.api.workflow import process_signal

        result = await process_signal(
            raw, mock_request, mock_db, mock_settings, mock_dispatcher,
        )

        # Should have passed dedup and hit the routing rules check
        assert result == []
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_dedup_skips_already_ignored(self):
        """If a signal_log with status=ignored exists for the same
        (channel_id, message_id, user_id), the workflow should return
        early — no point re-parsing a non-signal message via OpenAI."""
        raw = RawSignal(
            user_id=USER_A,
            channel_id=CHANNEL_1,
            raw_message="Good morning everyone!",
            message_id=55,
        )

        mock_db = AsyncMock()

        # Dedup check returns existing ID (previously ignored)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = UUID(
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
        )
        mock_db.execute = AsyncMock(return_value=dedup_result)

        mock_request = MagicMock()
        mock_settings = MagicMock()
        mock_dispatcher = MagicMock()

        from src.api.workflow import process_signal

        result = await process_signal(
            raw, mock_request, mock_db, mock_settings, mock_dispatcher,
        )

        assert result == []
        assert mock_db.execute.call_count == 1
