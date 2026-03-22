"""Core domain models for the SGM Telegram Signal Copier.

All models are pure Pydantic — no infrastructure imports (no SQLAlchemy, no
FastAPI, no third-party DB/queue libraries).  These models define the ubiquitous
language shared across every layer of the application.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Subscription tier
# ---------------------------------------------------------------------------

class SubscriptionTier(str, Enum):
    """Available subscription tiers with destination-count limits."""

    free = "free"
    starter = "starter"
    pro = "pro"
    elite = "elite"

    @property
    def max_destinations(self) -> int:
        """Return the maximum number of webhook destinations for this tier."""
        return {
            SubscriptionTier.free: 5,
            SubscriptionTier.starter: 2,
            SubscriptionTier.pro: 5,
            SubscriptionTier.elite: 15,
        }[self]


# ---------------------------------------------------------------------------
# Signal action types (webhook `type` field values)
# ---------------------------------------------------------------------------

class SignalAction(str, Enum):
    """Webhook action types supported by the SageMaster API (forex)."""

    start_long = "start_long_market_deal"
    start_short = "start_short_market_deal"
    start_long_limit = "start_long_limit_deal"
    start_short_limit = "start_short_limit_deal"
    partial_close_lot = "partially_close_by_lot"
    partial_close_pct = "partially_close_by_percentage"
    breakeven = "move_sl_to_breakeven"
    close_position = "close_order_at_market_price"
    close_all = "close_all_orders_at_market_price"
    close_all_stop = "close_all_orders_at_market_price_and_stop_assist"
    start_assist = "start_assist"
    stop_assist = "stop_assist"
    extra_order = "open_extra_order"  # crypto only


REQUIRED_ENTRY_ACTION_VALUES: tuple[str, ...] = (
    SignalAction.start_long.value,
    SignalAction.start_short.value,
    SignalAction.start_long_limit.value,
    SignalAction.start_short_limit.value,
)


def normalize_enabled_actions(enabled_actions: list[str] | None) -> list[str] | None:
    """Ensure required entry actions are always present while preserving order."""
    if enabled_actions is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for action in enabled_actions:
        if action not in seen:
            normalized.append(action)
            seen.add(action)

    for required in REQUIRED_ENTRY_ACTION_VALUES:
        if required not in seen:
            normalized.append(required)
            seen.add(required)

    return normalized


# Crypto action type strings — differ from forex per SageMaster DCA UI.
# Crypto uses "deals" and "ai_assist" instead of forex "orders" and "assist".
# Crypto does not support lot-based partial close; both lot and pct map to percentage.
CRYPTO_ACTION_TYPE: dict[str, str] = {
    "start_deal": "start_deal",  # crypto uses single type for long/short
    "close_position": "close_order_at_market_price",
    "close_all": "close_all_deals_at_market_price",
    "close_all_stop": "close_all_deals_at_market_price_and_stop_ai_assist",
    "start_assist": "start_ai_assist_and_deal",
    "stop_assist": "stop_ai_assist",
    "partial_close_lot": "partially_closed_by_percentage",  # no lot support
    "partial_close_pct": "partially_closed_by_percentage",
    "breakeven": "moved_sl_adjustment",
    "extra_order": "open_extra_order",
}


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(BaseModel):
    """Application user."""

    id: UUID = Field(default_factory=uuid4)
    email: str
    password_hash: str
    subscription_tier: SubscriptionTier = SubscriptionTier.free
    is_admin: bool = False
    is_disabled: bool = False
    email_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Signal models
# ---------------------------------------------------------------------------

class RawSignal(BaseModel):
    """An unprocessed signal message captured from a Telegram channel."""

    user_id: UUID
    channel_id: str
    raw_message: str
    message_id: int
    reply_to_msg_id: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ParsedSignal(BaseModel):
    """A signal after GPT-based parsing and normalisation."""

    action: Literal[
        "entry", "partial_close", "breakeven", "close_position",
        "modify_sl", "modify_tp", "trailing_sl", "extra_order",
        "close_all", "close_all_stop", "start_assist", "stop_assist",
    ] = "entry"
    symbol: str
    direction: Literal["long", "short"] = "long"
    order_type: Literal["market", "limit", "stop"] = "market"
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profits: list[float] = Field(default_factory=list)
    source_asset_class: str = "forex"
    is_valid_signal: bool = True
    ignore_reason: str | None = None
    lots: str | None = None
    percentage: int | None = None
    new_sl: float | None = None
    new_tp: float | None = None
    trailing_sl_pips: int | None = None
    breakeven_offset_pips: int | None = None
    take_profit_pips: list[int] = Field(default_factory=list)
    stop_loss_pips: int | None = None
    is_market: bool | None = None
    order_price: float | None = None


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

class RoutingRule(BaseModel):
    """Maps a Telegram source channel to a SageMaster webhook destination."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    source_channel_id: str
    source_channel_name: str | None = None
    destination_webhook_url: str
    payload_version: Literal["V1", "V2"] = "V1"
    symbol_mappings: dict[str, str] = Field(default_factory=dict)
    risk_overrides: dict[str, Any] = Field(default_factory=dict)
    webhook_body_template: dict[str, Any] | None = None
    rule_name: str | None = None
    destination_label: str | None = None
    destination_type: Literal["sagemaster_forex", "sagemaster_crypto", "custom"] = "sagemaster_forex"
    custom_ai_instructions: str | None = None
    enabled_actions: list[str] | None = None
    keyword_blacklist: list[str] = Field(default_factory=list)
    is_active: bool = True


# ---------------------------------------------------------------------------
# Webhook payloads
# ---------------------------------------------------------------------------

class WebhookPayloadV1(BaseModel):
    """SageMaster V1 webhook payload (static strategy trigger).

    Supports both entry actions and trade management actions.
    """

    type: str
    assistId: str
    source: str
    symbol: str
    date: str
    # Management action fields
    slAdjustment: int | None = None
    percentage: int | None = None
    lotSize: float | None = None


class WebhookPayloadV2(BaseModel):
    """SageMaster V2 webhook payload — supports trade signals and provider commands."""

    type: SignalAction
    assistId: str
    source: str | None = None
    symbol: str | None = None
    price: str | None = None
    takeProfits: list[float] | None = None
    takeProfitsPips: list[int] | None = None
    stopLoss: float | None = None
    stopLossPips: int | None = None
    balance: int | None = None
    lots: float | None = None
    # Management action fields
    slAdjustment: int | None = None
    percentage: int | None = None
    lotSize: float | None = None

    @model_validator(mode="after")
    def _check_required_fields_per_action(self) -> Self:
        """Enforce field requirements based on action type."""
        entry_actions = (
            SignalAction.start_long, SignalAction.start_short,
            SignalAction.start_long_limit, SignalAction.start_short_limit,
        )
        if self.type in entry_actions:
            if not self.symbol or not self.source:
                raise ValueError(
                    f"'symbol' and 'source' are required for {self.type.value}"
                )
        if self.type == SignalAction.partial_close_lot and not self.lots:
            raise ValueError("'lots' is required for partially_close_by_lot")
        if self.type == SignalAction.partial_close_pct and self.percentage is None:
            raise ValueError("'percentage' is required for partially_close_by_percentage")
        return self


# ---------------------------------------------------------------------------
# Dispatch result
# ---------------------------------------------------------------------------

class DispatchResult(BaseModel):
    """Outcome of dispatching a parsed signal through a routing rule."""

    routing_rule_id: UUID | None = None
    status: Literal["success", "failed", "ignored"]
    error_message: str | None = None
    webhook_payload: dict | None = None
    attempt_count: int = 1
