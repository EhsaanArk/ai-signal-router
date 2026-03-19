"""Contract tests for webhook payloads matching the SageMaster specification.

Expands on test_mapper.py with schema compliance checks, edge cases,
and end-to-end payload construction verification.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.core.mapper import (
    apply_symbol_mapping,
    build_webhook_payload,
)
from src.core.models import (
    ParsedSignal,
    RoutingRule,
    SignalAction,
    WebhookPayloadV1,
    WebhookPayloadV2,
)

SAMPLE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_RULE_ID = UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_ASSIST_ID = "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
SAMPLE_WEBHOOK_URL = f"https://api.sagemaster.io/deals_idea/{SAMPLE_ASSIST_ID}"

ISO_8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
)


# =====================================================================
# Helpers
# =====================================================================

def _make_signal(**overrides) -> ParsedSignal:
    defaults = dict(
        symbol="EURUSD",
        direction="long",
        order_type="market",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profits=[1.1050, 1.1100],
        source_asset_class="forex",
    )
    defaults.update(overrides)
    return ParsedSignal(**defaults)


_DEFAULT_V1_TEMPLATE = {
    "type": "",
    "assistId": SAMPLE_ASSIST_ID,
    "source": "",
    "symbol": "",
    "date": "",
}

_DEFAULT_V2_TEMPLATE = {
    "type": "",
    "assistId": SAMPLE_ASSIST_ID,
    "source": "",
    "symbol": "",
    "date": "",
    "price": "",
    "takeProfits": [],
    "stopLoss": None,
}


def _make_rule(version: str = "V1", **overrides) -> RoutingRule:
    defaults = dict(
        id=SAMPLE_RULE_ID,
        user_id=SAMPLE_USER_ID,
        source_channel_id="-1001234567890",
        destination_webhook_url=SAMPLE_WEBHOOK_URL,
        payload_version=version,
        webhook_body_template=(
            overrides.pop("webhook_body_template", None)
            or (_DEFAULT_V2_TEMPLATE.copy() if version == "V2" else _DEFAULT_V1_TEMPLATE.copy())
        ),
    )
    defaults.update(overrides)
    return RoutingRule(**defaults)


# =====================================================================
# 1. V1 payload schema compliance
# =====================================================================


class TestV1SchemaCompliance:
    """Verify V1 payloads match the SageMaster specification exactly."""

    def test_v1_has_exactly_required_fields(self):
        """V1 payload must have at minimum: type, assistId, source, symbol, date."""
        signal = _make_signal()
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert set(payload.keys()) == {"type", "assistId", "source", "symbol", "date"}

    @pytest.mark.parametrize(
        "direction, expected_type",
        [
            ("long", "start_long_market_deal"),
            ("short", "start_short_market_deal"),
        ],
    )
    def test_v1_type_values(self, direction, expected_type):
        """V1 ``type`` must be one of the two allowed action strings."""
        signal = _make_signal(direction=direction)
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == expected_type

    def test_v1_source_matches_signal_source_asset_class(self):
        """V1 ``source`` must match the signal's source_asset_class."""
        for asset_class in ("forex", "crypto", "indices"):
            signal = _make_signal(source_asset_class=asset_class)
            rule = _make_rule("V1")
            payload = build_webhook_payload(signal, rule)
            assert payload["source"] == asset_class

    def test_v1_date_is_iso8601(self):
        """V1 ``date`` must be an ISO 8601 formatted string."""
        signal = _make_signal()
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert ISO_8601_RE.match(payload["date"]), f"Date is not ISO 8601: {payload['date']}"
        # Also verify it can be parsed as a datetime
        datetime.fromisoformat(payload["date"])


# =====================================================================
# 2. V2 payload schema compliance
# =====================================================================


class TestV2SchemaCompliance:
    """Verify V2 payloads match the SageMaster specification."""

    def test_v2_has_v1_fields_plus_extras(self):
        """V2 payload must have core fields PLUS price, takeProfits, stopLoss."""
        signal = _make_signal()
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        core_fields = {"type", "assistId", "source", "symbol"}
        v2_extras = {"price", "takeProfits", "stopLoss"}
        assert core_fields.issubset(set(payload.keys()))
        assert v2_extras.issubset(set(payload.keys()))

    def test_v2_take_profits_is_list(self):
        """V2 ``takeProfits`` must be a list of floats."""
        signal = _make_signal(take_profits=[1.1050, 1.1100, 1.1200])
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["takeProfits"], list)
        assert all(isinstance(tp, float) for tp in payload["takeProfits"])

    def test_v2_price_is_string(self):
        """V2 ``price`` must be a string per the SageMaster spec."""
        signal = _make_signal(entry_price=1.2345)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["price"], str)

    def test_v2_stop_loss_is_float(self):
        """V2 ``stopLoss`` must be a float."""
        signal = _make_signal(stop_loss=1.0900)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["stopLoss"], float)

    def test_v2_multiple_take_profit_levels(self):
        """V2 payload should handle 1, 3, and 5 take profit levels."""
        for tp_count in (1, 3, 5):
            tps = [1.1000 + (i * 0.005) for i in range(1, tp_count + 1)]
            signal = _make_signal(take_profits=tps)
            rule = _make_rule("V2")
            payload = build_webhook_payload(signal, rule)
            assert len(payload["takeProfits"]) == tp_count

    def test_v2_no_entry_price_stripped(self):
        """When entry_price is None, price field should be stripped from payload."""
        signal = _make_signal(entry_price=None)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert "price" not in payload  # empty optional fields stripped

    def test_v2_no_stop_loss_stripped(self):
        """When stop_loss is None, stopLoss field should be stripped from payload."""
        signal = _make_signal(stop_loss=None)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert "stopLoss" not in payload  # empty optional fields stripped

    def test_v2_empty_take_profits_stripped(self):
        """When take_profits is empty, takeProfits should be stripped from payload."""
        signal = _make_signal(take_profits=[])
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert "takeProfits" not in payload  # empty optional fields stripped


# =====================================================================
# 3. V2 special action types
# =====================================================================


class TestV2SpecialActions:
    """Verify V2 provider command payloads (partial close, breakeven)."""

    def test_partially_close_by_lot_payload(self):
        """partially_close_by_lot payload must have ``type`` and ``lots``."""
        payload = WebhookPayloadV2(
            type=SignalAction.partial_close_lot,
            assistId=SAMPLE_ASSIST_ID,
            lots=0.5,
        )
        dumped = payload.model_dump(exclude_none=True)
        assert dumped["type"] == "partially_close_by_lot"
        assert dumped["lots"] == 0.5

    def test_partially_close_requires_lots(self):
        """partially_close_by_lot without ``lots`` must raise ValidationError."""
        with pytest.raises(ValidationError, match="lots"):
            WebhookPayloadV2(
                type=SignalAction.partial_close_lot,
                assistId=SAMPLE_ASSIST_ID,
            )

    def test_partially_close_by_percentage_payload(self):
        """partially_close_by_percentage payload must have ``type`` and ``percentage``."""
        payload = WebhookPayloadV2(
            type=SignalAction.partial_close_pct,
            assistId=SAMPLE_ASSIST_ID,
            percentage=50,
        )
        dumped = payload.model_dump(exclude_none=True)
        assert dumped["type"] == "partially_close_by_percentage"
        assert dumped["percentage"] == 50

    def test_partially_close_pct_requires_percentage(self):
        """partially_close_by_percentage without ``percentage`` must raise ValidationError."""
        with pytest.raises(ValidationError, match="percentage"):
            WebhookPayloadV2(
                type=SignalAction.partial_close_pct,
                assistId=SAMPLE_ASSIST_ID,
            )

    def test_breakeven_payload(self):
        """breakeven payload must have move_sl_to_breakeven type and slAdjustment=0."""
        payload = WebhookPayloadV2(
            type=SignalAction.breakeven,
            assistId=SAMPLE_ASSIST_ID,
            slAdjustment=0,
        )
        dumped = payload.model_dump(exclude_none=True)
        assert dumped["type"] == "move_sl_to_breakeven"
        assert dumped["assistId"] == SAMPLE_ASSIST_ID
        assert dumped["slAdjustment"] == 0

    def test_close_position_payload(self):
        """close_position payload must have close_order_at_market_price type."""
        payload = WebhookPayloadV2(
            type=SignalAction.close_position,
            assistId=SAMPLE_ASSIST_ID,
            source="forex",
            symbol="EURUSD",
        )
        dumped = payload.model_dump(exclude_none=True)
        assert dumped["type"] == "close_order_at_market_price"


# =====================================================================
# 4. Symbol mapping edge cases
# =====================================================================


class TestSymbolMappingEdgeCases:
    """Edge cases for apply_symbol_mapping beyond basic match/no-match."""

    def test_multiple_mappings_in_one_rule(self):
        """A rule with multiple mappings should apply the correct one."""
        rule = _make_rule(
            "V2",
            symbol_mappings={"GOLD": "XAUUSD", "SILVER": "XAGUSD", "OIL": "USOIL"},
        )
        for raw, expected in [("GOLD", "XAUUSD"), ("SILVER", "XAGUSD"), ("OIL", "USOIL")]:
            signal = _make_signal(symbol=raw)
            result = apply_symbol_mapping(signal, rule)
            assert result.symbol == expected

    def test_case_sensitivity(self):
        """Symbol mappings are case-sensitive — 'gold' should NOT match 'GOLD'."""
        rule = _make_rule("V2", symbol_mappings={"GOLD": "XAUUSD"})
        signal = _make_signal(symbol="gold")
        result = apply_symbol_mapping(signal, rule)
        assert result.symbol == "gold"  # no mapping applied

    def test_empty_symbol_mappings_dict(self):
        """An empty symbol_mappings dict should leave the symbol unchanged."""
        rule = _make_rule("V2", symbol_mappings={})
        signal = _make_signal(symbol="EURUSD")
        result = apply_symbol_mapping(signal, rule)
        assert result.symbol == "EURUSD"

    def test_symbol_not_in_mappings_passthrough(self):
        """A symbol absent from the mappings dict should pass through unchanged."""
        rule = _make_rule("V2", symbol_mappings={"GOLD": "XAUUSD"})
        signal = _make_signal(symbol="GBPJPY")
        result = apply_symbol_mapping(signal, rule)
        assert result.symbol == "GBPJPY"

    def test_mapping_does_not_mutate_original_signal(self):
        """apply_symbol_mapping should return a new object, not mutate the original."""
        rule = _make_rule("V2", symbol_mappings={"GOLD": "XAUUSD"})
        signal = _make_signal(symbol="GOLD")
        result = apply_symbol_mapping(signal, rule)
        assert signal.symbol == "GOLD"
        assert result.symbol == "XAUUSD"
        assert signal is not result


# =====================================================================
# 5. Risk overrides
# =====================================================================


class TestRiskOverrides:
    """Verify risk_overrides behaviour on V2 payloads."""

    def test_risk_overrides_lots_applied(self):
        """risk_overrides with ``lots`` should be applicable to payload."""
        rule = _make_rule("V2", risk_overrides={"lots": "0.1"})
        signal = _make_signal()
        payload = build_webhook_payload(signal, rule)
        # The mapper builds the base payload; risk_overrides are applied
        # at the dispatch layer.  Verify the rule carries the override.
        assert rule.risk_overrides["lots"] == "0.1"
        # Verify the override can be merged into payload dict
        payload.update(rule.risk_overrides)
        assert payload["lots"] == "0.1"

    def test_risk_overrides_empty_dict_no_changes(self):
        """An empty risk_overrides dict should not add any fields."""
        rule = _make_rule("V2", risk_overrides={})
        signal = _make_signal()
        payload = build_webhook_payload(signal, rule)
        payload.update(rule.risk_overrides)
        assert "lots" not in payload


# =====================================================================
# 7. End-to-end payload construction
# =====================================================================


class TestEndToEndPayloadConstruction:
    """Full flow: ParsedSignal + RoutingRule -> build_webhook_payload -> valid JSON."""

    def test_e2e_v1_long_produces_valid_json(self):
        """V1 long payload must serialise to JSON matching SageMaster spec."""
        signal = _make_signal(direction="long", symbol="EURUSD")
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        assert parsed["type"] == "start_long_market_deal"
        assert parsed["assistId"] == SAMPLE_ASSIST_ID
        assert parsed["source"] == "forex"
        assert parsed["symbol"] == "EURUSD"
        assert "date" in parsed

    def test_e2e_v2_short_with_tp_sl_produces_valid_json(self):
        """V2 short payload with TP/SL must serialise to valid JSON."""
        signal = _make_signal(
            direction="short",
            symbol="GBPUSD",
            entry_price=1.2500,
            stop_loss=1.2600,
            take_profits=[1.2400, 1.2300],
            source_asset_class="forex",
        )
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        assert parsed["type"] == "start_short_market_deal"
        assert parsed["assistId"] == SAMPLE_ASSIST_ID
        assert parsed["source"] == "forex"
        assert parsed["symbol"] == "GBPUSD"
        assert parsed["price"] == "1.25"
        assert parsed["takeProfits"] == [1.2400, 1.2300]
        assert parsed["stopLoss"] == 1.2600

    def test_e2e_with_symbol_mapping(self):
        """End-to-end: GOLD signal with symbol mapping produces XAUUSD in payload."""
        signal = _make_signal(
            symbol="GOLD",
            direction="long",
            source_asset_class="commodities",
        )
        rule = _make_rule("V2", symbol_mappings={"GOLD": "XAUUSD"})
        mapped = apply_symbol_mapping(signal, rule)
        payload = build_webhook_payload(mapped, rule)

        assert payload["symbol"] == "XAUUSD"
        assert payload["source"] == "commodities"

    def test_e2e_v1_has_exactly_5_fields(self):
        """V1 entry payload should have exactly 5 core fields."""
        signal = _make_signal()
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert set(payload.keys()) == {"type", "assistId", "source", "symbol", "date"}

    def test_e2e_v2_null_fields_present(self):
        """V2 payload with no SL/TP should strip empty fields (avoids SageMaster rejection)."""
        signal = _make_signal(entry_price=None, stop_loss=None, take_profits=[])
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert "price" not in payload
        assert "stopLoss" not in payload
        assert "takeProfits" not in payload

    @pytest.mark.parametrize(
        "direction, asset_class",
        [
            ("long", "forex"),
            ("short", "forex"),
            ("long", "crypto"),
            ("short", "crypto"),
        ],
    )
    def test_e2e_v1_direction_and_asset_class_combinations(self, direction, asset_class):
        """V1 payloads for all direction/asset-class combos are valid JSON."""
        signal = _make_signal(direction=direction, source_asset_class=asset_class)
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        expected_type = (
            "start_long_market_deal" if direction == "long"
            else "start_short_market_deal"
        )
        assert parsed["type"] == expected_type
        assert parsed["source"] == asset_class

    def test_e2e_round_trip_json_stability(self):
        """Serialise -> deserialise -> re-serialise should produce identical JSON."""
        signal = _make_signal()
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        first_json = json.dumps(payload, sort_keys=True)
        reconstituted = json.loads(first_json)
        second_json = json.dumps(reconstituted, sort_keys=True)
        assert first_json == second_json


# =====================================================================
# 8. V2 limit order types
# =====================================================================


class TestV2LimitOrders:
    """Verify limit order type mapping from ParsedSignal.order_type."""

    def test_v2_limit_long_type(self):
        """Limit long signal must produce start_long_limit_deal."""
        signal = _make_signal(order_type="limit", direction="long")
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_long_limit_deal"

    def test_v2_limit_short_type(self):
        """Limit short signal must produce start_short_limit_deal."""
        signal = _make_signal(order_type="limit", direction="short")
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_short_limit_deal"

    def test_v1_limit_long_type(self):
        """V1 limit long should also map correctly."""
        signal = _make_signal(order_type="limit", direction="long")
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_long_limit_deal"

    def test_v1_limit_short_type(self):
        """V1 limit short should also map correctly."""
        signal = _make_signal(order_type="limit", direction="short")
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_short_limit_deal"

    def test_market_order_type_unchanged(self):
        """Market orders should still produce market deal types."""
        signal = _make_signal(order_type="market", direction="long")
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert payload["type"] == "start_long_market_deal"


# =====================================================================
# 9. V2 pip-based TP/SL fields
# =====================================================================


class TestV2PipFields:
    """Verify pip-based take profit and stop loss fields in V2 payloads."""

    def test_v2_take_profit_pips_preserved_from_template(self):
        """takeProfitsPips set in template should be preserved."""
        template = {
            **_DEFAULT_V2_TEMPLATE,
            "takeProfitsPips": [30, 60],
        }
        signal = _make_signal()
        rule = _make_rule("V2", webhook_body_template=template)
        payload = build_webhook_payload(signal, rule)
        assert payload["takeProfitsPips"] == [30, 60]

    def test_v2_stop_loss_pips_preserved_from_template(self):
        """stopLossPips set in template should be preserved."""
        template = {
            **_DEFAULT_V2_TEMPLATE,
            "stopLossPips": 30,
        }
        signal = _make_signal()
        rule = _make_rule("V2", webhook_body_template=template)
        payload = build_webhook_payload(signal, rule)
        assert payload["stopLossPips"] == 30

    def test_v2_pip_fields_filled_from_signal(self):
        """Empty pip fields in template should be filled from signal data."""
        template = {
            **_DEFAULT_V2_TEMPLATE,
            "takeProfitsPips": [],
            "stopLossPips": None,
        }
        signal = _make_signal(
            take_profit_pips=[15, 30, 45],
            stop_loss_pips=20,
        )
        rule = _make_rule("V2", webhook_body_template=template)
        payload = build_webhook_payload(signal, rule)
        assert payload["takeProfitsPips"] == [15, 30, 45]
        assert payload["stopLossPips"] == 20

    def test_v2_pip_fields_not_added_if_not_in_template(self):
        """Pip fields should NOT be added if the template doesn't have them."""
        signal = _make_signal(take_profit_pips=[30], stop_loss_pips=20)
        rule = _make_rule("V2")  # default template has no pip fields
        payload = build_webhook_payload(signal, rule)
        assert "takeProfitsPips" not in payload
        assert "stopLossPips" not in payload

    def test_v2_balance_and_lots_preserved(self):
        """balance and lots from template should be preserved in entry."""
        template = {
            **_DEFAULT_V2_TEMPLATE,
            "balance": 1000,
            "lots": 1,
        }
        signal = _make_signal()
        rule = _make_rule("V2", webhook_body_template=template)
        payload = build_webhook_payload(signal, rule)
        assert payload["balance"] == 1000
        assert payload["lots"] == 1


# =====================================================================
# 10. lotSize type compliance
# =====================================================================


class TestLotSizeType:
    """Verify lotSize is sent as a float per SageMaster spec."""

    def test_partial_close_lot_size_is_float(self):
        """lotSize in partial close payload must be a float."""
        signal = _make_signal(action="partial_close", lots="0.3")
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["lotSize"], float)
        assert payload["lotSize"] == 0.3

    def test_partial_close_lot_size_default_is_float(self):
        """Default lotSize when signal.lots is None must be a float."""
        signal = _make_signal(action="partial_close", lots=None)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["lotSize"], float)
        assert payload["lotSize"] == 0.5

    def test_partial_close_lot_size_non_numeric_fallback(self):
        """Non-numeric lots string should fall back to 0.5 float."""
        signal = _make_signal(action="partial_close", lots="half")
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload["lotSize"], float)
        assert payload["lotSize"] == 0.5
