"""Tests for src.core.mapper — symbol mapping, payload building, tier limits."""

import pytest

from src.core.mapper import (
    apply_symbol_mapping,
    build_webhook_payload,
    check_asset_class_mismatch,
    check_template_symbol_mismatch,
    check_tier_limit,
)
from src.core.models import (
    ParsedSignal,
    RoutingRule,
    SignalAction,
    SubscriptionTier,
)


# ---- apply_symbol_mapping ----


def test_apply_symbol_mapping_match(sample_routing_rule_v2):
    """GOLD should be mapped to XAUUSD when the mapping exists."""
    signal = ParsedSignal(symbol="GOLD", direction="long")
    result = apply_symbol_mapping(signal, sample_routing_rule_v2)
    assert result.symbol == "XAUUSD"


def test_apply_symbol_mapping_no_match(sample_routing_rule_v2):
    """Symbol should remain unchanged when no mapping exists."""
    signal = ParsedSignal(symbol="EURUSD", direction="long")
    result = apply_symbol_mapping(signal, sample_routing_rule_v2)
    assert result.symbol == "EURUSD"


# ---- build_webhook_payload requires template ----


def test_build_webhook_payload_no_template_raises(sample_parsed_signal):
    """build_webhook_payload must raise ValueError when no template is provided."""
    rule = RoutingRule(
        id="22222222-2222-2222-2222-222222222222",
        user_id="11111111-1111-1111-1111-111111111111",
        source_channel_id="-1001234567890",
        destination_webhook_url="https://api.sagemaster.io/deals_idea/some-id",
        payload_version="V1",
    )
    with pytest.raises(ValueError, match="Webhook body template is required"):
        build_webhook_payload(sample_parsed_signal, rule)


def test_build_webhook_payload_v1_with_template(sample_parsed_signal):
    """V1 payload via template must contain type, assistId, source, symbol, and date."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "source": "",
        "symbol": "",
        "date": "",
    }, version="V1")
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["type"] == "start_long_market_deal"
    assert payload["assistId"] == "my-assist-id"
    assert payload["source"] == "forex"
    assert payload["symbol"] == "EURUSD"
    assert payload["date"] != ""


def test_build_webhook_payload_v1_short_with_template():
    """Short direction should produce 'start_short_market_deal'."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "source": "",
        "symbol": "",
        "date": "",
    }, version="V1")
    signal = ParsedSignal(symbol="GBPUSD", direction="short")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "start_short_market_deal"


def test_build_webhook_payload_v2_with_template(sample_parsed_signal):
    """V2 payload via template must include price, takeProfits, and stopLoss."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "source": "",
        "symbol": "",
        "date": "",
        "price": "",
        "takeProfits": [],
        "stopLoss": None,
    }, version="V2")
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["type"] == "start_long_market_deal"
    assert payload["assistId"] == "my-assist-id"
    assert payload["source"] == "forex"
    assert payload["symbol"] == "EURUSD"
    assert payload["price"] == "1.1"
    assert payload["takeProfits"] == [1.1050, 1.1100]
    assert payload["stopLoss"] == 1.0950


# ---- check_tier_limit ----


def test_check_tier_limit_within():
    """Should return True when current count is below the tier maximum."""
    assert check_tier_limit(SubscriptionTier.free, 0) is True
    assert check_tier_limit(SubscriptionTier.pro, 4) is True


def test_check_tier_limit_exceeded():
    """Should return False when current count meets or exceeds the tier maximum."""
    assert check_tier_limit(SubscriptionTier.free, 5) is False
    assert check_tier_limit(SubscriptionTier.starter, 2) is False
    assert check_tier_limit(SubscriptionTier.pro, 5) is False


# ---- Follow-up action types (with template) ----


def test_partial_close_by_lot_v2():
    """partial_close with lots should produce partially_close_by_lot."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="partial_close", symbol="EURUSD", lots="0.3")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_close_by_lot"
    assert payload["lotSize"] == 0.3


def test_partial_close_by_lot_default():
    """partial_close without lots or percentage should default to lot-based with 0.5."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="partial_close", symbol="EURUSD")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_close_by_lot"
    assert payload["lotSize"] == 0.5


def test_partial_close_by_percentage_v2():
    """partial_close with percentage should produce partially_close_by_percentage."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="partial_close", symbol="EURUSD", percentage=50)
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_close_by_percentage"
    assert payload["percentage"] == 50


def test_breakeven_v2():
    """breakeven should produce move_sl_to_breakeven with slAdjustment=0."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "XAUUSD",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="breakeven", symbol="XAUUSD")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "move_sl_to_breakeven"
    assert payload["slAdjustment"] == 0


def test_close_position_v2():
    """close_position should produce close_order_at_market_price."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "GBPJPY",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="close_position", symbol="GBPJPY")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "close_order_at_market_price"


def test_followup_no_template_raises():
    """Follow-up actions without a template should raise ValueError."""
    rule = RoutingRule(
        id="22222222-2222-2222-2222-222222222222",
        user_id="11111111-1111-1111-1111-111111111111",
        source_channel_id="-1001234567890",
        destination_webhook_url="https://api.sagemaster.io/deals_idea/some-id",
        payload_version="V1",
    )
    signal = ParsedSignal(action="close_position", symbol="EURUSD")
    with pytest.raises(ValueError, match="Webhook body template is required"):
        build_webhook_payload(signal, rule)


def test_modify_sl_maps_to_breakeven():
    """modify_sl should map to move_sl_to_breakeven action."""
    from src.core.mapper import _signal_action

    signal = ParsedSignal(action="modify_sl", symbol="EURUSD", new_sl=1.0980)
    assert _signal_action(signal) == SignalAction.breakeven


def test_modify_tp_raises():
    """modify_tp should raise ValueError (not supported by SageMaster)."""
    from src.core.mapper import _signal_action

    signal = ParsedSignal(action="modify_tp", symbol="EURUSD", new_tp=1.1200)
    with pytest.raises(ValueError, match="not supported"):
        _signal_action(signal)


def test_trailing_sl_maps_to_breakeven():
    """trailing_sl should map to move_sl_to_breakeven action."""
    from src.core.mapper import _signal_action

    signal = ParsedSignal(action="trailing_sl", symbol="XAUUSD", trailing_sl_pips=30)
    assert _signal_action(signal) == SignalAction.breakeven


def test_entry_backward_compat(sample_parsed_signal):
    """Existing entry signals (no action field) should still work with template."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "source": "",
        "symbol": "",
        "date": "",
        "price": "",
        "takeProfits": [],
        "stopLoss": None,
    }, version="V2")
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["type"] == "start_long_market_deal"


# ---- Template follow-up: entry field stripping ----


def _rule_with_template(
    template: dict,
    version: str = "V1",
    destination_type: str = "sagemaster_forex",
) -> RoutingRule:
    """Helper to create a routing rule with a webhook_body_template."""
    return RoutingRule(
        id="22222222-2222-2222-2222-222222222222",
        user_id="11111111-1111-1111-1111-111111111111",
        source_channel_id="-1001234567890",
        source_channel_name="VIP Signals",
        destination_webhook_url=(
            "https://api.sagemaster.io/deals_idea/"
            "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
        ),
        payload_version=version,
        webhook_body_template=template,
        destination_type=destination_type,
    )


def test_template_followup_strips_entry_fields():
    """Management actions via template should strip price/takeProfits/stopLoss."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
        "date": "",
        "price": "{{close}}",
        "takeProfits": [1.1, 1.2],
        "stopLoss": 1.05,
    }, version="V2")
    signal = ParsedSignal(action="close_position", symbol="EURUSD")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "close_order_at_market_price"
    assert "price" not in payload
    assert "takeProfits" not in payload
    assert "stopLoss" not in payload
    assert payload["assistId"] == "my-assist-id"


def test_template_followup_breakeven_injects_slAdjustment():
    """Breakeven via template should inject slAdjustment=0."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "XAUUSD",
        "source": "forex",
        "date": "",
    })
    signal = ParsedSignal(action="breakeven", symbol="XAUUSD")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "move_sl_to_breakeven"
    assert payload["slAdjustment"] == 0


def test_template_followup_partial_close_pct():
    """Partial close by percentage via template should inject percentage field."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
        "date": "",
        "price": "{{close}}",
        "takeProfits": [],
    })
    signal = ParsedSignal(action="partial_close", symbol="EURUSD", percentage=50)
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_close_by_percentage"
    assert payload["percentage"] == 50
    assert "price" not in payload  # entry fields stripped
    assert "takeProfits" not in payload


def test_template_followup_partial_close_lot():
    """Partial close by lot via template should inject lotSize field."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
        "date": "",
    })
    signal = ParsedSignal(action="partial_close", symbol="EURUSD", lots="0.3")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_close_by_lot"
    assert payload["lotSize"] == 0.3


# ---- Template field preservation (entry) ----


def test_template_preserves_prefilled_symbol_and_source(sample_parsed_signal):
    """Template with pre-filled symbol and source should NOT be overwritten."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "AUDCAD",
        "source": "forex",
        "date": "",
    })
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["symbol"] == "AUDCAD"
    assert payload["source"] == "forex"
    assert payload["type"] == "start_long_market_deal"
    assert payload["assistId"] == "my-assist-id"


def test_template_fills_empty_symbol_and_source(sample_parsed_signal):
    """Template with empty symbol/source should be filled from signal."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "",
        "source": "",
        "date": "",
    })
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["symbol"] == "EURUSD"
    assert payload["source"] == "forex"


def test_template_no_extra_fields_injected(sample_parsed_signal):
    """Template without symbol/source keys should NOT have them injected."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "date": "",
    })
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert "symbol" not in payload
    assert "source" not in payload
    assert payload["assistId"] == "my-assist-id"
    assert payload["type"] == "start_long_market_deal"


def test_template_v2_preserves_prefilled_tp_sl(sample_parsed_signal):
    """V2 template with pre-filled price/TP/SL should NOT be overwritten."""
    rule = _rule_with_template(
        {
            "type": "",
            "assistId": "my-assist-id",
            "symbol": "AUDCAD",
            "source": "forex",
            "date": "",
            "price": "2.0",
            "takeProfits": [2.1, 2.2],
            "stopLoss": 1.9,
        },
        version="V2",
    )
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["price"] == "2.0"
    assert payload["takeProfits"] == [2.1, 2.2]
    assert payload["stopLoss"] == 1.9


def test_template_v2_fills_empty_tp_sl(sample_parsed_signal):
    """V2 template with empty price/TP/SL keys should be filled from signal."""
    rule = _rule_with_template(
        {
            "type": "",
            "assistId": "my-assist-id",
            "symbol": "AUDCAD",
            "source": "forex",
            "date": "",
            "price": "",
            "takeProfits": [],
            "stopLoss": None,
        },
        version="V2",
    )
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["symbol"] == "AUDCAD"
    assert payload["price"] == "1.1"
    assert payload["takeProfits"] == [1.1050, 1.1100]
    assert payload["stopLoss"] == 1.0950


def test_template_v2_no_extra_v2_fields(sample_parsed_signal):
    """V2 template without price/TP/SL keys should NOT have them injected."""
    rule = _rule_with_template(
        {
            "type": "",
            "assistId": "my-assist-id",
            "symbol": "AUDCAD",
            "source": "forex",
            "date": "",
        },
        version="V2",
    )
    payload = build_webhook_payload(sample_parsed_signal, rule)
    assert payload["symbol"] == "AUDCAD"
    assert "price" not in payload
    assert "takeProfits" not in payload
    assert "stopLoss" not in payload


# ---- TradingView placeholder substitution ----


def test_template_replaces_close_and_ticker_placeholders():
    """{{close}} and {{ticker}} placeholders should be replaced with signal data."""
    rule = _rule_with_template({
        "type": "start_deal",
        "tradeSymbol": "{{ticker}}",
        "price": "{{close}}",
        "date": "{{time}}",
    })
    signal = ParsedSignal(
        symbol="BTCUSDT",
        direction="long",
        entry_price=64500.50,
        source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["tradeSymbol"] == "BTCUSDT"
    assert payload["price"] == "64500.5"
    assert payload["type"] == "start_deal"  # preserved, not overwritten
    assert payload["date"] != "{{time}}"  # replaced with timestamp


def test_crypto_template_preserves_type_no_extra_fields():
    """Crypto-style template: type='start_deal' preserved, no extra fields injected."""
    rule = _rule_with_template({
        "type": "start_deal",
        "tradeSymbol": "{{ticker}}",
        "price": "{{close}}",
    })
    signal = ParsedSignal(
        symbol="ETHUSDT",
        direction="long",
        entry_price=3200.0,
        source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "start_deal"
    assert payload["tradeSymbol"] == "ETHUSDT"
    assert payload["price"] == "3200.0"
    assert "symbol" not in payload
    assert "source" not in payload
    assert "date" not in payload


def test_forex_template_empty_type_filled_from_direction():
    """Forex template with empty type should get direction-based type."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "AUDCAD",
        "source": "forex",
        "date": "",
    })
    signal = ParsedSignal(symbol="AUDCAD", direction="short", source_asset_class="forex")
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "start_short_market_deal"
    assert payload["symbol"] == "AUDCAD"  # preserved from template
    assert payload["source"] == "forex"  # preserved from template


# ---- check_template_symbol_mismatch ----


def test_mismatch_hardcoded_tradeSymbol_different_signal():
    """Hardcoded tradeSymbol that differs from signal should return mismatch for forex."""
    rule = _rule_with_template({"type": "start_deal", "tradeSymbol": "LUMIA/USDT"})
    signal = ParsedSignal(symbol="BTC/USDT", direction="long")
    reason = check_template_symbol_mismatch(signal, rule)
    assert reason is not None
    assert "BTC/USDT" in reason
    assert "LUMIA/USDT" in reason


def test_crypto_tradeSymbol_mismatch_allowed():
    """Crypto DCA assists have a fixed tradeSymbol — mismatch should be allowed."""
    rule = _rule_with_template(
        {"type": "start_deal", "tradeSymbol": "LUMIA/USDT", "eventSymbol": "{{ticker}}"},
        destination_type="sagemaster_crypto",
    )
    signal = ParsedSignal(symbol="BTC/USDT", direction="long", source_asset_class="crypto")
    reason = check_template_symbol_mismatch(signal, rule)
    assert reason is None  # should NOT block


def test_crypto_eventSymbol_mismatch_still_blocks():
    """Crypto eventSymbol hardcoded mismatch should still block dispatch."""
    rule = _rule_with_template(
        {"type": "start_deal", "tradeSymbol": "LUMIA/USDT", "eventSymbol": "LUMIA/USDT"},
        destination_type="sagemaster_crypto",
    )
    signal = ParsedSignal(symbol="BTC/USDT", direction="long", source_asset_class="crypto")
    reason = check_template_symbol_mismatch(signal, rule)
    assert reason is not None
    assert "eventSymbol" in reason


def test_mismatch_hardcoded_tradeSymbol_matching_signal():
    """Hardcoded tradeSymbol that matches signal should return None (OK)."""
    rule = _rule_with_template({"type": "start_deal", "tradeSymbol": "LUMIA/USDT"})
    signal = ParsedSignal(symbol="LUMIA/USDT", direction="long")
    assert check_template_symbol_mismatch(signal, rule) is None


def test_mismatch_placeholder_tradeSymbol():
    """{{ticker}} placeholder should never cause a mismatch."""
    rule = _rule_with_template({"type": "start_deal", "tradeSymbol": "{{ticker}}"})
    signal = ParsedSignal(symbol="ANY/COIN", direction="long")
    assert check_template_symbol_mismatch(signal, rule) is None


def test_mismatch_empty_tradeSymbol():
    """Empty tradeSymbol (dynamic) should never cause a mismatch."""
    rule = _rule_with_template({"type": "start_deal", "tradeSymbol": ""})
    signal = ParsedSignal(symbol="ANY/COIN", direction="long")
    assert check_template_symbol_mismatch(signal, rule) is None


def test_mismatch_no_template():
    """No template at all should never cause a mismatch."""
    rule = RoutingRule(
        id="22222222-2222-2222-2222-222222222222",
        user_id="11111111-1111-1111-1111-111111111111",
        source_channel_id="-1001234567890",
        source_channel_name="VIP Signals",
        destination_webhook_url=(
            "https://api.sagemaster.io/deals_idea/"
            "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
        ),
        payload_version="V1",
    )
    signal = ParsedSignal(symbol="BTC/USDT", direction="long")
    assert check_template_symbol_mismatch(signal, rule) is None


def test_mismatch_hardcoded_symbol_field():
    """Hardcoded 'symbol' field (not tradeSymbol) should also be checked."""
    rule = _rule_with_template({
        "type": "",
        "symbol": "AUDCAD",
        "source": "forex",
    })
    signal = ParsedSignal(symbol="EURUSD", direction="long")
    reason = check_template_symbol_mismatch(signal, rule)
    assert reason is not None
    assert "EURUSD" in reason
    assert "AUDCAD" in reason


def test_close_placeholder_no_price():
    """{{close}} should be stripped when entry_price is None (avoids SageMaster rejection)."""
    rule = _rule_with_template({
        "type": "start_deal",
        "tradeSymbol": "{{ticker}}",
        "price": "{{close}}",
    })
    signal = ParsedSignal(symbol="ETH/USDT", direction="long", entry_price=None)
    payload = build_webhook_payload(signal, rule)
    assert "price" not in payload  # empty optional fields stripped
    assert payload["tradeSymbol"] == "ETH/USDT"


def test_eventSymbol_empty_filled_from_signal():
    """Empty eventSymbol should be filled from signal."""
    rule = _rule_with_template({
        "type": "start_deal",
        "tradeSymbol": "{{ticker}}",
        "eventSymbol": "",
        "price": "{{close}}",
    })
    signal = ParsedSignal(
        symbol="SOL/USDT", direction="long", entry_price=150.0,
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["eventSymbol"] == "SOL/USDT"
    assert payload["tradeSymbol"] == "SOL/USDT"


def test_modify_sl_payload_with_new_sl():
    """modify_sl with new_sl should produce breakeven with slAdjustment = new_sl."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="modify_sl", symbol="EURUSD", new_sl=25)
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "move_sl_to_breakeven"
    assert payload["slAdjustment"] == 25


def test_trailing_sl_payload():
    """trailing_sl should produce breakeven with slAdjustment = trailing_sl_pips."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "XAUUSD",
        "source": "forex",
    }, version="V2")
    signal = ParsedSignal(action="trailing_sl", symbol="XAUUSD", trailing_sl_pips=30)
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "move_sl_to_breakeven"
    assert payload["slAdjustment"] == 30


def test_mismatch_hardcoded_eventSymbol():
    """Hardcoded eventSymbol that differs from signal should return mismatch."""
    rule = _rule_with_template({
        "type": "start_deal",
        "tradeSymbol": "{{ticker}}",
        "eventSymbol": "LUMIA/USDT",
    })
    signal = ParsedSignal(symbol="BTC/USDT", direction="long")
    reason = check_template_symbol_mismatch(signal, rule)
    assert reason is not None
    assert "LUMIA/USDT" in reason


# ---- Crypto management action payloads ----

_CRYPTO_TEMPLATE = {
    "type": "start_deal",
    "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
    "exchange": "binance",
    "tradeSymbol": "{{ticker}}",
    "eventSymbol": "{{ticker}}",
    "price": "{{close}}",
    "date": "{{time}}",
}


def test_crypto_partial_close_pct_payload():
    """Crypto partial close should use documented crypto type and field names."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="partial_close", symbol="BTC/USDT", direction="long",
        percentage=50, entry_price=64500.0, source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_closed_by_percentage"
    assert payload["percentage"] == 50
    assert payload["position_type"] == "long"
    # Should not have forex-specific fields
    assert "lotSize" not in payload
    assert "slAdjustment" not in payload


def test_crypto_partial_close_lot_without_pct_raises():
    """Crypto does not support lot-based close without a percentage — must reject."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="partial_close", symbol="ETH/USDT", direction="short",
        lots="0.5", source_asset_class="crypto",
    )
    with pytest.raises(ValueError, match="lot-based partial close"):
        build_webhook_payload(signal, rule)


def test_crypto_partial_close_lot_with_pct_uses_percentage():
    """Crypto lot-based close with a percentage available should use the percentage."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="partial_close", symbol="ETH/USDT", direction="short",
        lots="0.5", percentage=75, source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_closed_by_percentage"
    assert payload["percentage"] == 75
    assert payload["position_type"] == "short"
    assert "lotSize" not in payload


def test_crypto_breakeven_payload():
    """Crypto breakeven should use moved_sl_adjustment type and sl_adjustment field."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="breakeven", symbol="BTC/USDT", direction="long",
        entry_price=64500.0, source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "moved_sl_adjustment"
    assert payload["sl_adjustment"] == 0
    assert payload["position_type"] == "long"
    # Should not have forex-specific camelCase field
    assert "slAdjustment" not in payload


def test_crypto_modify_sl_payload():
    """Crypto modify_sl should use moved_sl_adjustment with sl_adjustment value."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="modify_sl", symbol="SOL/USDT", direction="long",
        new_sl=42.0, source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "moved_sl_adjustment"
    assert payload["sl_adjustment"] == 42
    assert payload["position_type"] == "long"


def test_crypto_close_position_payload():
    """Crypto close uses same type as forex (close_order_at_market_price)."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="close_position", symbol="BTC/USDT", direction="long",
        source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "close_order_at_market_price"


def test_crypto_entry_uses_start_deal():
    """Crypto entry should use start_deal type regardless of direction."""
    rule = _rule_with_template(
        {**_CRYPTO_TEMPLATE, "type": ""},
        destination_type="sagemaster_crypto",
    )
    signal = ParsedSignal(
        symbol="BTC/USDT", direction="long",
        entry_price=64500.0, source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "start_deal"


def test_forex_management_unchanged():
    """Forex management actions should remain unchanged after crypto branching."""
    rule = _rule_with_template({
        "type": "",
        "assistId": "my-assist-id",
        "symbol": "EURUSD",
        "source": "forex",
    }, destination_type="sagemaster_forex")
    signal = ParsedSignal(action="partial_close", symbol="EURUSD", percentage=50)
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "partially_close_by_percentage"
    assert payload["percentage"] == 50
    assert "position_type" not in payload
    assert "sl_adjustment" not in payload


# ---- Asset class compatibility checks ----


def test_asset_class_crypto_to_crypto_ok():
    """Crypto signal to crypto destination should pass."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(symbol="BTC/USDT", direction="long", source_asset_class="crypto")
    assert check_asset_class_mismatch(signal, rule) is None


def test_asset_class_forex_to_forex_ok():
    """Forex signal to forex destination should pass."""
    rule = _rule_with_template({"type": "", "assistId": "x", "symbol": "", "source": "forex"}, destination_type="sagemaster_forex")
    signal = ParsedSignal(symbol="EURUSD", direction="long", source_asset_class="forex")
    assert check_asset_class_mismatch(signal, rule) is None


def test_asset_class_commodities_to_forex_ok():
    """Commodities (XAUUSD) to forex destination should pass — SFX supports commodities."""
    rule = _rule_with_template({"type": "", "assistId": "x", "symbol": "", "source": "forex"}, destination_type="sagemaster_forex")
    signal = ParsedSignal(symbol="XAUUSD", direction="long", source_asset_class="commodities")
    assert check_asset_class_mismatch(signal, rule) is None


def test_asset_class_indices_to_forex_ok():
    """Indices (US30) to forex destination should pass — SFX supports indices."""
    rule = _rule_with_template({"type": "", "assistId": "x", "symbol": "", "source": "forex"}, destination_type="sagemaster_forex")
    signal = ParsedSignal(symbol="US30", direction="long", source_asset_class="indices")
    assert check_asset_class_mismatch(signal, rule) is None


def test_asset_class_commodities_to_crypto_rejected():
    """Commodities (XAUUSD) to crypto destination should be rejected."""
    rule = _rule_with_template(_CRYPTO_TEMPLATE, destination_type="sagemaster_crypto")
    signal = ParsedSignal(symbol="XAUUSD", direction="long", source_asset_class="commodities")
    reason = check_asset_class_mismatch(signal, rule)
    assert reason is not None
    assert "commodities" in reason
    assert "sagemaster_crypto" in reason


def test_asset_class_crypto_to_forex_rejected():
    """Crypto signal to forex destination should be rejected."""
    rule = _rule_with_template({"type": "", "assistId": "x", "symbol": "", "source": "forex"}, destination_type="sagemaster_forex")
    signal = ParsedSignal(symbol="BTC/USDT", direction="long", source_asset_class="crypto")
    reason = check_asset_class_mismatch(signal, rule)
    assert reason is not None
    assert "crypto" in reason
    assert "sagemaster_forex" in reason


def test_asset_class_custom_destination_accepts_all():
    """Custom destinations should accept any asset class."""
    rule = _rule_with_template({"type": "", "symbol": ""}, destination_type="custom")
    for asset_class in ("forex", "crypto", "commodities", "indices", "unknown"):
        signal = ParsedSignal(symbol="TEST", direction="long", source_asset_class=asset_class)
        assert check_asset_class_mismatch(signal, rule) is None


# ---- Crypto extra order ----


def test_crypto_extra_order_payload():
    """extra_order action should produce open_extra_order with crypto fields."""
    rule = _rule_with_template({
        "type": "",
        "aiAssistId": "my-assist-id",
        "exchange": "bitgetfutures",
        "tradeSymbol": "BTC/USDT:USDT",
        "eventSymbol": "{{ticker}}",
        "price": "{{close}}",
        "date": "",
    }, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="extra_order", symbol="BTC/USDT", direction="long",
        source_asset_class="crypto", is_market=False, order_price=30000,
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "open_extra_order"
    assert payload["position_type"] == "long"
    assert payload["is_market"] is False
    assert payload["order_price"] == 30000


def test_crypto_extra_order_market_default():
    """extra_order without is_market should default to market order."""
    rule = _rule_with_template({
        "type": "",
        "aiAssistId": "my-assist-id",
        "exchange": "bitgetfutures",
        "tradeSymbol": "BTC/USDT:USDT",
        "date": "",
    }, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        action="extra_order", symbol="BTC/USDT", direction="long",
        source_asset_class="crypto",
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "open_extra_order"
    assert payload["is_market"] is True
    assert "order_price" not in payload


# ---- Crypto entry with TP/SL (percentage-based) ----


def test_crypto_entry_with_tp_sl_percentages():
    """Crypto entry with take_profits and stopLoss should fill from signal."""
    rule = _rule_with_template({
        "type": "",
        "aiAssistId": "my-assist-id",
        "exchange": "bitgetfutures",
        "tradeSymbol": "",
        "position_type": "",
        "eventSymbol": "",
        "price": "",
        "date": "",
        "take_profits": [],
        "stopLoss": None,
    }, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        symbol="BTC/USDT", direction="long",
        source_asset_class="crypto",
        take_profits=[1, 2, 5], stop_loss=10,
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["type"] == "start_deal"
    assert payload["take_profits"] == [1, 2, 5]
    assert payload["stopLoss"] == 10
    assert payload["position_type"] == "long"


def test_crypto_entry_snake_case_stop_loss():
    """Crypto entry with snake_case stop_loss should be filled from signal."""
    rule = _rule_with_template({
        "type": "",
        "aiAssistId": "my-assist-id",
        "exchange": "bitgetfutures",
        "tradeSymbol": "",
        "position_type": "",
        "eventSymbol": "",
        "price": "",
        "date": "",
        "take_profits": [],
        "stop_loss": None,
    }, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        symbol="BTC/USDT", direction="short",
        source_asset_class="crypto",
        take_profits=[2, 4], stop_loss=5,
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["take_profits"] == [2, 4]
    assert payload["stop_loss"] == 5
    assert payload["position_type"] == "short"


def test_crypto_entry_preserves_prefilled_tp_sl():
    """Crypto entry with pre-filled TP/SL should NOT be overwritten."""
    rule = _rule_with_template({
        "type": "",
        "aiAssistId": "my-assist-id",
        "exchange": "bitgetfutures",
        "tradeSymbol": "BTC/USDT:USDT",
        "position_type": "long",
        "eventSymbol": "",
        "price": "",
        "date": "",
        "take_profits": [1, 2, 5],
        "stopLoss": 10,
    }, destination_type="sagemaster_crypto")
    signal = ParsedSignal(
        symbol="BTC/USDT", direction="long",
        source_asset_class="crypto",
        take_profits=[3, 6, 9], stop_loss=20,
    )
    payload = build_webhook_payload(signal, rule)
    assert payload["take_profits"] == [1, 2, 5]
    assert payload["stopLoss"] == 10


# ---- QA bug fixes (SGM-043) ----


class TestV1LimitOrderPrice:
    """Bug #2: V1 limit orders must include entry price in the payload."""

    def test_v1_limit_fills_price(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
            "price": "",
        }, version="V1")
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", order_type="limit",
            entry_price=1.0850,
        )
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_long_limit_deal"
        assert payload["price"] == "1.085"

    def test_v1_market_does_not_fill_price(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
            "price": "",
        }, version="V1")
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", order_type="market",
            entry_price=1.0850,
        )
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_long_market_deal"
        # V1 market orders should NOT fill price (gated behind V2)
        assert "price" not in payload  # stripped as empty

    def test_v1_short_limit_fills_price(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
            "price": "",
        }, version="V1")
        signal = ParsedSignal(
            symbol="GBPUSD", direction="short", order_type="limit",
            entry_price=1.2650,
        )
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_short_limit_deal"
        assert payload["price"] == "1.265"


class TestLotsTypeConversion:
    """Bug #4: V2 lots must be sent as a number, not a string."""

    def test_lots_string_converted_to_float(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
            "lots": "0.5",
        }, version="V2")
        signal = ParsedSignal(symbol="EURUSD", direction="long")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["lots"], float)
        assert payload["lots"] == 0.5

    def test_lots_integer_string_converted(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
            "lots": "2",
        }, version="V2")
        signal = ParsedSignal(symbol="EURUSD", direction="long")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["lots"], float)
        assert payload["lots"] == 2.0

    def test_balance_string_converted_to_int(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
            "balance": "1000",
        }, version="V2")
        signal = ParsedSignal(symbol="EURUSD", direction="long")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["balance"], int)
        assert payload["balance"] == 1000


class TestBreakevenOffset:
    """Bug #3: Breakeven with pip offset should populate slAdjustment."""

    def test_breakeven_offset_forex(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
        }, version="V1")
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", action="breakeven",
            breakeven_offset_pips=-10,
        )
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "move_sl_to_breakeven"
        assert payload["slAdjustment"] == -10

    def test_breakeven_no_offset_defaults_zero(self):
        rule = _rule_with_template({
            "type": "",
            "assistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
        }, version="V1")
        signal = ParsedSignal(
            symbol="EURUSD", direction="long", action="breakeven",
        )
        payload = build_webhook_payload(signal, rule)
        assert payload["slAdjustment"] == 0

    def test_breakeven_offset_crypto(self):
        rule = _rule_with_template({
            "type": "",
            "aiAssistId": "assist-123",
            "source": "",
            "symbol": "",
            "date": "",
        }, version="V1", destination_type="sagemaster_crypto")
        signal = ParsedSignal(
            symbol="BTC/USDT", direction="long", action="breakeven",
            source_asset_class="crypto",
            breakeven_offset_pips=-5,
        )
        payload = build_webhook_payload(signal, rule)
        assert payload["sl_adjustment"] == -5
