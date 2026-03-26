"""Webhook contract tests — validate payloads match SageMaster's expected schema.

These tests are deterministic (no OpenAI calls). They verify that
build_webhook_payload() produces payloads conforming to the documented
SageMaster webhook schemas in docs/WEBHOOK_PAYLOADS.md.

Covers:
  - Forex V1 entry (long + short)
  - Forex V2 entry with TP/SL
  - Forex V1/V2 management actions (close, partial close, breakeven)
  - Crypto entry (start_deal)
  - Crypto management actions (partial close, breakeven, extra order)
  - Empty optional fields are stripped (prevents "Invalid S/L or T/P")
  - Limit/stop order payloads include price
"""

from __future__ import annotations

import pytest

from src.core.mapper import build_webhook_payload
from src.core.models import ParsedSignal, RoutingRule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = "11111111-1111-1111-1111-111111111111"
_RULE_ID = "22222222-2222-2222-2222-222222222222"
_ASSIST_ID = "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
_AI_ASSIST_ID = "aaa79d52-1ab9-4d3b-a7ca-125b2f5e0307"


def _forex_rule(version: str = "V1", template: dict | None = None) -> RoutingRule:
    tpl = template or {
        "type": "",
        "assistId": _ASSIST_ID,
        "source": "",
        "symbol": "",
        "date": "",
    }
    if version == "V2" and template is None:
        tpl.update({"price": "", "takeProfits": [], "stopLoss": None})
    return RoutingRule(
        id=_RULE_ID,
        user_id=_USER_ID,
        source_channel_id="-100123",
        destination_webhook_url="https://sfx.sagemaster.io/deals_idea/test",
        payload_version=version,
        destination_type="sagemaster_forex",
        webhook_body_template=tpl,
    )


def _crypto_rule(template: dict | None = None) -> RoutingRule:
    tpl = template or {
        "type": "",
        "aiAssistId": _AI_ASSIST_ID,
        "exchange": "binance",
        "tradeSymbol": "",
        "eventSymbol": "",
        "price": "",
        "date": "",
    }
    return RoutingRule(
        id=_RULE_ID,
        user_id=_USER_ID,
        source_channel_id="-100123",
        destination_webhook_url="https://api.sagemaster.io/deals_idea/test",
        payload_version="V1",
        destination_type="sagemaster_crypto",
        webhook_body_template=tpl,
    )


# ---------------------------------------------------------------------------
# Forex V1 contract
# ---------------------------------------------------------------------------


class TestForexV1Contract:
    """Forex V1 payloads must have: type, assistId, source, symbol, date."""

    _REQUIRED_KEYS = {"type", "assistId", "source", "symbol", "date"}

    def test_v1_long_entry(self):
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", entry_price=1.1000,
            stop_loss=1.0950, take_profits=[1.1050],
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert self._REQUIRED_KEYS <= payload.keys()
        assert payload["type"] == "start_long_market_deal"
        assert payload["assistId"] == _ASSIST_ID
        assert payload["source"] == "forex"
        assert payload["symbol"] == "EURUSD"
        assert payload["date"]  # non-empty timestamp

    def test_v1_short_entry(self):
        signal = ParsedSignal(
            symbol="GBPUSD", direction="short", entry_price=1.2650,
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "start_short_market_deal"

    def test_v1_close_position(self):
        signal = ParsedSignal(
            action="close_position", symbol="XAUUSD",
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "close_order_at_market_price"
        assert payload["assistId"] == _ASSIST_ID
        assert "symbol" in payload

    def test_v1_close_all_strips_symbol(self):
        signal = ParsedSignal(action="close_all", symbol="XAUUSD")
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "close_all_orders_at_market_price"
        # close_all should NOT include symbol (operates on all positions)
        assert "symbol" not in payload

    def test_v1_breakeven(self):
        signal = ParsedSignal(
            action="breakeven", symbol="XAUUSD",
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "move_sl_to_breakeven"
        assert "slAdjustment" in payload

    def test_v1_partial_close_by_lot(self):
        signal = ParsedSignal(
            action="partial_close", symbol="EURUSD", lots="0.3",
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "partially_close_by_lot"
        assert payload["lotSize"] == 0.3

    def test_v1_partial_close_by_percentage(self):
        signal = ParsedSignal(
            action="partial_close", symbol="EURUSD", percentage=50,
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "partially_close_by_percentage"
        assert payload["percentage"] == 50

    def test_v1_start_assist(self):
        signal = ParsedSignal(action="start_assist", symbol="XAUUSD")
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "start_assist"
        assert payload["assistId"] == _ASSIST_ID
        # start_assist is symbolless — should not have symbol
        assert "symbol" not in payload

    def test_v1_stop_assist(self):
        signal = ParsedSignal(action="stop_assist", symbol="XAUUSD")
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "stop_assist"
        assert payload["assistId"] == _ASSIST_ID
        assert "symbol" not in payload


# ---------------------------------------------------------------------------
# Forex V2 contract
# ---------------------------------------------------------------------------


class TestForexV2Contract:
    """Forex V2 payloads include dynamic TP/SL fields from signal."""

    def test_v2_entry_with_tp_sl(self):
        signal = ParsedSignal(
            symbol="XAUUSD", direction="long", entry_price=2650.0,
            stop_loss=2640.0, take_profits=[2660.0, 2670.0],
            source_asset_class="forex",
        )
        payload = build_webhook_payload(signal, _forex_rule("V2"))
        assert payload["type"] == "start_long_market_deal"
        assert payload["takeProfits"] == [2660.0, 2670.0]
        assert payload["stopLoss"] == 2640.0
        assert "price" in payload

    def test_v2_entry_strips_empty_tp_sl(self):
        """Empty TP/SL must be stripped — SageMaster rejects empty arrays."""
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", entry_price=1.1000,
            take_profits=[], stop_loss=None,
        )
        payload = build_webhook_payload(signal, _forex_rule("V2"))
        assert "takeProfits" not in payload, "Empty takeProfits should be stripped"
        assert "stopLoss" not in payload, "None stopLoss should be stripped"

    def test_v2_limit_order_includes_price(self):
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", order_type="limit",
            entry_price=1.0950, stop_loss=1.0900, take_profits=[1.1000],
        )
        payload = build_webhook_payload(signal, _forex_rule("V2"))
        assert payload["type"] == "start_long_limit_deal"
        assert "price" in payload
        assert payload["price"] != ""

    def test_v2_stop_order(self):
        signal = ParsedSignal(
            symbol="GBPUSD", direction="short", order_type="stop",
            entry_price=1.2450, stop_loss=1.2500, take_profits=[1.2350],
        )
        payload = build_webhook_payload(signal, _forex_rule("V2"))
        assert payload["type"] == "start_short_limit_deal"

    def test_v2_pip_based_tp_sl(self):
        """TP/SL in pips (no absolute price)."""
        signal = ParsedSignal(
            symbol="XAUUSD", direction="long",
            take_profit_pips=[50, 100], stop_loss_pips=30,
            source_asset_class="forex",
        )
        rule = _forex_rule("V2", template={
            "type": "",
            "assistId": _ASSIST_ID,
            "source": "",
            "symbol": "",
            "date": "",
            "price": "",
            "takeProfitsPips": [],
            "stopLossPips": None,
        })
        payload = build_webhook_payload(signal, rule)
        assert payload["takeProfitsPips"] == [50, 100]
        assert payload["stopLossPips"] == 30


# ---------------------------------------------------------------------------
# Crypto contract
# ---------------------------------------------------------------------------


class TestCryptoContract:
    """Crypto payloads use aiAssistId, exchange, tradeSymbol, eventSymbol."""

    def test_crypto_entry(self):
        signal = ParsedSignal(
            symbol="BTC/USDT", direction="long", entry_price=95000,
            source_asset_class="crypto",
        )
        payload = build_webhook_payload(signal, _crypto_rule())
        assert payload["type"] == "start_deal"
        assert payload["aiAssistId"] == _AI_ASSIST_ID
        assert payload["exchange"] == "binance"
        assert "position_type" in payload

    def test_crypto_entry_with_tp_sl(self):
        signal = ParsedSignal(
            symbol="BTC/USDT", direction="long", entry_price=95000,
            take_profits=[1, 2, 5], stop_loss=10,
            source_asset_class="crypto",
        )
        payload = build_webhook_payload(signal, _crypto_rule())
        assert payload["type"] == "start_deal"
        assert payload.get("take_profits") == [1, 2, 5]

    def test_crypto_partial_close_percentage(self):
        signal = ParsedSignal(
            action="partial_close", symbol="BTC/USDT",
            direction="long", percentage=50,
            source_asset_class="crypto",
        )
        payload = build_webhook_payload(signal, _crypto_rule())
        assert payload["type"] == "partially_closed_by_percentage"
        assert payload["percentage"] == 50
        assert payload["position_type"] == "long"

    def test_crypto_breakeven(self):
        signal = ParsedSignal(
            action="breakeven", symbol="BTC/USDT", direction="long",
            source_asset_class="crypto",
        )
        payload = build_webhook_payload(signal, _crypto_rule())
        assert payload["type"] == "moved_sl_adjustment"
        assert "sl_adjustment" in payload
        assert payload["position_type"] == "long"

    def test_crypto_extra_order(self):
        signal = ParsedSignal(
            action="extra_order", symbol="BTC/USDT", direction="long",
            is_market=False, order_price=62000,
            source_asset_class="crypto",
        )
        payload = build_webhook_payload(signal, _crypto_rule())
        assert payload["type"] == "open_extra_order"
        assert payload["position_type"] == "long"
        assert payload["is_market"] is False
        assert payload["order_price"] == 62000

    def test_crypto_close_all(self):
        """Crypto close_all uses different type string than forex."""
        signal = ParsedSignal(
            action="close_all", symbol="BTC/USDT",
            source_asset_class="crypto",
        )
        payload = build_webhook_payload(signal, _crypto_rule())
        # Crypto uses "close_all_deals_at_market_price" not "close_all_orders_at_market_price"
        assert payload["type"] == "close_all_deals_at_market_price"
        assert payload["aiAssistId"] == _AI_ASSIST_ID

    def test_crypto_lot_partial_close_raises(self):
        """Crypto does not support lot-based partial close."""
        signal = ParsedSignal(
            action="partial_close", symbol="BTC/USDT",
            direction="long", lots="0.3",
            source_asset_class="crypto",
        )
        with pytest.raises(ValueError, match="lot-based partial close"):
            build_webhook_payload(signal, _crypto_rule())


# ---------------------------------------------------------------------------
# Cross-cutting contract rules
# ---------------------------------------------------------------------------


class TestContractRules:
    """Rules that apply across all payload types."""

    def test_no_template_raises(self):
        rule = RoutingRule(
            id=_RULE_ID,
            user_id=_USER_ID,
            source_channel_id="-100123",
            destination_webhook_url="https://sfx.sagemaster.io/deals_idea/test",
        )
        signal = ParsedSignal(symbol="EURUSD", direction="long")
        with pytest.raises(ValueError, match="Webhook body template is required"):
            build_webhook_payload(signal, rule)

    def test_modify_tp_unsupported(self):
        signal = ParsedSignal(
            action="modify_tp", symbol="EURUSD", new_tp=1.1200,
        )
        with pytest.raises(ValueError, match="modify_tp"):
            build_webhook_payload(signal, _forex_rule("V1"))

    def test_absolute_sl_modification_raises(self):
        """modify_sl with absolute price should be rejected."""
        signal = ParsedSignal(
            action="modify_sl", symbol="EURUSD", new_sl=1.0980,
        )
        with pytest.raises(ValueError, match="Absolute SL modification"):
            build_webhook_payload(signal, _forex_rule("V1"))

    def test_management_strips_entry_fields(self):
        """Management actions should not carry entry-only fields."""
        signal = ParsedSignal(
            action="close_position", symbol="XAUUSD",
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        for field in ("price", "takeProfits", "takeProfitsPips", "stopLoss", "stopLossPips", "balance"):
            assert field not in payload, f"Management payload should not have '{field}'"

    def test_trailing_sl_maps_to_breakeven(self):
        signal = ParsedSignal(
            action="trailing_sl", symbol="XAUUSD", trailing_sl_pips=30,
        )
        payload = build_webhook_payload(signal, _forex_rule("V1"))
        assert payload["type"] == "move_sl_to_breakeven"
        assert payload["slAdjustment"] == 30
