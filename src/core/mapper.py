"""Signal mapping and webhook payload construction.

Pure domain logic — no infrastructure imports.  Responsible for:

* Applying per-rule symbol mappings (e.g. "GOLD" -> "XAUUSD").
* Building SageMaster V1 / V2 webhook payloads.
* Enforcing subscription-tier destination limits.
* Extracting the asset-id UUID from a SageMaster webhook URL.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.core.models import ParsedSignal, RoutingRule, SubscriptionTier


# ---------------------------------------------------------------------------
# UUID regex used to extract asset IDs from webhook URLs
# ---------------------------------------------------------------------------
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def extract_asset_id(webhook_url: str) -> str:
    """Extract the UUID asset-id from a SageMaster webhook URL.

    SageMaster webhook URLs end with a UUID that identifies the destination
    trading account asset.  For example::

        https://app.sagemaster.com/api/webhook/ea1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d

    Parameters
    ----------
    webhook_url:
        The full webhook URL.

    Returns
    -------
    str
        The extracted UUID string.

    Raises
    ------
    ValueError
        If no UUID is found in the URL.
    """
    matches = _UUID_RE.findall(webhook_url)
    if not matches:
        raise ValueError(
            f"Could not extract asset ID (UUID) from webhook URL: {webhook_url}"
        )
    # The last UUID in the URL is the asset ID
    return matches[-1]


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

def _deal_type(direction: str, order_type: str) -> str:
    """Build the SageMaster ``type`` field string.

    Examples: ``start_long_market_deal``, ``start_short_limit_deal``.
    """
    return f"start_{direction}_{order_type}_deal"


def build_webhook_payload(signal: ParsedSignal, rule: RoutingRule) -> dict:
    """Construct a V1 or V2 webhook payload dictionary.

    Parameters
    ----------
    signal:
        The parsed (and optionally symbol-mapped) signal.
    rule:
        The routing rule whose ``payload_version`` and
        ``destination_webhook_url`` determine payload shape and asset ID.

    Returns
    -------
    dict
        A JSON-serialisable dictionary ready to POST to SageMaster.
    """
    asset_id = extract_asset_id(rule.destination_webhook_url)
    deal_type = _deal_type(signal.direction, signal.order_type)
    now_iso = datetime.now(timezone.utc).isoformat()

    payload: dict = {
        "type": deal_type,
        "assetId": asset_id,
        "source": signal.source_asset_class,
        "symbol": signal.symbol,
        "date": now_iso,
    }

    if rule.payload_version == "V2":
        if signal.entry_price is not None:
            payload["price"] = str(signal.entry_price)
        if signal.take_profits:
            payload["takeProfits"] = signal.take_profits
        if signal.stop_loss is not None:
            payload["stopLoss"] = signal.stop_loss

    return payload


# ---------------------------------------------------------------------------
# Tier limit check
# ---------------------------------------------------------------------------

def check_tier_limit(tier: SubscriptionTier, current_count: int) -> bool:
    """Return ``True`` if *current_count* is below the tier's destination cap.

    This is used before creating a new routing rule to enforce the user's
    subscription limits.
    """
    return current_count < tier.max_destinations
