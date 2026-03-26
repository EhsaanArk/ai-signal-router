"""QA Orchestrator test helpers — reusable factories for any agent.

Usage (webhook contract test):
    from tests.qa_helpers import forex_rule, crypto_rule, assert_payload_contract

    def test_my_new_action():
        signal = ParsedSignal(action="my_action", symbol="XAUUSD")
        payload = build_webhook_payload(signal, forex_rule("V1"))
        assert_payload_contract(payload, expected_type="my_action_type", forex=True)

Usage (parser fixture):
    from tests.qa_helpers import add_fixture_signal, FIXTURES_DIR

    # Step 1: Add raw signal to raw_signals.txt
    # Step 2: Add expected output to expected_payloads.json
    # Step 3: Classify in test_parser_fixtures.py (_ENTRY_IDS, _MANAGEMENT_IDS, or _IGNORED_IDS)

Usage (E2E smoke test signal):
    from tests.qa_helpers import SAMPLE_SIGNALS

    signal_text = SAMPLE_SIGNALS["forex_buy"]  # Pre-built signal strings
"""

from __future__ import annotations

from src.core.mapper import build_webhook_payload
from src.core.models import ParsedSignal, RoutingRule

# ---------------------------------------------------------------------------
# Constants — shared across all QA test files
# ---------------------------------------------------------------------------

SAMPLE_USER_ID = "11111111-1111-1111-1111-111111111111"
SAMPLE_RULE_ID = "22222222-2222-2222-2222-222222222222"
SAMPLE_ASSIST_ID = "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
SAMPLE_AI_ASSIST_ID = "aaa79d52-1ab9-4d3b-a7ca-125b2f5e0307"

# Pre-built signal strings for E2E and smoke tests
SAMPLE_SIGNALS = {
    "forex_buy": "BUY GBPUSD @ 1.2650\nTP1: 1.2700\nTP2: 1.2750\nSL: 1.2600",
    "forex_sell": "SELL XAUUSD @ 2350.50\nTP: 2330.00\nSL: 2360.00",
    "crypto_long": "LONG BTC/USDT\nEntry: 95000\nTP: 98000\nSL: 93000",
    "crypto_short": "SHORT ETH/USDT\nEntry: 3500\nTP: 3200\nSL: 3700",
    "close_all": "Close all trades now",
    "partial_close": "Close half of EURUSD position now",
    "breakeven": "Move SL to breakeven on XAUUSD",
    "nonsignal": "Good morning everyone! Have a great trading day",
}


# ---------------------------------------------------------------------------
# Rule factories — create routing rules for contract tests
# ---------------------------------------------------------------------------

def forex_rule(
    version: str = "V1",
    template: dict | None = None,
    assist_id: str = SAMPLE_ASSIST_ID,
) -> RoutingRule:
    """Create a forex routing rule for contract testing.

    Args:
        version: "V1" or "V2"
        template: Custom webhook body template. If None, uses default.
        assist_id: SageMaster Assist ID for the template.

    Example:
        rule = forex_rule("V2")
        payload = build_webhook_payload(signal, rule)
    """
    tpl = template or {
        "type": "",
        "assistId": assist_id,
        "source": "",
        "symbol": "",
        "date": "",
    }
    if version == "V2" and template is None:
        tpl.update({"price": "", "takeProfits": [], "stopLoss": None})
    return RoutingRule(
        id=SAMPLE_RULE_ID,
        user_id=SAMPLE_USER_ID,
        source_channel_id="-100123",
        destination_webhook_url="https://sfx.sagemaster.io/deals_idea/test",
        payload_version=version,
        destination_type="sagemaster_forex",
        webhook_body_template=tpl,
    )


def crypto_rule(
    template: dict | None = None,
    ai_assist_id: str = SAMPLE_AI_ASSIST_ID,
) -> RoutingRule:
    """Create a crypto routing rule for contract testing.

    Args:
        template: Custom webhook body template. If None, uses default.
        ai_assist_id: SageMaster AI Assist ID for the template.

    Example:
        rule = crypto_rule()
        payload = build_webhook_payload(signal, rule)
    """
    tpl = template or {
        "type": "",
        "aiAssistId": ai_assist_id,
        "exchange": "binance",
        "tradeSymbol": "",
        "eventSymbol": "",
        "price": "",
        "date": "",
    }
    return RoutingRule(
        id=SAMPLE_RULE_ID,
        user_id=SAMPLE_USER_ID,
        source_channel_id="-100123",
        destination_webhook_url="https://api.sagemaster.io/deals_idea/test",
        payload_version="V1",
        destination_type="sagemaster_crypto",
        webhook_body_template=tpl,
    )


# ---------------------------------------------------------------------------
# Contract assertions — validate payload structure
# ---------------------------------------------------------------------------

# Required fields per destination type
_FOREX_REQUIRED = {"type", "assistId", "source", "date"}
_CRYPTO_REQUIRED = {"type", "aiAssistId", "exchange", "date"}

# Fields that must NOT appear on management actions
_ENTRY_ONLY_FIELDS = {"price", "takeProfits", "takeProfitsPips", "stopLoss", "stopLossPips", "balance"}

# Symbolless actions — these operate on all positions, no symbol needed
_SYMBOLLESS_TYPES = {
    "close_all_orders_at_market_price",
    "close_all_orders_at_market_price_and_stop_assist",
    "start_assist",
    "stop_assist",
    "close_all_deals_at_market_price",
    "close_all_deals_at_market_price_and_stop_ai_assist",
    "start_ai_assist_and_deal",
    "stop_ai_assist",
}


def assert_payload_contract(
    payload: dict,
    expected_type: str,
    forex: bool = True,
    is_entry: bool = False,
    is_management: bool = False,
) -> None:
    """Assert a webhook payload conforms to SageMaster's contract.

    Args:
        payload: The payload dict from build_webhook_payload()
        expected_type: Expected value of the "type" field
        forex: True for forex destination, False for crypto
        is_entry: True if this is an entry signal (validates entry fields)
        is_management: True if this is a management action (validates no entry fields)

    Example:
        payload = build_webhook_payload(signal, forex_rule("V1"))
        assert_payload_contract(payload, "start_long_market_deal", forex=True, is_entry=True)
    """
    # Check type
    assert payload["type"] == expected_type, (
        f"Expected type '{expected_type}', got '{payload['type']}'"
    )

    # Check required fields
    required = _FOREX_REQUIRED if forex else _CRYPTO_REQUIRED
    for field in required:
        assert field in payload, f"Missing required field '{field}' in payload"

    # Check symbol rules
    if payload["type"] in _SYMBOLLESS_TYPES:
        for sym_field in ("symbol", "tradeSymbol", "eventSymbol"):
            assert sym_field not in payload, (
                f"Symbolless action '{payload['type']}' should not have '{sym_field}'"
            )

    # Check management actions don't carry entry fields
    if is_management:
        for field in _ENTRY_ONLY_FIELDS:
            assert field not in payload, (
                f"Management action should not have entry field '{field}'"
            )

    # Check entry has non-empty date
    assert payload.get("date"), "Payload must have a non-empty 'date' field"


def assert_entry_payload(
    payload: dict,
    expected_type: str,
    expected_symbol: str,
    forex: bool = True,
) -> None:
    """Shorthand for entry signal contract assertion.

    Example:
        assert_entry_payload(payload, "start_long_market_deal", "EURUSD")
    """
    assert_payload_contract(payload, expected_type, forex=forex, is_entry=True)
    if forex:
        assert payload.get("symbol") == expected_symbol
    else:
        # Crypto uses tradeSymbol or eventSymbol
        assert expected_symbol in (
            payload.get("tradeSymbol", ""),
            payload.get("eventSymbol", ""),
            payload.get("symbol", ""),
        )


def assert_management_payload(
    payload: dict,
    expected_type: str,
    forex: bool = True,
) -> None:
    """Shorthand for management action contract assertion.

    Example:
        assert_management_payload(payload, "close_order_at_market_price")
    """
    assert_payload_contract(payload, expected_type, forex=forex, is_management=True)
