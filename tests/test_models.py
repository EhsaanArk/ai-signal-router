"""Tests for src.core.models — Pydantic model validation and defaults."""

from uuid import UUID

from src.core.models import (
    ParsedSignal,
    RawSignal,
    RoutingRule,
    SubscriptionTier,
)


def test_subscription_tier_max_destinations():
    """Each tier should report the correct max_destinations value."""
    assert SubscriptionTier.free.max_destinations == 1
    assert SubscriptionTier.starter.max_destinations == 2
    assert SubscriptionTier.pro.max_destinations == 5
    assert SubscriptionTier.elite.max_destinations == 15


def test_parsed_signal_defaults():
    """ParsedSignal should have sensible defaults for optional fields."""
    signal = ParsedSignal(symbol="EURUSD", direction="long")
    assert signal.order_type == "market"
    assert signal.entry_price is None
    assert signal.stop_loss is None
    assert signal.take_profits == []
    assert signal.source_asset_class == "forex"
    assert signal.is_valid_signal is True
    assert signal.ignore_reason is None


def test_routing_rule_defaults():
    """RoutingRule should have sensible defaults for optional fields."""
    rule = RoutingRule(
        user_id=UUID("11111111-1111-1111-1111-111111111111"),
        source_channel_id="-1001234567890",
        destination_webhook_url="https://api.sagemaster.io/deals_idea/abc",
    )
    assert rule.payload_version == "V1"
    assert rule.symbol_mappings == {}
    assert rule.risk_overrides == {}
    assert rule.is_active is True
    assert rule.source_channel_name is None
    assert isinstance(rule.id, UUID)


def test_raw_signal_creation(sample_raw_signal):
    """RawSignal should be creatable with valid data and have correct fields."""
    assert sample_raw_signal.channel_id == "-1001234567890"
    assert sample_raw_signal.message_id == 42
    assert "EURUSD" in sample_raw_signal.raw_message
    assert sample_raw_signal.timestamp is not None
