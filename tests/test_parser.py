"""Unit tests for src/core/parser.parse_and_validate()."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.core.models import ParsedSignal, RawSignal
from src.core.parser import parse_and_validate
from tests.conftest import SAMPLE_USER_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_parser(return_value: ParsedSignal | None = None, side_effect=None):
    """Create a mock satisfying the SignalParser protocol."""
    parser = AsyncMock()
    if side_effect is not None:
        parser.parse.side_effect = side_effect
    else:
        parser.parse.return_value = return_value
    return parser


def _raw() -> RawSignal:
    """Convenience factory for a sample RawSignal."""
    return RawSignal(
        user_id=SAMPLE_USER_ID,
        channel_id="-1001234567890",
        raw_message="EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050",
        message_id=99,
    )


# ---------------------------------------------------------------------------
# 1. Valid signal — has symbol + direction
# ---------------------------------------------------------------------------


class TestParseAndValidateValidSignal:
    """parse_and_validate with a fully valid ParsedSignal."""

    async def test_returns_parsed_signal(self, sample_parsed_signal: ParsedSignal):
        parser = _make_mock_parser(return_value=sample_parsed_signal)

        result = await parse_and_validate(parser, _raw())

        assert result is sample_parsed_signal
        parser.parse.assert_awaited_once()

    async def test_valid_short_signal(self):
        signal = ParsedSignal(symbol="GBPUSD", direction="short")
        parser = _make_mock_parser(return_value=signal)

        result = await parse_and_validate(parser, _raw())

        assert result.symbol == "GBPUSD"
        assert result.direction == "short"
        assert result.is_valid_signal is True

    async def test_preserves_all_fields(self):
        signal = ParsedSignal(
            symbol="XAUUSD",
            direction="long",
            order_type="limit",
            entry_price=2350.50,
            stop_loss=2340.00,
            take_profits=[2360.00, 2370.00],
            source_asset_class="commodities",
        )
        parser = _make_mock_parser(return_value=signal)

        result = await parse_and_validate(parser, _raw())

        assert result.order_type == "limit"
        assert result.entry_price == 2350.50
        assert result.stop_loss == 2340.00
        assert result.take_profits == [2360.00, 2370.00]
        assert result.source_asset_class == "commodities"


# ---------------------------------------------------------------------------
# 2. Invalid signal — is_valid_signal=False
# ---------------------------------------------------------------------------


class TestParseAndValidateInvalidSignal:
    """parse_and_validate when the parser marks the signal as not valid."""

    async def test_returns_signal_with_ignore_reason(self):
        signal = ParsedSignal.model_construct(
            symbol="",
            direction="long",
            is_valid_signal=False,
            ignore_reason="Message is a greeting, not a trading signal.",
        )
        parser = _make_mock_parser(return_value=signal)

        result = await parse_and_validate(parser, _raw())

        assert result.is_valid_signal is False
        assert result.ignore_reason == "Message is a greeting, not a trading signal."

    async def test_skips_validation_when_not_valid(self):
        """Even with empty symbol/direction, no ValueError is raised."""
        signal = ParsedSignal.model_construct(
            symbol="",
            direction=None,
            is_valid_signal=False,
            ignore_reason="Not a signal.",
        )
        parser = _make_mock_parser(return_value=signal)

        result = await parse_and_validate(parser, _raw())

        assert result.is_valid_signal is False
        assert result.direction is None


# ---------------------------------------------------------------------------
# 3. Parser raises an exception — graceful error propagation
# ---------------------------------------------------------------------------


class TestParseAndValidateParserException:
    """parse_and_validate when the parser itself raises."""

    async def test_propagates_runtime_error(self):
        parser = _make_mock_parser(side_effect=RuntimeError("LLM timeout"))

        with pytest.raises(RuntimeError, match="LLM timeout"):
            await parse_and_validate(parser, _raw())

    async def test_propagates_connection_error(self):
        parser = _make_mock_parser(side_effect=ConnectionError("API unreachable"))

        with pytest.raises(ConnectionError, match="API unreachable"):
            await parse_and_validate(parser, _raw())

    async def test_propagates_generic_exception(self):
        parser = _make_mock_parser(side_effect=Exception("unexpected failure"))

        with pytest.raises(Exception, match="unexpected failure"):
            await parse_and_validate(parser, _raw())


# ---------------------------------------------------------------------------
# 4. Edge cases — missing symbol or direction on a "valid" signal
# ---------------------------------------------------------------------------


class TestParseAndValidateEdgeCases:
    """Edge cases: symbol/direction missing on signals marked as valid."""

    async def test_missing_symbol_raises_value_error(self):
        """Signal has direction but no symbol -> ValueError."""
        signal = ParsedSignal.model_construct(
            symbol="",
            direction="long",
            is_valid_signal=True,
            order_type="market",
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            source_asset_class="forex",
            ignore_reason=None,
        )
        parser = _make_mock_parser(return_value=signal)

        with pytest.raises(ValueError, match="symbol.*missing or empty"):
            await parse_and_validate(parser, _raw())

    async def test_none_symbol_raises_value_error(self):
        """Symbol is None on a valid signal -> ValueError."""
        signal = ParsedSignal.model_construct(
            symbol=None,
            direction="long",
            is_valid_signal=True,
            order_type="market",
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            source_asset_class="forex",
            ignore_reason=None,
        )
        parser = _make_mock_parser(return_value=signal)

        with pytest.raises(ValueError, match="symbol.*missing or empty"):
            await parse_and_validate(parser, _raw())

    async def test_whitespace_only_symbol_raises_value_error(self):
        """Symbol is whitespace-only on a valid signal -> ValueError."""
        signal = ParsedSignal.model_construct(
            symbol="   ",
            direction="short",
            is_valid_signal=True,
            order_type="market",
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            source_asset_class="forex",
            ignore_reason=None,
        )
        parser = _make_mock_parser(return_value=signal)

        with pytest.raises(ValueError, match="symbol.*missing or empty"):
            await parse_and_validate(parser, _raw())

    async def test_missing_direction_raises_value_error(self):
        """Signal has symbol but no direction -> ValueError."""
        signal = ParsedSignal.model_construct(
            symbol="EURUSD",
            direction=None,
            is_valid_signal=True,
            order_type="market",
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            source_asset_class="forex",
            ignore_reason=None,
        )
        parser = _make_mock_parser(return_value=signal)

        with pytest.raises(ValueError, match="direction.*missing or.*invalid"):
            await parse_and_validate(parser, _raw())

    async def test_invalid_direction_raises_value_error(self):
        """Direction is not 'long' or 'short' -> ValueError."""
        signal = ParsedSignal.model_construct(
            symbol="EURUSD",
            direction="buy",
            is_valid_signal=True,
            order_type="market",
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            source_asset_class="forex",
            ignore_reason=None,
        )
        parser = _make_mock_parser(return_value=signal)

        with pytest.raises(ValueError, match="direction.*missing or.*invalid.*buy"):
            await parse_and_validate(parser, _raw())


# ---------------------------------------------------------------------------
# 5. Mock verification — parser is called exactly once with the raw signal
# ---------------------------------------------------------------------------


class TestParserMockInteraction:
    """Verify the mock SignalParser is invoked correctly."""

    async def test_parser_receives_raw_signal(self):
        signal = ParsedSignal(symbol="USDJPY", direction="long")
        parser = _make_mock_parser(return_value=signal)
        raw = _raw()

        await parse_and_validate(parser, raw)

        parser.parse.assert_awaited_once_with(raw)

    async def test_parser_not_called_extra_times(self):
        signal = ParsedSignal(symbol="USDJPY", direction="short")
        parser = _make_mock_parser(return_value=signal)

        await parse_and_validate(parser, _raw())

        assert parser.parse.await_count == 1
