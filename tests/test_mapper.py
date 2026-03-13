"""Tests for src.core.mapper — symbol mapping, payload building, tier limits."""

from src.core.mapper import (
    apply_symbol_mapping,
    build_webhook_payload,
    check_tier_limit,
    extract_asset_id,
)
from src.core.models import (
    ParsedSignal,
    RoutingRule,
    SignalAction,
    SubscriptionTier,
    WebhookPayloadV1,
    WebhookPayloadV2,
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


# ---- build_webhook_payload V1 ----


def test_build_webhook_payload_v1(sample_parsed_signal, sample_routing_rule_v1):
    """V1 payload must contain type, assetId, source, symbol, and date."""
    payload = build_webhook_payload(sample_parsed_signal, sample_routing_rule_v1)
    assert isinstance(payload, WebhookPayloadV1)
    assert payload.type == "start_long_market_deal"
    assert payload.assetId == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
    assert payload.source == "forex"
    assert payload.symbol == "EURUSD"
    assert payload.date is not None


def test_build_webhook_payload_v1_short(sample_routing_rule_v1):
    """Short direction should produce 'start_short_market_deal'."""
    signal = ParsedSignal(symbol="GBPUSD", direction="short")
    payload = build_webhook_payload(signal, sample_routing_rule_v1)
    assert isinstance(payload, WebhookPayloadV1)
    assert payload.type == "start_short_market_deal"


# ---- build_webhook_payload V2 ----


def test_build_webhook_payload_v2(sample_parsed_signal, sample_routing_rule_v2):
    """V2 payload must include price, takeProfits, and stopLoss."""
    payload = build_webhook_payload(sample_parsed_signal, sample_routing_rule_v2)
    assert isinstance(payload, WebhookPayloadV2)
    assert payload.type == SignalAction.start_long
    assert payload.assetId == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
    assert payload.source == "forex"
    assert payload.symbol == "EURUSD"
    assert payload.price == "1.1"
    assert payload.takeProfits == [1.1050, 1.1100]
    assert payload.stopLoss == 1.0950


# ---- check_tier_limit ----


def test_check_tier_limit_within():
    """Should return True when current count is below the tier maximum."""
    assert check_tier_limit(SubscriptionTier.free, 0) is True
    assert check_tier_limit(SubscriptionTier.pro, 4) is True


def test_check_tier_limit_exceeded():
    """Should return False when current count meets or exceeds the tier maximum."""
    assert check_tier_limit(SubscriptionTier.free, 1) is False
    assert check_tier_limit(SubscriptionTier.starter, 2) is False
    assert check_tier_limit(SubscriptionTier.pro, 5) is False


# ---- extract_asset_id ----


def test_extract_asset_id():
    """Should extract UUID from a SageMaster webhook URL."""
    url = "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
    assert extract_asset_id(url) == "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
