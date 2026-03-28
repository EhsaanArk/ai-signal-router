"""Unit tests for POST /parse-preview endpoint.

Tests the parse-preview logic by calling the inner function directly
with the slowapi rate limiter disabled (it requires a real ASGI Request).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.api.deps import limiter
from src.core.exceptions import ExternalServiceError, InputValidationError
from src.core.models import ParsedSignal, RawSignal


# ---------------------------------------------------------------------------
# Import the endpoint function and request/response models
# ---------------------------------------------------------------------------

from src.api.routes import (
    ParsePreviewRequest,
    ParsePreviewResponse,
    parse_preview,
)


# ---------------------------------------------------------------------------
# Disable the rate limiter for unit tests (it needs a real Starlette Request)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_limiter():
    limiter.enabled = False
    yield
    limiter.enabled = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_USER_ID = "11111111-1111-1111-1111-111111111111"


def _mock_user():
    """Create a mock user with the minimum fields needed."""
    user = MagicMock()
    user.id = SAMPLE_USER_ID
    return user


def _mock_request():
    """Create a mock FastAPI Request (minimal, limiter is disabled)."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


def _valid_parsed_signal(**overrides) -> ParsedSignal:
    defaults = dict(
        action="entry",
        symbol="XAUUSD",
        direction="long",
        order_type="market",
        source_asset_class="forex",
        is_valid_signal=True,
        stop_loss=2300.0,
        take_profits=[2350.0],
    )
    defaults.update(overrides)
    return ParsedSignal(**defaults)


def _invalid_parsed_signal(**overrides) -> ParsedSignal:
    return ParsedSignal(
        symbol="UNKNOWN",
        direction="long",
        order_type="market",
        source_asset_class="forex",
        is_valid_signal=False,
        ignore_reason="Not a trading signal",
        **overrides,
    )


# ---------------------------------------------------------------------------
# Request model validation
# ---------------------------------------------------------------------------


class TestParsePreviewRequestValidation:
    """Test Pydantic validation on the request model."""

    def test_valid_request(self):
        req = ParsePreviewRequest(message="Buy XAUUSD")
        assert req.message == "Buy XAUUSD"
        assert req.destination_type == "sagemaster_forex"

    def test_empty_message_rejected(self):
        with pytest.raises(Exception):
            ParsePreviewRequest(message="")

    def test_max_length_enforced(self):
        with pytest.raises(Exception):
            ParsePreviewRequest(message="x" * 2001)

    def test_max_length_boundary(self):
        req = ParsePreviewRequest(message="x" * 2000)
        assert len(req.message) == 2000


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class TestParsePreviewResponse:
    """Test the response model strips internal fields."""

    def test_valid_signal_response(self):
        resp = ParsePreviewResponse(
            is_valid_signal=True,
            action="entry",
            symbol="XAUUSD",
            direction="long",
            order_type="market",
            take_profits=[2350.0],
        )
        assert resp.is_valid_signal is True
        assert resp.action == "entry"

    def test_invalid_signal_response(self):
        resp = ParsePreviewResponse(
            is_valid_signal=False,
            ignore_reason="Not a trading signal",
        )
        assert resp.is_valid_signal is False
        assert resp.action is None
        assert resp.ignore_reason == "Not a trading signal"


# ---------------------------------------------------------------------------
# Endpoint logic tests (with mocked parser)
# ---------------------------------------------------------------------------


class TestParsePreviewEndpoint:
    """Test the parse_preview endpoint function with mocked dependencies."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        """Provide a settings object with OPENAI_API_KEY set."""
        mock_settings = MagicMock()
        mock_settings.OPENAI_API_KEY = "test-key"
        with patch("src.api.routes.routing_rules.get_settings", return_value=mock_settings):
            yield mock_settings

    @pytest.fixture
    def _patch_no_api_key(self, _patch_settings):
        """Override settings to have no OPENAI_API_KEY."""
        _patch_settings.OPENAI_API_KEY = ""

    async def test_valid_signal_returns_parsed_result(self):
        """Happy path: parser returns a valid signal."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _valid_parsed_signal()

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Buy XAUUSD SL 2300 TP 2350"),
                current_user=_mock_user(),
            )

        assert result.is_valid_signal is True
        assert result.action == "entry"
        assert result.symbol == "XAUUSD"
        assert result.direction == "long"
        assert result.stop_loss == 2300.0
        assert result.take_profits == [2350.0]

    async def test_invalid_signal_returns_reason(self):
        """Parser returns is_valid_signal=False with ignore_reason."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _invalid_parsed_signal()

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Hello world"),
                current_user=_mock_user(),
            )

        assert result.is_valid_signal is False
        assert result.action is None
        assert result.symbol is None
        assert result.ignore_reason == "Not a trading signal"

    async def test_unknown_symbol_stripped(self):
        """When parser returns 'UNKNOWN' symbol, response shows None."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _valid_parsed_signal(symbol="UNKNOWN")

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Buy something"),
                current_user=_mock_user(),
            )

        assert result.is_valid_signal is True
        assert result.symbol is None  # "UNKNOWN" stripped

    async def test_timeout_raises_external_service_error(self):
        """When parser takes >10s, endpoint raises ExternalServiceError."""
        mock_parser = AsyncMock()

        async def slow_parse(*args, **kwargs):
            await asyncio.sleep(20)
            return _valid_parsed_signal()

        mock_parser.parse.side_effect = slow_parse

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            with pytest.raises(ExternalServiceError) as exc_info:
                await parse_preview(
                    request=_mock_request(),
                    body=ParsePreviewRequest(message="Buy XAUUSD"),
                    current_user=_mock_user(),
                )
            assert "timed out" in str(exc_info.value).lower()

    async def test_parser_exception_raises_input_validation_error(self):
        """When parser raises an unexpected error, endpoint raises InputValidationError."""
        mock_parser = AsyncMock()
        mock_parser.parse.side_effect = RuntimeError("OpenAI down")

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            with pytest.raises(InputValidationError):
                await parse_preview(
                    request=_mock_request(),
                    body=ParsePreviewRequest(message="Buy XAUUSD"),
                    current_user=_mock_user(),
                )

    async def test_no_api_key_raises_external_service_error(self, _patch_no_api_key):
        """When OPENAI_API_KEY is not set, endpoint raises ExternalServiceError."""
        with pytest.raises(ExternalServiceError):
            await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Buy XAUUSD"),
                current_user=_mock_user(),
            )

    async def test_stub_signal_uses_preview_channel(self):
        """Verify the stub RawSignal uses 'preview' as channel_id."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _valid_parsed_signal()

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Buy XAUUSD"),
                current_user=_mock_user(),
            )

        # Verify the RawSignal passed to parser.parse()
        call_args = mock_parser.parse.call_args
        raw_signal = call_args[0][0]
        assert raw_signal.channel_id == "preview"
        assert raw_signal.message_id == 0
        assert raw_signal.raw_message == "Buy XAUUSD"


# ---------------------------------------------------------------------------
# Forwarding verdict tests (enhanced parse-preview fields)
# ---------------------------------------------------------------------------


class TestParsePreviewForwardingVerdict:
    """Test the route_would_forward / blocked_reason / display_action_label fields."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        mock_settings = MagicMock()
        mock_settings.OPENAI_API_KEY = "test-key"
        with patch("src.api.routes.routing_rules.get_settings", return_value=mock_settings):
            yield mock_settings

    async def test_valid_signal_no_enabled_actions_forwards(self):
        """When enabled_actions is None (all enabled), signal should forward."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _valid_parsed_signal()

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Buy XAUUSD", enabled_actions=None),
                current_user=_mock_user(),
            )

        assert result.route_would_forward is True
        assert result.blocked_reason is None
        assert result.display_action_label == "start_long_market_deal"

    async def test_valid_signal_action_enabled_forwards(self):
        """When the parsed action is in enabled_actions, signal should forward."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _valid_parsed_signal()

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(
                    message="Buy XAUUSD",
                    enabled_actions=["start_long_market_deal", "close_order_at_market_price"],
                ),
                current_user=_mock_user(),
            )

        assert result.route_would_forward is True
        assert result.blocked_reason is None

    async def test_valid_signal_action_disabled_blocked(self):
        """When the parsed action is NOT in enabled_actions, signal should be blocked."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _valid_parsed_signal(
            action="close_position", symbol="XAUUSD",
        )

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(
                    message="Close XAUUSD",
                    enabled_actions=["start_long_market_deal"],
                ),
                current_user=_mock_user(),
            )

        assert result.route_would_forward is False
        assert "disabled" in result.blocked_reason
        assert result.display_action_label == "close_order_at_market_price"

    async def test_invalid_signal_no_verdict(self):
        """When signal is invalid, forwarding verdict should be null."""
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = _invalid_parsed_signal()

        with patch("src.adapters.openai.OpenAISignalParser", return_value=mock_parser):
            result = await parse_preview(
                request=_mock_request(),
                body=ParsePreviewRequest(message="Hello world"),
                current_user=_mock_user(),
            )

        assert result.route_would_forward is None
        assert result.blocked_reason is None
        assert result.display_action_label is None
