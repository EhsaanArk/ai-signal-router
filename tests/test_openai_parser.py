"""Tests for src/adapters/openai/parser.py — OpenAI signal parser."""

from __future__ import annotations

import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.openai.parser import OpenAISignalParser, _SYSTEM_PROMPT
from src.core.models import ParsedSignal, RawSignal

SAMPLE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_signal(text: str) -> RawSignal:
    """Create a ``RawSignal`` with the given raw_message text."""
    return RawSignal(
        user_id=SAMPLE_USER_ID,
        channel_id="-1001234567890",
        raw_message=text,
        message_id=1,
    )


def _mock_openai_response(content: str) -> MagicMock:
    """Build a mock ChatCompletion response whose first choice contains *content*."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _build_parser_with_mock() -> tuple[OpenAISignalParser, AsyncMock]:
    """Create an ``OpenAISignalParser`` with a mocked ``AsyncOpenAI`` client.

    Returns (parser, mock_create) where mock_create is the awaitable
    ``client.chat.completions.create``.
    """
    with patch("src.adapters.openai.parser.AsyncOpenAI") as MockClient:
        mock_create = AsyncMock()
        MockClient.return_value.chat.completions.create = mock_create
        parser = OpenAISignalParser(api_key="test-key")
    return parser, mock_create


# ---------------------------------------------------------------------------
# Load fixture data for parametrised tests
# ---------------------------------------------------------------------------

def _load_raw_signals() -> list[str]:
    """Parse ``raw_signals.txt`` and return the 10 signal bodies."""
    text = (FIXTURES_DIR / "raw_signals.txt").read_text()
    signals: list[str] = []
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("--- SIGNAL"):
            if current_lines:
                signals.append("\n".join(current_lines).strip())
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        signals.append("\n".join(current_lines).strip())
    return signals


def _load_expected_payloads() -> list[dict]:
    """Load ``expected_payloads.json``."""
    return json.loads((FIXTURES_DIR / "expected_payloads.json").read_text())


_RAW_SIGNALS = _load_raw_signals()
_EXPECTED_PAYLOADS = _load_expected_payloads()


def _expected_to_openai_json(expected: dict) -> str:
    """Convert a fixture expected payload into a JSON string the mock OpenAI
    response should return, matching the schema ``OpenAISignalParser`` expects.
    """
    parsed = expected["parsed"]
    if parsed["status"] == "ignored":
        return json.dumps({
            "symbol": "UNKNOWN",
            "direction": "long",
            "order_type": "market",
            "entry_price": None,
            "stop_loss": None,
            "take_profits": [],
            "source_asset_class": "forex",
            "is_valid_signal": False,
            "ignore_reason": parsed["reason"],
        })

    direction_map = {"BUY": "long", "SELL": "short"}
    symbol = parsed["symbol"]
    # Determine asset class using the same heuristics as the system prompt.
    if symbol in ("GOLD", "XAUUSD", "XAGUSD", "SILVER"):
        asset_class = "commodities"
    elif symbol in ("BTCUSD", "BTCUSDT", "ETHUSD", "ETHUSDT",
                     "BTC/USD", "BTC/USDT", "ETH/USD", "ETH/USDT") or "/" in symbol:
        asset_class = "crypto"
    elif symbol in ("US30", "NAS100", "SPX500", "DAX", "USTEC"):
        asset_class = "indices"
    else:
        asset_class = "forex"

    return json.dumps({
        "symbol": symbol,
        "direction": direction_map[parsed["direction"]],
        "order_type": "market",
        "entry_price": parsed["entry_price"],
        "stop_loss": parsed["stop_loss"],
        "take_profits": parsed["take_profits"],
        "source_asset_class": asset_class,
        "is_valid_signal": True,
        "ignore_reason": None,
    })


# ---------------------------------------------------------------------------
# 1. Valid BUY signal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_valid_buy_signal():
    """A BUY signal should be parsed into a ParsedSignal with correct fields."""
    parser, mock_create = _build_parser_with_mock()

    openai_json = json.dumps({
        "symbol": "EURUSD",
        "direction": "long",
        "order_type": "market",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profits": [1.1050, 1.1100],
        "source_asset_class": "forex",
        "is_valid_signal": True,
        "ignore_reason": None,
    })
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal("BUY EURUSD @ 1.1000\nSL: 1.0950\nTP1: 1.1050\nTP2: 1.1100")
    result = await parser.parse(raw)

    assert isinstance(result, ParsedSignal)
    assert result.symbol == "EURUSD"
    assert result.direction == "long"
    assert result.order_type == "market"
    assert result.entry_price == 1.1000
    assert result.stop_loss == 1.0950
    assert result.take_profits == [1.1050, 1.1100]
    assert result.source_asset_class == "forex"
    assert result.is_valid_signal is True
    assert result.ignore_reason is None


# ---------------------------------------------------------------------------
# 2. Valid SELL signal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_valid_sell_signal():
    """A SELL signal should be parsed with direction='short'."""
    parser, mock_create = _build_parser_with_mock()

    openai_json = json.dumps({
        "symbol": "XAUUSD",
        "direction": "short",
        "order_type": "market",
        "entry_price": 2350.50,
        "stop_loss": 2360.00,
        "take_profits": [2330.00],
        "source_asset_class": "commodities",
        "is_valid_signal": True,
        "ignore_reason": None,
    })
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal("SELL XAUUSD\nEntry: 2350.50\nSL: 2360.00\nTP: 2330.00")
    result = await parser.parse(raw)

    assert isinstance(result, ParsedSignal)
    assert result.symbol == "XAUUSD"
    assert result.direction == "short"
    assert result.entry_price == 2350.50
    assert result.stop_loss == 2360.00
    assert result.take_profits == [2330.00]
    assert result.source_asset_class == "commodities"
    assert result.is_valid_signal is True
    assert result.ignore_reason is None


# ---------------------------------------------------------------------------
# 3. Non-signal message (news/chat)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_non_signal_message():
    """A chat/news message should come back as is_valid_signal=False."""
    parser, mock_create = _build_parser_with_mock()

    openai_json = json.dumps({
        "symbol": "UNKNOWN",
        "direction": "long",
        "order_type": "market",
        "entry_price": None,
        "stop_loss": None,
        "take_profits": [],
        "source_asset_class": "forex",
        "is_valid_signal": False,
        "ignore_reason": "General chat/news, no trading parameters found.",
    })
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal("Good morning VIPs! Huge news coming out today, stay safe.")
    result = await parser.parse(raw)

    assert result.is_valid_signal is False
    assert result.ignore_reason is not None
    assert "chat" in result.ignore_reason.lower() or "news" in result.ignore_reason.lower()


# ---------------------------------------------------------------------------
# 4. Malformed JSON from OpenAI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_malformed_json():
    """When OpenAI returns non-JSON, the parser should return an invalid signal gracefully."""
    parser, mock_create = _build_parser_with_mock()

    mock_create.return_value = _mock_openai_response("This is not JSON at all {{{")

    raw = _make_raw_signal("BUY EURUSD")
    result = await parser.parse(raw)

    assert isinstance(result, ParsedSignal)
    assert result.is_valid_signal is False
    assert result.symbol == "UNKNOWN"
    assert result.ignore_reason is not None
    assert "JSON decode error" in result.ignore_reason


# ---------------------------------------------------------------------------
# 5. OpenAI API exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_openai_api_error():
    """When the OpenAI API raises, the parser should return an invalid signal."""
    parser, mock_create = _build_parser_with_mock()

    mock_create.side_effect = RuntimeError("Connection timed out")

    raw = _make_raw_signal("BUY EURUSD")
    result = await parser.parse(raw)

    assert isinstance(result, ParsedSignal)
    assert result.is_valid_signal is False
    assert result.symbol == "UNKNOWN"
    assert result.ignore_reason is not None
    assert "AI parser error" in result.ignore_reason


# ---------------------------------------------------------------------------
# 6. System prompt included in API call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_system_prompt_included_in_api_call():
    """The system prompt must be sent as the first message in the API call."""
    parser, mock_create = _build_parser_with_mock()

    openai_json = json.dumps({"is_valid_signal": False, "ignore_reason": "test"})
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal("Hello world")
    await parser.parse(raw)

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")

    assert messages is not None
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == _SYSTEM_PROMPT
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello world"


# ---------------------------------------------------------------------------
# 7. original_context prepends correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_with_original_context():
    """When original_context is provided, the user message should contain both
    [ORIGINAL SIGNAL] and [FOLLOW-UP MESSAGE] sections."""
    parser, mock_create = _build_parser_with_mock()

    openai_json = json.dumps({
        "action": "partial_close",
        "symbol": "EURUSD",
        "direction": "long",
        "order_type": "market",
        "entry_price": None,
        "stop_loss": None,
        "take_profits": [],
        "lots": "0.5",
        "source_asset_class": "forex",
        "is_valid_signal": True,
        "ignore_reason": None,
    })
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal("Close half")
    original_text = "BUY EURUSD @ 1.1000\nSL: 1.0950\nTP1: 1.1050"
    result = await parser.parse(raw, original_context=original_text)

    # Verify the user message was constructed with context
    call_kwargs = mock_create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_msg = messages[1]["content"]
    assert "[ORIGINAL SIGNAL]" in user_msg
    assert original_text in user_msg
    assert "[FOLLOW-UP MESSAGE]" in user_msg
    assert "Close half" in user_msg

    # Verify the parsed result
    assert result.action == "partial_close"
    assert result.symbol == "EURUSD"
    assert result.is_valid_signal is True


@pytest.mark.asyncio
async def test_parse_without_original_context():
    """When original_context is None, the user message should be the raw message only."""
    parser, mock_create = _build_parser_with_mock()

    openai_json = json.dumps({
        "symbol": "EURUSD",
        "direction": "long",
        "order_type": "market",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profits": [1.1050],
        "source_asset_class": "forex",
        "is_valid_signal": True,
        "ignore_reason": None,
    })
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal("BUY EURUSD @ 1.1000\nSL: 1.0950\nTP1: 1.1050")
    result = await parser.parse(raw, original_context=None)

    call_kwargs = mock_create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_msg = messages[1]["content"]
    assert "[ORIGINAL SIGNAL]" not in user_msg
    assert user_msg == "BUY EURUSD @ 1.1000\nSL: 1.0950\nTP1: 1.1050"

    assert result.is_valid_signal is True
    assert result.symbol == "EURUSD"


# ---------------------------------------------------------------------------
# 9. Parametrised fixture signals (all 10)
# ---------------------------------------------------------------------------

_FIXTURE_IDS = [p["id"] for p in _EXPECTED_PAYLOADS]
_FIXTURE_PARAMS = list(zip(_RAW_SIGNALS, _EXPECTED_PAYLOADS, strict=False))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_text, expected",
    _FIXTURE_PARAMS,
    ids=_FIXTURE_IDS,
)
async def test_fixture_signals(raw_text: str, expected: dict):
    """Each of the 10 fixture signals should be parsed correctly when OpenAI
    returns the corresponding expected payload.
    """
    parser, mock_create = _build_parser_with_mock()

    openai_json = _expected_to_openai_json(expected)
    mock_create.return_value = _mock_openai_response(openai_json)

    raw = _make_raw_signal(raw_text)
    result = await parser.parse(raw)

    parsed = expected["parsed"]

    if parsed["status"] == "ignored":
        assert result.is_valid_signal is False
        assert result.ignore_reason is not None
        assert result.ignore_reason == parsed["reason"]
    else:
        assert result.is_valid_signal is True
        assert result.symbol == parsed["symbol"]

        direction_map = {"BUY": "long", "SELL": "short"}
        assert result.direction == direction_map[parsed["direction"]]
        assert result.entry_price == parsed["entry_price"]
        assert result.stop_loss == parsed["stop_loss"]
        assert result.take_profits == parsed["take_profits"]
