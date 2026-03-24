"""Public API router — /api/v1 endpoints for the SGM Telegram Signal Copier.

This package splits the monolithic routes module into focused sub-modules.
The combined ``router`` exported here is a drop-in replacement for the
original single-file router.
"""

from fastapi import APIRouter

from src.api.routes.auth import router as auth_router
from src.api.routes.telegram import router as telegram_router
from src.api.routes.routing_rules import router as routing_rules_router
from src.api.routes.user import router as user_router

# Re-export key symbols that external code imports directly from
# ``src.api.routes`` (e.g. tests).
from src.api.routes.auth import (  # noqa: F401
    _build_verification_email_html,
    _find_valid_token_row,
    _user_me_from_row,
    pwd_context,
)
from src.api.routes.telegram import (  # noqa: F401
    _create_telegram_bot_link_token,
    _decode_telegram_bot_link_token,
)
from src.api.routes.routing_rules import (  # noqa: F401
    _check_tier_limit,
    _rule_to_response,
    parse_preview,
)
from src.api.routes.schemas import (  # noqa: F401
    AcceptTermsRequest,
    ChangePasswordRequest,
    ChannelInfo,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogStatsResponse,
    MessageResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    PaginatedLogs,
    ParsePreviewRequest,
    ParsePreviewResponse,
    RegisterRequest,
    ResetPasswordRequest,
    RoutingRuleCreate,
    RoutingRuleResponse,
    RoutingRuleUpdate,
    SendCodeRequest,
    SendCodeResponse,
    SignalLogResponse,
    TelegramBotLinkResponse,
    TelegramBotUpdate,
    TelegramStatusResponse,
    TestWebhookRequest,
    TestWebhookResponse,
    TokenResponse,
    UserMeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
    VerifyEmailRequest,
)

router = APIRouter()
router.include_router(auth_router)
router.include_router(telegram_router)
router.include_router(routing_rules_router)
router.include_router(user_router)
