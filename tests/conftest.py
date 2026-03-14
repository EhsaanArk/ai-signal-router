"""Shared pytest fixtures for the SGM Telegram Signal Copier test suite."""

from uuid import UUID

import pytest

from src.core.models import ParsedSignal, RawSignal, RoutingRule


SAMPLE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_RULE_ID = UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_ASSIST_ID = "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
SAMPLE_WEBHOOK_URL = (
    "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
)

# Default templates used by test fixtures — the assistId comes from the user's
# SageMaster template, never from the webhook URL.
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


@pytest.fixture
def sample_parsed_signal() -> ParsedSignal:
    """A basic EURUSD long market signal."""
    return ParsedSignal(
        symbol="EURUSD",
        direction="long",
        order_type="market",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profits=[1.1050, 1.1100],
        source_asset_class="forex",
    )


@pytest.fixture
def sample_routing_rule_v1() -> RoutingRule:
    """Routing rule configured for V1 payloads with a default template."""
    return RoutingRule(
        id=SAMPLE_RULE_ID,
        user_id=SAMPLE_USER_ID,
        source_channel_id="-1001234567890",
        source_channel_name="VIP Signals",
        destination_webhook_url=SAMPLE_WEBHOOK_URL,
        payload_version="V1",
        webhook_body_template=_DEFAULT_V1_TEMPLATE.copy(),
    )


@pytest.fixture
def sample_routing_rule_v2() -> RoutingRule:
    """Routing rule configured for V2 payloads with symbol mappings and a default template."""
    return RoutingRule(
        id=SAMPLE_RULE_ID,
        user_id=SAMPLE_USER_ID,
        source_channel_id="-1001234567890",
        source_channel_name="VIP Signals",
        destination_webhook_url=SAMPLE_WEBHOOK_URL,
        payload_version="V2",
        symbol_mappings={"GOLD": "XAUUSD"},
        webhook_body_template=_DEFAULT_V2_TEMPLATE.copy(),
    )


@pytest.fixture
def sample_raw_signal() -> RawSignal:
    """A raw unprocessed Telegram signal message."""
    return RawSignal(
        user_id=SAMPLE_USER_ID,
        channel_id="-1001234567890",
        raw_message="EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050\nTP2: 1.1100",
        message_id=42,
    )
