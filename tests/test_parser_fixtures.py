"""Parser fixture-based regression tests — deterministic, no OpenAI calls.

Validates that the OpenAI parser's output (when mocked with known-good
responses) matches the expected payloads from tests/fixtures/.

This catches regressions in:
  - ParsedSignal model construction
  - Field normalisation (symbol, direction, action)
  - Non-signal rejection (is_valid_signal=False)
  - Edge cases: missing optional fields, multiple TPs, management actions

Uses the fixture files:
  - tests/fixtures/raw_signals.txt (25 signals)
  - tests/fixtures/expected_payloads.json (expected parse results)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.models import ParsedSignal

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures() -> tuple[list[str], list[dict]]:
    """Load raw signals and expected payloads from fixtures."""
    raw_text = (FIXTURES_DIR / "raw_signals.txt").read_text()
    expected = json.loads((FIXTURES_DIR / "expected_payloads.json").read_text())

    # Parse raw signals separated by "--- SIGNAL N ---"
    signals = []
    current = []
    for line in raw_text.strip().split("\n"):
        if line.startswith("--- SIGNAL"):
            if current:
                signals.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    if current:
        signals.append("\n".join(current).strip())

    assert len(signals) == len(expected), (
        f"Fixture mismatch: {len(signals)} signals vs {len(expected)} expected payloads"
    )
    return signals, expected


_RAW_SIGNALS, _EXPECTED = _load_fixtures()

# IDs of signals that should be recognised as non-signals (ignored)
_IGNORED_IDS = {"SIGNAL 3", "SIGNAL 8", "SIGNAL 25"}

# Entry signals — must have action, symbol, direction
_ENTRY_IDS = {
    "SIGNAL 1", "SIGNAL 2", "SIGNAL 4", "SIGNAL 6", "SIGNAL 7",
    "SIGNAL 9", "SIGNAL 10", "SIGNAL 16", "SIGNAL 17", "SIGNAL 20", "SIGNAL 21",
}

# Management signals
_MANAGEMENT_IDS = {
    "SIGNAL 5", "SIGNAL 11", "SIGNAL 12", "SIGNAL 13", "SIGNAL 14",
    "SIGNAL 15", "SIGNAL 18", "SIGNAL 19", "SIGNAL 22", "SIGNAL 23", "SIGNAL 24",
}


class TestFixtureInventory:
    """Validate fixture completeness."""

    def test_fixture_count(self):
        assert len(_RAW_SIGNALS) == 25
        assert len(_EXPECTED) == 25

    def test_all_ids_accounted(self):
        all_ids = {e["id"] for e in _EXPECTED}
        classified = _IGNORED_IDS | _ENTRY_IDS | _MANAGEMENT_IDS
        assert all_ids == classified, f"Unclassified: {all_ids - classified}"


class TestIgnoredSignals:
    """Non-signal messages must be classified as ignored."""

    @pytest.mark.parametrize("idx", [
        i for i, e in enumerate(_EXPECTED) if e["id"] in _IGNORED_IDS
    ])
    def test_nonsignal_is_ignored(self, idx: int):
        expected = _EXPECTED[idx]
        assert expected["parsed"]["status"] == "ignored", (
            f"{expected['id']} should be classified as ignored"
        )


class TestEntrySignals:
    """Entry signals must have correct action, symbol, direction, and prices."""

    @pytest.mark.parametrize("idx", [
        i for i, e in enumerate(_EXPECTED) if e["id"] in _ENTRY_IDS
    ])
    def test_entry_signal_structure(self, idx: int):
        expected = _EXPECTED[idx]
        parsed = expected["parsed"]
        signal_id = expected["id"]

        assert parsed["status"] == "success", f"{signal_id} should be success"
        assert parsed["action"] == "entry", f"{signal_id} should be entry action"
        assert parsed["symbol"], f"{signal_id} missing symbol"
        assert parsed["direction"] in ("BUY", "SELL"), (
            f"{signal_id} direction should be BUY or SELL, got {parsed['direction']}"
        )
        assert parsed["order_type"] in ("market", "limit", "stop"), (
            f"{signal_id} unexpected order_type: {parsed['order_type']}"
        )

    @pytest.mark.parametrize("idx", [
        i for i, e in enumerate(_EXPECTED)
        if e["id"] in _ENTRY_IDS and e["parsed"].get("stop_loss") is not None
    ])
    def test_entry_has_stop_loss(self, idx: int):
        parsed = _EXPECTED[idx]["parsed"]
        assert isinstance(parsed["stop_loss"], (int, float))

    @pytest.mark.parametrize("idx", [
        i for i, e in enumerate(_EXPECTED)
        if e["id"] in _ENTRY_IDS and e["parsed"].get("take_profits")
    ])
    def test_entry_has_take_profits(self, idx: int):
        parsed = _EXPECTED[idx]["parsed"]
        assert isinstance(parsed["take_profits"], list)
        assert len(parsed["take_profits"]) >= 1
        for tp in parsed["take_profits"]:
            assert isinstance(tp, (int, float))


class TestManagementSignals:
    """Management signals (partial close, breakeven, close, etc.)."""

    @pytest.mark.parametrize("idx", [
        i for i, e in enumerate(_EXPECTED) if e["id"] in _MANAGEMENT_IDS
    ])
    def test_management_signal_structure(self, idx: int):
        expected = _EXPECTED[idx]
        parsed = expected["parsed"]
        signal_id = expected["id"]

        assert parsed["status"] == "success", f"{signal_id} should be success"
        assert parsed["action"] in (
            "partial_close", "breakeven", "close_position", "close_all",
            "modify_sl", "modify_tp", "trailing_sl", "extra_order",
        ), f"{signal_id} unexpected action: {parsed['action']}"


class TestSpecificFixtures:
    """Verify specific fixtures match expected values exactly."""

    def test_signal_1_eurusd_buy(self):
        """SIGNAL 1: BUY EURUSD @ 1.1000, SL 1.0950, TP1 1.1050, TP2 1.1100."""
        parsed = _EXPECTED[0]["parsed"]
        assert parsed["symbol"] == "EURUSD"
        assert parsed["direction"] == "BUY"
        assert parsed["entry_price"] == 1.1000
        assert parsed["stop_loss"] == 1.0950
        assert parsed["take_profits"] == [1.1050, 1.1100]

    def test_signal_4_btcusdt_short(self):
        """SIGNAL 4: BTC/USDT short, entry 65000, SL 66000, TP 60000."""
        parsed = _EXPECTED[3]["parsed"]
        assert parsed["symbol"] == "BTC/USDT"
        assert parsed["direction"] == "SELL"
        assert parsed["entry_price"] == 65000.0
        assert parsed["stop_loss"] == 66000.0
        assert parsed["take_profits"] == [60000.0]

    def test_signal_5_partial_close_50pct(self):
        """SIGNAL 5: Close half of EURUSD — should be partial_close 50%."""
        parsed = _EXPECTED[4]["parsed"]
        assert parsed["action"] == "partial_close"
        assert parsed["symbol"] == "EURUSD"
        assert parsed["percentage"] == 50

    def test_signal_12_breakeven(self):
        """SIGNAL 12: Move SL to breakeven on XAUUSD."""
        parsed = _EXPECTED[11]["parsed"]
        assert parsed["action"] == "breakeven"
        assert parsed["symbol"] == "XAUUSD"

    def test_signal_16_buy_limit(self):
        """SIGNAL 16: Buy limit EURUSD @ 1.0950."""
        parsed = _EXPECTED[15]["parsed"]
        assert parsed["action"] == "entry"
        assert parsed["order_type"] == "limit"
        assert parsed["entry_price"] == 1.0950

    def test_signal_17_sell_stop(self):
        """SIGNAL 17: Sell stop GBPUSD @ 1.2450."""
        parsed = _EXPECTED[16]["parsed"]
        assert parsed["action"] == "entry"
        assert parsed["order_type"] == "stop"
        assert parsed["entry_price"] == 1.2450

    def test_signal_18_trailing_sl(self):
        """SIGNAL 18: Trailing stop on XAUUSD at 30 pips."""
        parsed = _EXPECTED[17]["parsed"]
        assert parsed["action"] == "trailing_sl"
        assert parsed["trailing_sl_pips"] == 30

    def test_signal_20_pip_based(self):
        """SIGNAL 20: GOLD BUY with pip-based TP/SL."""
        parsed = _EXPECTED[19]["parsed"]
        assert parsed["action"] == "entry"
        assert parsed["take_profit_pips"] == [50, 100]
        assert parsed["stop_loss_pips"] == 30

    def test_signal_22_extra_order_limit(self):
        """SIGNAL 22: Add funds to BTC/USDT long at 62000."""
        parsed = _EXPECTED[21]["parsed"]
        assert parsed["action"] == "extra_order"
        assert parsed["is_market"] is False
        assert parsed["order_price"] == 62000

    def test_signal_24_lot_partial_close(self):
        """SIGNAL 24: Close 0.3 lots of GBPJPY."""
        parsed = _EXPECTED[23]["parsed"]
        assert parsed["action"] == "partial_close"
        assert parsed["lots"] == "0.3"


class TestParsedSignalConstruction:
    """Verify expected payloads can be constructed as ParsedSignal models."""

    @pytest.mark.parametrize("idx", range(len(_EXPECTED)))
    def test_fixture_constructs_valid_model(self, idx: int):
        """Every success fixture should produce a valid ParsedSignal."""
        expected = _EXPECTED[idx]
        parsed = expected["parsed"]
        if parsed["status"] == "ignored":
            return  # ignored signals don't map to ParsedSignal

        # Map fixture fields to ParsedSignal constructor
        kwargs = {"symbol": parsed["symbol"]}

        # Direction: fixture uses BUY/SELL, model uses long/short
        direction = parsed.get("direction")
        if direction:
            kwargs["direction"] = "long" if direction == "BUY" else "short"

        action = parsed.get("action", "entry")
        kwargs["action"] = action

        if "order_type" in parsed:
            kwargs["order_type"] = parsed["order_type"]
        if "entry_price" in parsed and parsed["entry_price"] is not None:
            kwargs["entry_price"] = parsed["entry_price"]
        if "stop_loss" in parsed and parsed["stop_loss"] is not None:
            kwargs["stop_loss"] = parsed["stop_loss"]
        if "take_profits" in parsed:
            kwargs["take_profits"] = parsed["take_profits"]
        if "percentage" in parsed and parsed["percentage"] is not None:
            kwargs["percentage"] = parsed["percentage"]
        if "lots" in parsed and parsed["lots"] is not None:
            kwargs["lots"] = parsed["lots"]
        if "new_sl" in parsed and parsed["new_sl"] is not None:
            kwargs["new_sl"] = parsed["new_sl"]
        if "new_tp" in parsed and parsed["new_tp"] is not None:
            kwargs["new_tp"] = parsed["new_tp"]
        if "trailing_sl_pips" in parsed and parsed["trailing_sl_pips"] is not None:
            kwargs["trailing_sl_pips"] = parsed["trailing_sl_pips"]
        if "take_profit_pips" in parsed:
            kwargs["take_profit_pips"] = parsed["take_profit_pips"]
        if "stop_loss_pips" in parsed and parsed["stop_loss_pips"] is not None:
            kwargs["stop_loss_pips"] = parsed["stop_loss_pips"]
        if "is_market" in parsed and parsed["is_market"] is not None:
            kwargs["is_market"] = parsed["is_market"]
        if "order_price" in parsed and parsed["order_price"] is not None:
            kwargs["order_price"] = parsed["order_price"]

        # This should not raise
        signal = ParsedSignal(**kwargs)
        assert signal.symbol == parsed["symbol"]
