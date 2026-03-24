"""Tests for the Stage 2 dispatch-signal endpoint (two-stage pipeline).

Tests the new POST /api/workflow/dispatch-signal endpoint that processes
individual per-routing-rule dispatch jobs independently.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.core.models import (
    DispatchJob,
    DispatchResult,
    ParsedSignal,
    RawSignalMeta,
    RoutingRule,
)


# ---------------------------------------------------------------------------
# Model unit tests
# ---------------------------------------------------------------------------


SAMPLE_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_RULE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _make_parsed_signal() -> ParsedSignal:
    return ParsedSignal(
        symbol="EURUSD",
        direction="long",
        order_type="market",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profits=[1.1050],
        source_asset_class="forex",
        is_valid_signal=True,
    )


def _make_raw_signal_meta() -> RawSignalMeta:
    return RawSignalMeta(
        user_id=SAMPLE_USER_ID,
        channel_id="-1001234567890",
        message_id=42,
        raw_message="EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050",
        timestamp=datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestDispatchJobModel:
    """Test the new DispatchJob and RawSignalMeta models."""

    def test_dispatch_job_round_trip(self):
        """DispatchJob serialises and deserialises correctly."""
        job = DispatchJob(
            parsed_signal=_make_parsed_signal(),
            routing_rule_id=SAMPLE_RULE_ID,
            raw_signal_meta=_make_raw_signal_meta(),
        )
        json_str = job.model_dump_json()
        restored = DispatchJob.model_validate_json(json_str)
        assert restored.routing_rule_id == SAMPLE_RULE_ID
        assert restored.parsed_signal.symbol == "EURUSD"
        assert restored.raw_signal_meta.user_id == SAMPLE_USER_ID
        assert restored.raw_signal_meta.message_id == 42

    def test_raw_signal_meta_optional_reply(self):
        """RawSignalMeta reply_to_msg_id defaults to None."""
        meta = RawSignalMeta(
            user_id=SAMPLE_USER_ID,
            channel_id="-100",
            message_id=1,
            raw_message="test",
        )
        assert meta.reply_to_msg_id is None

    def test_raw_signal_meta_with_reply(self):
        """RawSignalMeta captures reply_to_msg_id when set."""
        meta = RawSignalMeta(
            user_id=SAMPLE_USER_ID,
            channel_id="-100",
            message_id=2,
            reply_to_msg_id=1,
            raw_message="test",
        )
        assert meta.reply_to_msg_id == 1

    def test_raw_signal_meta_timestamp_preserved(self):
        """RawSignalMeta preserves explicit timestamp through serialisation."""
        ts = datetime(2026, 3, 24, 15, 30, 0, tzinfo=timezone.utc)
        meta = RawSignalMeta(
            user_id=SAMPLE_USER_ID,
            channel_id="-100",
            message_id=99,
            raw_message="test timestamp",
            timestamp=ts,
        )
        json_str = meta.model_dump_json()
        restored = RawSignalMeta.model_validate_json(json_str)
        assert restored.timestamp == ts

    def test_raw_signal_meta_timestamp_defaults(self):
        """RawSignalMeta generates a default timestamp when not provided."""
        meta = RawSignalMeta(
            user_id=SAMPLE_USER_ID,
            channel_id="-100",
            message_id=100,
            raw_message="test default",
        )
        assert meta.timestamp is not None
        assert isinstance(meta.timestamp, datetime)


class TestDispatchResultQueued:
    """Test the new 'queued' status on DispatchResult."""

    def test_queued_status_valid(self):
        dr = DispatchResult(
            routing_rule_id=SAMPLE_RULE_ID,
            status="queued",
        )
        assert dr.status == "queued"
        assert dr.error_message is None

    def test_all_statuses_valid(self):
        for s in ("success", "failed", "ignored", "queued"):
            dr = DispatchResult(routing_rule_id=SAMPLE_RULE_ID, status=s)
            assert dr.status == s


# ---------------------------------------------------------------------------
# Publisher adapter tests
# ---------------------------------------------------------------------------


class TestQStashPublisherDispatchJob:
    """Test enqueue_dispatch_job on QStashPublisher."""

    @pytest.mark.asyncio
    async def test_enqueue_dispatch_job_posts_to_dispatch_url(self):
        from src.adapters.qstash.publisher import QStashPublisher

        publisher = QStashPublisher(
            qstash_token="test-token",
            workflow_url="http://api/api/workflow/process-signal",
            dispatch_url="http://api/api/workflow/dispatch-signal",
        )
        job = DispatchJob(
            parsed_signal=_make_parsed_signal(),
            routing_rule_id=SAMPLE_RULE_ID,
            raw_signal_meta=_make_raw_signal_meta(),
        )

        mock_response = AsyncMock()
        mock_response.is_success = True
        publisher._client.post = AsyncMock(return_value=mock_response)

        await publisher.enqueue_dispatch_job(job)

        publisher._client.post.assert_called_once()
        call_args = publisher._client.post.call_args
        assert "dispatch-signal" in call_args[0][0]

        await publisher.close()

    @pytest.mark.asyncio
    async def test_enqueue_dispatch_job_raises_without_dispatch_url(self):
        from src.adapters.qstash.publisher import QStashPublisher

        publisher = QStashPublisher(
            qstash_token="test-token",
            workflow_url="http://api/api/workflow/process-signal",
        )
        job = DispatchJob(
            parsed_signal=_make_parsed_signal(),
            routing_rule_id=SAMPLE_RULE_ID,
            raw_signal_meta=_make_raw_signal_meta(),
        )

        with pytest.raises(RuntimeError, match="dispatch_url not configured"):
            await publisher.enqueue_dispatch_job(job)

        await publisher.close()


class TestLocalQueueAdapterDispatchJob:
    """Test enqueue_dispatch_job on LocalQueueAdapter."""

    @pytest.mark.asyncio
    async def test_dispatch_callback_invoked(self):
        from src.adapters.qstash.publisher import LocalQueueAdapter

        callback = AsyncMock()
        dispatch_callback = AsyncMock()
        adapter = LocalQueueAdapter(
            callback=callback,
            dispatch_callback=dispatch_callback,
        )
        job = DispatchJob(
            parsed_signal=_make_parsed_signal(),
            routing_rule_id=SAMPLE_RULE_ID,
            raw_signal_meta=_make_raw_signal_meta(),
        )

        await adapter.enqueue_dispatch_job(job)
        dispatch_callback.assert_called_once_with(job)
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_raises_without_callback(self):
        from src.adapters.qstash.publisher import LocalQueueAdapter

        adapter = LocalQueueAdapter(callback=AsyncMock())
        job = DispatchJob(
            parsed_signal=_make_parsed_signal(),
            routing_rule_id=SAMPLE_RULE_ID,
            raw_signal_meta=_make_raw_signal_meta(),
        )

        with pytest.raises(RuntimeError, match="dispatch_callback not configured"):
            await adapter.enqueue_dispatch_job(job)


# ---------------------------------------------------------------------------
# Workflow helper tests
# ---------------------------------------------------------------------------


class TestProcessSingleRule:
    """Test the extracted _process_single_rule module-level function."""

    @pytest.mark.asyncio
    async def test_keyword_blacklist_returns_ignored(self):
        from src.api.workflow import _process_single_rule
        from src.core.models import RawSignal

        rule_row = _mock_rule_row(keyword_blacklist=["spam"])
        raw = RawSignal(
            user_id=SAMPLE_USER_ID,
            channel_id="-100",
            raw_message="This is spam content",
            message_id=1,
        )
        parsed = _make_parsed_signal()
        dispatcher = AsyncMock()

        result, log_kwargs = await _process_single_rule(
            rule_row, raw, parsed, dispatcher,
        )
        assert result.status == "ignored"
        assert "blacklisted" in result.error_message
        dispatcher.dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_dispatch(self):
        from src.api.workflow import _process_single_rule
        from src.core.models import RawSignal

        rule_row = _mock_rule_row()
        raw = RawSignal(
            user_id=SAMPLE_USER_ID,
            channel_id="-100",
            raw_message="EURUSD BUY @ 1.1000",
            message_id=1,
        )
        parsed = _make_parsed_signal()
        dispatcher = AsyncMock()
        dispatcher.dispatch.return_value = DispatchResult(
            routing_rule_id=SAMPLE_RULE_ID,
            status="success",
            webhook_payload={"type": "start_long_market_deal"},
        )

        result, log_kwargs = await _process_single_rule(
            rule_row, raw, parsed, dispatcher,
        )
        assert result.status == "success"
        assert log_kwargs["status"] == "success"
        dispatcher.dispatch.assert_called_once()


def _mock_rule_row(
    keyword_blacklist: list[str] | None = None,
    enabled_actions: list[str] | None = None,
) -> object:
    """Create a mock RoutingRuleModel row for testing."""
    row = type("MockRuleRow", (), {})()
    row.id = SAMPLE_RULE_ID
    row.user_id = SAMPLE_USER_ID
    row.source_channel_id = "-100"
    row.source_channel_name = "Test Channel"
    row.destination_webhook_url = "https://app.sagemaster.com/api/webhook/test"
    row.payload_version = "V1"
    row.symbol_mappings = {}
    row.risk_overrides = {}
    row.webhook_body_template = {
        "type": "",
        "assistId": "test-assist",
        "source": "",
        "symbol": "",
        "date": "",
    }
    row.rule_name = "Test Rule"
    row.destination_label = "Test"
    row.destination_type = "sagemaster_forex"
    row.custom_ai_instructions = None
    row.is_active = True
    row.enabled_actions = enabled_actions
    row.keyword_blacklist = keyword_blacklist or []
    return row
