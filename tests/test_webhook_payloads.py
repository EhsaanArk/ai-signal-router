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
    extract_asset_id,
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
SAMPLE_ASSET_ID = "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
SAMPLE_WEBHOOK_URL = f"https://api.sagemaster.io/deals_idea/{SAMPLE_ASSET_ID}"

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


def _make_rule(version: str = "V1", **overrides) -> RoutingRule:
    defaults = dict(
        id=SAMPLE_RULE_ID,
        user_id=SAMPLE_USER_ID,
        source_channel_id="-1001234567890",
        destination_webhook_url=SAMPLE_WEBHOOK_URL,
        payload_version=version,
    )
    defaults.update(overrides)
    return RoutingRule(**defaults)


# =====================================================================
# 1. V1 payload schema compliance
# =====================================================================


class TestV1SchemaCompliance:
    """Verify V1 payloads match the SageMaster specification exactly."""

    def test_v1_has_exactly_required_fields(self):
        """V1 payload must have EXACTLY: type, assetId, source, symbol, date."""
        signal = _make_signal()
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        dumped = payload.model_dump()
        assert set(dumped.keys()) == {"type", "assetId", "source", "symbol", "date"}

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
        assert payload.type == expected_type

    def test_v1_source_matches_signal_source_asset_class(self):
        """V1 ``source`` must match the signal's source_asset_class."""
        for asset_class in ("forex", "crypto", "indices"):
            signal = _make_signal(source_asset_class=asset_class)
            rule = _make_rule("V1")
            payload = build_webhook_payload(signal, rule)
            assert payload.source == asset_class

    def test_v1_date_is_iso8601(self):
        """V1 ``date`` must be an ISO 8601 formatted string."""
        signal = _make_signal()
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        assert ISO_8601_RE.match(payload.date), f"Date is not ISO 8601: {payload.date}"
        # Also verify it can be parsed as a datetime
        datetime.fromisoformat(payload.date)


# =====================================================================
# 2. V2 payload schema compliance
# =====================================================================


class TestV2SchemaCompliance:
    """Verify V2 payloads match the SageMaster specification."""

    def test_v2_has_v1_fields_plus_extras(self):
        """V2 payload must have all V1 fields (except date) PLUS price, takeProfits, stopLoss."""
        signal = _make_signal()
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        dumped = payload.model_dump(exclude_none=True)
        v1_fields = {"type", "assetId", "source", "symbol"}
        v2_extras = {"price", "takeProfits", "stopLoss"}
        assert v1_fields.issubset(set(dumped.keys()))
        assert v2_extras.issubset(set(dumped.keys()))

    def test_v2_take_profits_is_list(self):
        """V2 ``takeProfits`` must be a list of floats."""
        signal = _make_signal(take_profits=[1.1050, 1.1100, 1.1200])
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload.takeProfits, list)
        assert all(isinstance(tp, float) for tp in payload.takeProfits)

    def test_v2_price_is_string(self):
        """V2 ``price`` must be a string per the SageMaster spec."""
        signal = _make_signal(entry_price=1.2345)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload.price, str)

    def test_v2_stop_loss_is_float(self):
        """V2 ``stopLoss`` must be a float."""
        signal = _make_signal(stop_loss=1.0900)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert isinstance(payload.stopLoss, float)

    def test_v2_multiple_take_profit_levels(self):
        """V2 payload should handle 1, 3, and 5 take profit levels."""
        for tp_count in (1, 3, 5):
            tps = [1.1000 + (i * 0.005) for i in range(1, tp_count + 1)]
            signal = _make_signal(take_profits=tps)
            rule = _make_rule("V2")
            payload = build_webhook_payload(signal, rule)
            assert len(payload.takeProfits) == tp_count

    def test_v2_no_entry_price_yields_none(self):
        """When entry_price is None, V2 price field should be None."""
        signal = _make_signal(entry_price=None)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert payload.price is None

    def test_v2_no_stop_loss_yields_none(self):
        """When stop_loss is None, V2 stopLoss field should be None."""
        signal = _make_signal(stop_loss=None)
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert payload.stopLoss is None

    def test_v2_empty_take_profits_yields_none(self):
        """When take_profits is empty, V2 takeProfits should be None."""
        signal = _make_signal(take_profits=[])
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        assert payload.takeProfits is None


# =====================================================================
# 3. V2 special action types
# =====================================================================


class TestV2SpecialActions:
    """Verify V2 provider command payloads (partial close, breakeven)."""

    def test_partially_close_by_lot_payload(self):
        """partially_close_by_lot payload must have ``type`` and ``lots``."""
        payload = WebhookPayloadV2(
            type=SignalAction.partial_close,
            assetId=SAMPLE_ASSET_ID,
            lots="0.5",
        )
        dumped = payload.model_dump(exclude_none=True)
        assert dumped["type"] == "partially_close_by_lot"
        assert dumped["lots"] == "0.5"
        assert "symbol" not in dumped
        assert "source" not in dumped

    def test_partially_close_requires_lots(self):
        """partially_close_by_lot without ``lots`` must raise ValidationError."""
        with pytest.raises(ValidationError, match="lots"):
            WebhookPayloadV2(
                type=SignalAction.partial_close,
                assetId=SAMPLE_ASSET_ID,
            )

    def test_breakeven_payload(self):
        """breakeven payload requires only ``type`` and ``assetId``."""
        payload = WebhookPayloadV2(
            type=SignalAction.breakeven,
            assetId=SAMPLE_ASSET_ID,
        )
        dumped = payload.model_dump(exclude_none=True)
        assert dumped["type"] == "breakeven"
        assert dumped["assetId"] == SAMPLE_ASSET_ID
        # No extra fields needed
        assert "symbol" not in dumped
        assert "lots" not in dumped

    def test_breakeven_minimal_keys(self):
        """breakeven serialised payload should only have type and assetId."""
        payload = WebhookPayloadV2(
            type=SignalAction.breakeven,
            assetId=SAMPLE_ASSET_ID,
        )
        dumped = payload.model_dump(exclude_none=True)
        assert set(dumped.keys()) == {"type", "assetId"}


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
        """risk_overrides with ``lots`` should be applicable to V2 payload."""
        rule = _make_rule("V2", risk_overrides={"lots": "0.1"})
        signal = _make_signal()
        payload = build_webhook_payload(signal, rule)
        # The mapper builds the base payload; risk_overrides are applied
        # at the dispatch layer.  Verify the rule carries the override.
        assert rule.risk_overrides["lots"] == "0.1"
        # Verify the override can be merged into a serialised payload
        dumped = payload.model_dump(exclude_none=True)
        dumped.update(rule.risk_overrides)
        assert dumped["lots"] == "0.1"

    def test_risk_overrides_empty_dict_no_changes(self):
        """An empty risk_overrides dict should not add any fields."""
        rule = _make_rule("V2", risk_overrides={})
        signal = _make_signal()
        payload = build_webhook_payload(signal, rule)
        dumped = payload.model_dump(exclude_none=True)
        dumped.update(rule.risk_overrides)
        assert "lots" not in dumped


# =====================================================================
# 6. Asset ID extraction edge cases
# =====================================================================


class TestAssetIdExtraction:
    """Edge cases for extract_asset_id beyond the happy path."""

    def test_standard_url(self):
        """Standard SageMaster webhook URL."""
        url = "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
        assert extract_asset_id(url) == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"

    def test_url_with_trailing_slash(self):
        """URL with a trailing slash should still extract the UUID."""
        url = "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307/"
        assert extract_asset_id(url) == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"

    def test_url_with_query_parameters(self):
        """URL with query params should still extract the UUID."""
        url = "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307?token=abc"
        assert extract_asset_id(url) == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"

    def test_alternative_host_url(self):
        """UUID extraction should work regardless of hostname."""
        url = "https://app.sagemaster.com/api/webhook/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
        assert extract_asset_id(url) == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "https://api.sagemaster.io/deals_idea/not-a-uuid",
            "https://api.sagemaster.io/deals_idea/",
            "https://api.sagemaster.io/",
            "",
            "no-url-at-all",
        ],
        ids=["bad-uuid", "empty-path", "root-path", "empty-string", "plain-text"],
    )
    def test_invalid_url_raises_value_error(self, invalid_url):
        """URLs without a valid UUID must raise ValueError."""
        with pytest.raises(ValueError, match="Could not extract asset ID"):
            extract_asset_id(invalid_url)

    def test_url_with_multiple_uuids_returns_last(self):
        """When a URL contains multiple UUIDs, the last one is the asset ID."""
        url = (
            "https://api.sagemaster.io/orgs/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            "/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
        )
        assert extract_asset_id(url) == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"


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
        dumped = payload.model_dump()
        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)

        assert parsed["type"] == "start_long_market_deal"
        assert parsed["assetId"] == SAMPLE_ASSET_ID
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
        dumped = payload.model_dump(exclude_none=True)
        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)

        assert parsed["type"] == "start_short_market_deal"
        assert parsed["assetId"] == SAMPLE_ASSET_ID
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
        dumped = payload.model_dump(exclude_none=True)

        assert dumped["symbol"] == "XAUUSD"
        assert dumped["source"] == "commodities"

    def test_e2e_v1_exclude_none_has_no_extra_fields(self):
        """V1 payload serialised with exclude_none should have exactly 5 fields."""
        signal = _make_signal()
        rule = _make_rule("V1")
        payload = build_webhook_payload(signal, rule)
        dumped = payload.model_dump(exclude_none=True)
        assert len(dumped) == 5
        assert set(dumped.keys()) == {"type", "assetId", "source", "symbol", "date"}

    def test_e2e_v2_exclude_none_omits_null_fields(self):
        """V2 payload with no SL/TP should omit those keys when exclude_none=True."""
        signal = _make_signal(entry_price=None, stop_loss=None, take_profits=[])
        rule = _make_rule("V2")
        payload = build_webhook_payload(signal, rule)
        dumped = payload.model_dump(exclude_none=True)
        assert "price" not in dumped
        assert "stopLoss" not in dumped
        assert "takeProfits" not in dumped

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
        dumped = payload.model_dump()
        json_str = json.dumps(dumped)
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
        dumped = payload.model_dump(exclude_none=True)
        first_json = json.dumps(dumped, sort_keys=True)
        reconstituted = json.loads(first_json)
        second_json = json.dumps(reconstituted, sort_keys=True)
        assert first_json == second_json
