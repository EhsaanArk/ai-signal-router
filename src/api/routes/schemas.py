"""Pydantic request/response schemas for /api/v1 endpoints."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# --- Auth -------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """User registration payload."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    terms_accepted: bool = Field(False, description="User must accept ToS and Privacy Policy")


class LoginRequest(BaseModel):
    """JSON login alternative to OAuth2 form data."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: UUID
    email: str
    subscription_tier: str
    is_admin: bool = False
    email_verified: bool = False
    created_at: str
    accepted_tos_version: str | None = None
    accepted_risk_waiver: bool = False


class LoginResponse(BaseModel):
    """Login response with token + user profile — eliminates extra /auth/me round-trip."""
    access_token: str
    token_type: str = "bearer"
    user: UserMeResponse
    email_sent: bool = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class DeleteAccountRequest(BaseModel):
    current_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class AcceptTermsRequest(BaseModel):
    tos_accepted: bool = False
    privacy_accepted: bool = False
    risk_waiver_accepted: bool = False


# --- Telegram ---------------------------------------------------------------

class SendCodeRequest(BaseModel):
    phone_number: str


class SendCodeResponse(BaseModel):
    phone_code_hash: str


class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str
    phone_code_hash: str
    password: str | None = None


class VerifyCodeResponse(BaseModel):
    status: str = "ok"
    requires_2fa: bool = False


class TelegramStatusResponse(BaseModel):
    connected: bool
    phone_number: str | None = None
    connected_at: str | None = None
    disconnected_at: str | None = None
    disconnected_reason: str | None = None
    last_signal_at: str | None = None


# --- Channels ---------------------------------------------------------------

class ChannelInfo(BaseModel):
    id: str
    title: str
    username: str | None = None


# --- Routing Rules ----------------------------------------------------------

class TestWebhookRequest(BaseModel):
    url: str


class TestWebhookResponse(BaseModel):
    success: bool
    status_code: int | None = None
    error: str | None = None


class RoutingRuleUpdate(BaseModel):
    source_channel_name: str | None = None
    destination_webhook_url: str | None = None
    payload_version: Literal["V1", "V2"] | None = None
    symbol_mappings: dict[str, str] | None = None
    risk_overrides: dict[str, Any] | None = None
    webhook_body_template: dict[str, Any] | None = None
    rule_name: str | None = None
    destination_label: str | None = None
    destination_type: Literal["sagemaster_forex", "sagemaster_crypto", "custom"] | None = None
    custom_ai_instructions: str | None = None
    enabled_actions: list[str] | None = None
    keyword_blacklist: list[str] | None = None
    is_active: bool | None = None


class RoutingRuleCreate(BaseModel):
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


class RoutingRuleResponse(BaseModel):
    id: UUID
    user_id: UUID
    source_channel_id: str
    source_channel_name: str | None
    destination_webhook_url: str
    payload_version: str
    symbol_mappings: dict[str, str]
    risk_overrides: dict[str, Any]
    webhook_body_template: dict[str, Any] | None
    rule_name: str | None = None
    destination_label: str | None = None
    destination_type: str = "sagemaster_forex"
    custom_ai_instructions: str | None = None
    enabled_actions: list[str] | None = None
    keyword_blacklist: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


# --- Logs -------------------------------------------------------------------

class SignalLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    routing_rule_id: UUID | None
    raw_message: str
    parsed_data: dict | None
    webhook_payload: dict | None
    status: str
    error_message: str | None
    processed_at: str
    message_id: int | None = None
    channel_id: str | None = None
    reply_to_msg_id: int | None = None


class PaginatedLogs(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[SignalLogResponse]


class LogStatsResponse(BaseModel):
    total: int
    success: int
    failed: int
    ignored: int


# --- Notifications ----------------------------------------------------------

class NotificationPreferencesResponse(BaseModel):
    email_on_success: bool = False
    email_on_failure: bool = True
    telegram_on_success: bool = False
    telegram_on_failure: bool = False
    telegram_bot_chat_id: int | None = None


class NotificationPreferencesUpdate(BaseModel):
    email_on_success: bool | None = None
    email_on_failure: bool | None = None
    telegram_on_success: bool | None = None
    telegram_on_failure: bool | None = None


# --- Telegram Bot -----------------------------------------------------------

class TelegramBotLinkResponse(BaseModel):
    bot_link: str


class TelegramBotUpdate(BaseModel):
    """Minimal Telegram Bot update payload for /start command."""
    update_id: int
    message: dict | None = None


# --- Parse Preview ----------------------------------------------------------

class ParsePreviewRequest(BaseModel):
    """Request body for the parse-preview sandbox."""
    message: str = Field(..., min_length=1, max_length=2000)
    destination_type: str = "sagemaster_forex"
    enabled_actions: list[str] | None = Field(default=None, max_length=20)


class ParsePreviewResponse(BaseModel):
    """Stripped parser result — never exposes system prompt or internals."""
    is_valid_signal: bool
    action: str | None = None
    symbol: str | None = None
    direction: str | None = None
    order_type: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profits: list[float] = Field(default_factory=list)
    percentage: int | None = None
    ignore_reason: str | None = None
    # Enhanced fields for forwarding verdict
    display_action_label: str | None = None
    route_would_forward: bool | None = None
    blocked_reason: str | None = None
