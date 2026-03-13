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

from src.core.models import (
    ParsedSignal,
    RoutingRule,
    SignalAction,
    SubscriptionTier,
    WebhookPayloadV1,
    WebhookPayloadV2,
)


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

def _signal_action(direction: str) -> SignalAction:
    """Map a ``ParsedSignal.direction`` to the corresponding ``SignalAction``."""
    if direction == "long":
        return SignalAction.start_long
    elif direction == "short":
        return SignalAction.start_short
    raise ValueError(f"Unsupported direction: {direction}")


def build_webhook_payload(
    signal: ParsedSignal, rule: RoutingRule
) -> WebhookPayloadV1 | WebhookPayloadV2:
    """Construct a validated V1 or V2 webhook payload model.

    Parameters
    ----------
    signal:
        The parsed (and optionally symbol-mapped) signal.
    rule:
        The routing rule whose ``payload_version`` and
        ``destination_webhook_url`` determine payload shape and asset ID.

    Returns
    -------
    WebhookPayloadV1 | WebhookPayloadV2
        A validated Pydantic model.  Call ``.model_dump()`` to serialise.
    """
    asset_id = extract_asset_id(rule.destination_webhook_url)
    action = _signal_action(signal.direction)

    if rule.payload_version == "V2":
        return WebhookPayloadV2(
            type=action,
            assetId=asset_id,
            source=signal.source_asset_class,
            symbol=signal.symbol,
            price=str(signal.entry_price) if signal.entry_price is not None else None,
            takeProfits=signal.take_profits or None,
            stopLoss=signal.stop_loss,
        )

    return WebhookPayloadV1(
        type=action.value,
        assetId=asset_id,
        source=signal.source_asset_class,
        symbol=signal.symbol,
        date=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Tier limit check
# ---------------------------------------------------------------------------

def check_tier_limit(tier: SubscriptionTier, current_count: int) -> bool:
    """Return ``True`` if *current_count* is below the tier's destination cap.

    This is used before creating a new routing rule to enforce the user's
    subscription limits.
    """
    return current_count < tier.max_destinations
