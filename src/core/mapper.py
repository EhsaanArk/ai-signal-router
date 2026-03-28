"""Signal mapping and webhook payload construction.

Pure domain logic — no infrastructure imports.  Responsible for:

* Applying per-rule symbol mappings (e.g. "GOLD" -> "XAUUSD").
* Building SageMaster webhook payloads from user-provided templates.
* Enforcing subscription-tier destination limits.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.core.models import (
    CRYPTO_ACTION_TYPE,
    ParsedSignal,
    RoutingRule,
    SignalAction,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)


def _utc_timestamp() -> str:
    """Return a UTC timestamp in the format SGM/TradingView expects: ``2026-03-13T21:19:00Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _replace_placeholders(template: dict, signal: "ParsedSignal") -> dict:
    """Replace TradingView ``{{...}}`` placeholders in template string values."""
    tv_vars = {
        "{{time}}": _utc_timestamp(),
        "{{close}}": str(signal.entry_price) if signal.entry_price is not None else "",
        "{{ticker}}": signal.symbol,
    }
    result = {}
    for key, value in template.items():
        if isinstance(value, str):
            for placeholder, replacement in tv_vars.items():
                value = value.replace(placeholder, replacement)
        result[key] = value
    return result


# Fields that should be stripped from the template for management actions
_ENTRY_ONLY_FIELDS = {"price", "takeProfits", "takeProfitsPips", "stopLoss", "stopLossPips", "balance"}


# ---------------------------------------------------------------------------
# Symbol mapping
# ---------------------------------------------------------------------------

def apply_symbol_mapping(signal: ParsedSignal, rule: RoutingRule) -> ParsedSignal:
    """Return a copy of *signal* with the symbol remapped if a mapping exists.

    If ``signal.symbol`` is a key in ``rule.symbol_mappings``, the returned
    ``ParsedSignal`` will have its ``symbol`` replaced with the mapped value.
    Otherwise the signal is returned unchanged.
    """
    if signal.symbol in rule.symbol_mappings:
        return signal.model_copy(
            update={"symbol": rule.symbol_mappings[signal.symbol]}
        )
    return signal


# ---------------------------------------------------------------------------
# Webhook payload builders
# ---------------------------------------------------------------------------

def _signal_action(signal: ParsedSignal) -> SignalAction:
    """Map a ``ParsedSignal`` to the corresponding ``SignalAction``.

    For entry signals, maps by direction.  For follow-up actions, maps
    directly to the corresponding ``SignalAction`` enum member.
    """
    action = signal.action
    if action == "entry":
        is_limit = signal.order_type in ("limit", "stop")
        # Safety: reject limit/stop orders without an entry price
        if is_limit and signal.entry_price is None:
            raise ValueError(
                f"Limit/stop order requires an entry price but none was provided "
                f"(order_type={signal.order_type}, symbol={signal.symbol})"
            )
        if signal.direction == "long":
            return SignalAction.start_long_limit if is_limit else SignalAction.start_long
        elif signal.direction == "short":
            return SignalAction.start_short_limit if is_limit else SignalAction.start_short
        raise ValueError(f"Unsupported direction: {signal.direction}")
    if action == "partial_close":
        # Choose lot-based or percentage-based depending on signal data
        if signal.percentage is not None:
            return SignalAction.partial_close_pct
        return SignalAction.partial_close_lot
    if action == "breakeven":
        return SignalAction.breakeven
    if action == "close_position":
        return SignalAction.close_position
    if action == "close_all":
        return SignalAction.close_all
    if action == "close_all_stop":
        return SignalAction.close_all_stop
    if action == "start_assist":
        return SignalAction.start_assist
    if action == "stop_assist":
        return SignalAction.stop_assist
    if action == "modify_sl":
        # modify_sl maps to breakeven — but absolute SL prices are rejected
        # in _inject_management_fields / _inject_crypto_management_fields
        return SignalAction.breakeven
    if action == "extra_order":
        return SignalAction.extra_order
    if action == "modify_tp":
        # modify_tp has no SageMaster equivalent — will be logged as unsupported
        raise ValueError("Action 'modify_tp' is not supported by SageMaster")
    if action == "trailing_sl":
        # trailing_sl maps to breakeven with slAdjustment = trailing pip value
        return SignalAction.breakeven
    raise ValueError(f"Unknown action: {action}")


def _strip_entry_fields(payload: dict) -> dict:
    """Remove entry-specific fields from a management action payload."""
    for field in _ENTRY_ONLY_FIELDS:
        payload.pop(field, None)
    # Also strip lots unless it's a partial close by lot
    return payload


def _inject_management_fields(payload: dict, signal: ParsedSignal, action: SignalAction) -> dict:
    """Add forex management-specific fields to the payload."""
    if action == SignalAction.partial_close_lot:
        try:
            payload["lotSize"] = float(signal.lots) if signal.lots else 0.5
        except (ValueError, TypeError):
            payload["lotSize"] = 0.5
        payload.pop("lots", None)
    elif action == SignalAction.partial_close_pct:
        payload["percentage"] = signal.percentage or 50
    elif action == SignalAction.breakeven:
        if signal.action == "modify_sl" and signal.new_sl is not None:
            # Absolute SL modification is not supported by SageMaster.
            # slAdjustment is a pip offset from entry, not an absolute price.
            # Passing an absolute price (e.g. 2350) would be misinterpreted as
            # a 2350-pip offset, causing wildly incorrect SL placement.
            raise ValueError(
                f"Absolute SL modification is not supported by SageMaster "
                f"(new_sl={signal.new_sl}). Only breakeven with pip offset "
                f"is supported via move_sl_to_breakeven."
            )
        elif signal.action == "trailing_sl" and signal.trailing_sl_pips is not None:
            payload["slAdjustment"] = signal.trailing_sl_pips
        elif signal.breakeven_offset_pips is not None:
            payload["slAdjustment"] = signal.breakeven_offset_pips
        else:
            payload["slAdjustment"] = 0
    return payload


def _inject_crypto_management_fields(
    payload: dict, signal: ParsedSignal, action: SignalAction,
) -> dict:
    """Add crypto management-specific fields per documented crypto schema.

    Key differences from forex:
    - Partial close uses ``position_type`` + ``percentage`` (no lot-based close)
    - SL adjustment uses ``sl_adjustment`` (snake_case, not camelCase)
    - ``position_type`` is required for partial close and SL adjustment
    """
    position_type = signal.direction or "long"

    if action == SignalAction.partial_close_lot:
        # Crypto does not support lot-based partial close
        if signal.percentage:
            payload["percentage"] = signal.percentage
        else:
            raise ValueError(
                f"Crypto does not support lot-based partial close "
                f"(lots={signal.lots}). Use a percentage instead "
                f"(e.g. 'close 50%' instead of 'close 0.5 lots')."
            )
        payload["position_type"] = position_type
        payload.pop("lotSize", None)
        payload.pop("lots", None)
    elif action == SignalAction.partial_close_pct:
        payload["percentage"] = signal.percentage or 50
        payload["position_type"] = position_type
    elif action == SignalAction.breakeven:
        if signal.action == "modify_sl" and signal.new_sl is not None:
            # Crypto sl_adjustment is a relative offset, not absolute price.
            # Absolute SL modification is not supported by SageMaster crypto.
            raise ValueError(
                f"Crypto does not support absolute SL modification "
                f"(new_sl={signal.new_sl}). Only breakeven with pip offset "
                f"is supported via moved_sl_adjustment."
            )
        elif signal.action == "trailing_sl" and signal.trailing_sl_pips is not None:
            payload["sl_adjustment"] = signal.trailing_sl_pips
        elif signal.breakeven_offset_pips is not None:
            payload["sl_adjustment"] = signal.breakeven_offset_pips
        else:
            payload["sl_adjustment"] = 0
        payload["position_type"] = position_type
    elif action == SignalAction.extra_order:
        payload["position_type"] = position_type
        payload["is_market"] = signal.is_market if signal.is_market is not None else True
        if signal.order_price is not None:
            payload["order_price"] = signal.order_price
    # close_position needs no extra fields beyond type
    return payload


def build_webhook_payload(
    signal: ParsedSignal, rule: RoutingRule
) -> dict:
    """Construct a webhook payload dict from the rule's template.

    A ``webhook_body_template`` is required.  The template must contain the
    ``assistId`` (forex) or ``aiAssistId`` (crypto) provided by the user —
    this function never injects or overwrites those fields.

    Parameters
    ----------
    signal:
        The parsed (and optionally symbol-mapped) signal.
    rule:
        The routing rule whose ``webhook_body_template`` and
        ``payload_version`` determine payload shape.

    Returns
    -------
    dict
        The constructed payload ready to POST.

    Raises
    ------
    ValueError
        If the rule has no ``webhook_body_template``.
    """
    if not rule.webhook_body_template:
        raise ValueError(
            "Webhook body template is required for SageMaster destinations. "
            "Copy the JSON from your SageMaster Assists overview page > "
            "alert configuration in SageMaster."
        )

    action = _signal_action(signal)

    # ------------------------------------------------------------------
    # Follow-up actions (non-entry)
    # ------------------------------------------------------------------
    is_crypto = rule.destination_type == "sagemaster_crypto"

    if signal.action != "entry":
        payload: dict = _replace_placeholders(rule.webhook_body_template, signal)
        _strip_entry_fields(payload)

        # Symbol-less actions: strip symbol fields (these operate on all positions or the Assist itself)
        _SYMBOLLESS_ACTIONS = {SignalAction.close_all, SignalAction.close_all_stop, SignalAction.start_assist, SignalAction.stop_assist}
        if action in _SYMBOLLESS_ACTIONS:
            for field in ("symbol", "tradeSymbol", "eventSymbol"):
                payload.pop(field, None)

        if is_crypto:
            # Map forex SignalAction to documented crypto type string
            crypto_key = action.name  # e.g. "partial_close_pct", "breakeven"
            payload["type"] = CRYPTO_ACTION_TYPE.get(crypto_key, action.value)
            _inject_crypto_management_fields(payload, signal, action)
        else:
            payload["type"] = action.value
            _inject_management_fields(payload, signal, action)
        return payload

    # ------------------------------------------------------------------
    # Entry signals
    # ------------------------------------------------------------------
    payload = _replace_placeholders(rule.webhook_body_template, signal)
    # Fill empty-string fields from signal data
    if payload.get("type") == "":
        payload["type"] = CRYPTO_ACTION_TYPE["start_deal"] if is_crypto else action.value
    if payload.get("date") == "":
        payload["date"] = _utc_timestamp()
    if payload.get("symbol") == "":
        payload["symbol"] = signal.symbol
    if payload.get("tradeSymbol") == "":
        payload["tradeSymbol"] = signal.symbol
    if payload.get("eventSymbol") == "":
        payload["eventSymbol"] = signal.symbol
    if payload.get("source") == "":
        payload["source"] = signal.source_asset_class
    # Signal-driven fields — fill when template has the key with empty/falsy
    # value.  Gated by V2 for forex; crypto always fills (no V1/V2 split).
    # V1 limit orders also need price filled to avoid market-order fallback.
    # Empty fields are stripped below so SageMaster doesn't reject them.
    is_limit_order = signal.order_type in ("limit", "stop")
    should_fill_signal_fields = rule.payload_version == "V2" or is_crypto
    # Always fill price for limit/stop orders regardless of payload version
    if should_fill_signal_fields or is_limit_order:
        if payload.get("price") == "":
            payload["price"] = str(signal.entry_price) if signal.entry_price is not None else ""
    if should_fill_signal_fields:
        if "take_profits" in payload and not payload["take_profits"]:
            payload["take_profits"] = signal.take_profits
        if "takeProfits" in payload and not payload["takeProfits"]:
            payload["takeProfits"] = signal.take_profits
        if "takeProfitsPips" in payload and not payload["takeProfitsPips"]:
            payload["takeProfitsPips"] = signal.take_profit_pips or []
        if "stopLoss" in payload and not payload["stopLoss"]:
            payload["stopLoss"] = signal.stop_loss
        if "stop_loss" in payload and not payload["stop_loss"]:
            payload["stop_loss"] = signal.stop_loss
        if "stopLossPips" in payload and not payload["stopLossPips"]:
            payload["stopLossPips"] = signal.stop_loss_pips
    # Crypto: inject TP/SL from signal even if template doesn't have the keys.
    # Crypto templates often omit TP/SL fields, but SageMaster accepts them
    # on start_deal payloads (take_profits as %, stopLoss as %).
    if is_crypto:
        if signal.take_profits and "take_profits" not in payload:
            payload["take_profits"] = signal.take_profits
        if signal.stop_loss is not None and "stopLoss" not in payload and "stop_loss" not in payload:
            payload["stopLoss"] = signal.stop_loss
    # Crypto entry also needs position_type from signal direction
    if is_crypto:
        if "position_type" not in payload or not payload.get("position_type"):
            payload["position_type"] = signal.direction or "long"

    # Ensure numeric fields are sent as numbers, not strings.
    # Template builder stores user input as strings; SageMaster rejects string lots.
    if "lots" in payload and payload["lots"] is not None:
        try:
            payload["lots"] = float(payload["lots"])
        except (ValueError, TypeError):
            pass  # leave as-is; will be stripped below if empty
    if "balance" in payload and payload["balance"] is not None:
        try:
            payload["balance"] = int(float(str(payload["balance"])))
        except (ValueError, TypeError):
            pass

    # Strip empty/falsy optional fields so SageMaster doesn't try to process
    # them (e.g., empty takeProfits:[] causes "Invalid S/L or T/P" rejection).
    # Core fields (type, assistId/aiAssistId, source, symbol, date) are never
    # stripped — they're always required.
    _OPTIONAL_FIELDS = {
        "price", "balance", "lots",
        "takeProfits", "takeProfitsPips", "stopLoss", "stopLossPips",
        "take_profits", "stop_loss",
        "position_type", "is_market", "order_price",
        "lotSize", "percentage", "slAdjustment", "sl_adjustment",
    }
    payload = {
        k: v for k, v in payload.items()
        if k not in _OPTIONAL_FIELDS or (v != "" and v != [] and v is not None)
    }

    # Safety: warn if TP/SL appear to be on the wrong side of entry price.
    # Only for non-crypto forex (absolute prices). Crypto may use percentages.
    if not is_crypto and signal.entry_price is not None:
        _ep = signal.entry_price
        if signal.stop_loss is not None:
            if signal.direction == "long" and signal.stop_loss > _ep:
                logger.warning(
                    "SL (%s) is above entry (%s) for a LONG %s — possible error",
                    signal.stop_loss, _ep, signal.symbol,
                )
            elif signal.direction == "short" and signal.stop_loss < _ep:
                logger.warning(
                    "SL (%s) is below entry (%s) for a SHORT %s — possible error",
                    signal.stop_loss, _ep, signal.symbol,
                )
        for tp in signal.take_profits:
            if signal.direction == "long" and tp < _ep:
                logger.warning(
                    "TP (%s) is below entry (%s) for a LONG %s — possible error",
                    tp, _ep, signal.symbol,
                )
            elif signal.direction == "short" and tp > _ep:
                logger.warning(
                    "TP (%s) is above entry (%s) for a SHORT %s — possible error",
                    tp, _ep, signal.symbol,
                )

    return payload


# ---------------------------------------------------------------------------
# Tier limit check
# ---------------------------------------------------------------------------

def check_template_symbol_mismatch(
    signal: ParsedSignal, rule: RoutingRule
) -> str | None:
    """Return a reason string if the signal symbol doesn't match the template's
    hardcoded symbol.  Returns ``None`` if no mismatch (OK to dispatch).

    A symbol is considered "hardcoded" when it is a non-empty string that does
    not contain a ``{{…}}`` placeholder.  Empty strings and placeholders like
    ``{{ticker}}`` are treated as dynamic and never cause a mismatch.

    For crypto destinations, ``tradeSymbol`` is skipped because single-pair
    DCA assists always have a fixed trade pair (e.g. ``BTC/USDT``) regardless
    of which signal triggered them.  Only ``eventSymbol`` is checked for crypto.
    """
    if not rule.webhook_body_template:
        return None
    is_crypto = rule.destination_type == "sagemaster_crypto"
    for field in ("symbol", "tradeSymbol", "eventSymbol"):
        # Crypto DCA assists have a fixed tradeSymbol — skip mismatch check
        if is_crypto and field == "tradeSymbol":
            continue
        value = rule.webhook_body_template.get(field)
        if isinstance(value, str) and value and "{{" not in value:
            if value != signal.symbol:
                return (
                    f"Signal symbol '{signal.symbol}' does not match "
                    f"template {field} '{value}'"
                )
    return None


# ---------------------------------------------------------------------------
# Asset class compatibility
# ---------------------------------------------------------------------------

# Which asset classes each SageMaster destination type can handle.
# "custom" is absent — no restriction for user-controlled webhooks.
_DESTINATION_ASSET_CLASSES: dict[str, set[str]] = {
    "sagemaster_forex": {"forex", "commodities", "indices"},
    "sagemaster_crypto": {"crypto"},
}


def check_asset_class_mismatch(
    signal: ParsedSignal, rule: RoutingRule,
) -> str | None:
    """Return a reason string if the signal's asset class is incompatible
    with the destination type.  Returns ``None`` if OK to dispatch.

    For example, a commodities signal (XAUUSD) should not be sent to a
    ``sagemaster_crypto`` destination because the crypto platform cannot
    trade forex/commodity instruments.
    """
    allowed = _DESTINATION_ASSET_CLASSES.get(rule.destination_type)
    if allowed is None:
        return None  # custom destinations accept everything
    if signal.source_asset_class not in allowed:
        return (
            f"Signal asset class '{signal.source_asset_class}' "
            f"is not supported by {rule.destination_type} destinations"
        )
    return None


def check_tier_limit(tier: SubscriptionTier, current_count: int) -> bool:
    """Return ``True`` if *current_count* is below the tier's destination cap.

    This is used before creating a new routing rule to enforce the user's
    subscription limits.
    """
    return current_count < tier.max_destinations
