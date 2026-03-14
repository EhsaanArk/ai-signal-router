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
            SubscriptionTier.free: 1,
            SubscriptionTier.starter: 2,
            SubscriptionTier.pro: 5,
            SubscriptionTier.elite: 15,
        }[self]


# ---------------------------------------------------------------------------
# Signal action types (webhook `type` field values)
# ---------------------------------------------------------------------------

class SignalAction(str, Enum):
    """Webhook action types supported by the SageMaster API."""

    start_long = "start_long_market_deal"
    start_short = "start_short_market_deal"
    partial_close_lot = "partially_close_by_lot"
    partial_close_pct = "partially_close_by_percentage"
    breakeven = "move_sl_to_breakeven"
    close_position = "close_order_at_market_price"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(BaseModel):
    """Application user."""

    id: UUID = Field(default_factory=uuid4)
    email: str
    password_hash: str
    subscription_tier: SubscriptionTier = SubscriptionTier.free
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
        "modify_sl", "modify_tp", "trailing_sl",
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
    lotSize: str | None = None


class WebhookPayloadV2(BaseModel):
    """SageMaster V2 webhook payload — supports trade signals and provider commands."""

    type: SignalAction
    assistId: str
    source: str | None = None
    symbol: str | None = None
    price: str | None = None
    takeProfits: list[float] | None = None
    stopLoss: float | None = None
    lots: str | None = None
    # Management action fields
    slAdjustment: int | None = None
    percentage: int | None = None
    lotSize: str | None = None

    @model_validator(mode="after")
    def _check_required_fields_per_action(self) -> Self:
        """Enforce field requirements based on action type."""
        if self.type in (SignalAction.start_long, SignalAction.start_short):
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
