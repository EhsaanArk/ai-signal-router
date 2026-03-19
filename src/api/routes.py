"""Public API router — /api/v1 endpoints for the SGM Telegram Signal Copier."""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import (
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.api.deps import (
    Settings,
    create_access_token,
    get_cache,
    get_current_user,
    get_db,
    get_session_store,
    get_settings,
    limiter,
)
import sentry_sdk

from src.core.models import RoutingRule, SubscriptionTier, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================================================
# Request / Response schemas
# ============================================================================


# --- Auth -------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """User registration payload."""
    email: str
    password: str


class LoginRequest(BaseModel):
    """JSON login alternative to OAuth2 form data."""
    email: str
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


class LoginResponse(BaseModel):
    """Login response with token + user profile — eliminates extra /auth/me round-trip."""
    access_token: str
    token_type: str = "bearer"
    user: UserMeResponse


def _user_me_from_row(row: UserModel) -> UserMeResponse:
    """Build a UserMeResponse from a DB row — DRY helper for login, register, and /me."""
    return UserMeResponse(
        id=row.id,
        email=row.email,
        subscription_tier=row.subscription_tier,
        is_admin=getattr(row, "is_admin", False),
        email_verified=getattr(row, "email_verified", False),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


class DeleteAccountRequest(BaseModel):
    current_password: str


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


# ============================================================================
# Auth endpoints
# ============================================================================


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Authenticate via email + password and return a JWT.

    Accepts standard OAuth2 form data (``username`` field = email).
    """
    result = await db.execute(
        select(UserModel).where(UserModel.email == form_data.username.lower())
    )
    user_row = result.scalar_one_or_none()

    if user_row is None or not pwd_context.verify(
        form_data.password, user_row.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if getattr(user_row, "is_disabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(
        data={"sub": str(user_row.id)}, settings=settings
    )
    return TokenResponse(access_token=token)


@router.post("/auth/login-json", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login_json(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """JSON-based login — returns token + user profile to avoid extra /auth/me round-trip."""
    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email.lower())
    )
    user_row = result.scalar_one_or_none()

    if user_row is None or not pwd_context.verify(
        body.password, user_row.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if getattr(user_row, "is_disabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(
        data={"sub": str(user_row.id)}, settings=settings
    )
    return LoginResponse(
        access_token=token,
        user=_user_me_from_row(user_row),
    )


@router.get("/auth/me", response_model=UserMeResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserMeResponse:
    """Return the current authenticated user's profile."""
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        subscription_tier=current_user.subscription_tier.value,
        is_admin=current_user.is_admin,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


@router.post(
    "/auth/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """Register a new user and return a JWT."""
    # Check email uniqueness (case-insensitive)
    normalised_email = body.email.lower()
    result = await db.execute(
        select(UserModel).where(UserModel.email == normalised_email)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    hashed = pwd_context.hash(body.password)
    new_user = UserModel(email=normalised_email, password_hash=hashed)
    db.add(new_user)
    await db.flush()

    # Send email verification
    raw_verify_token = secrets.token_urlsafe(32)
    verify_token_hash = pwd_context.hash(raw_verify_token)
    db.add(EmailVerificationTokenModel(
        user_id=new_user.id,
        token_hash=verify_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db.flush()

    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_verify_token}"
    if settings.RESEND_API_KEY:
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            await asyncio.to_thread(resend.Emails.send, {
                "from": "Sage Radar AI <noreply@radar.sagemaster.com>",
                "to": [body.email],
                "subject": "Verify your email",
                "html": (
                    "<p>Welcome to Sage Radar AI! Please verify your email address "
                    "by clicking the link below.</p>"
                    f'<p><a href="{verify_link}">Verify Email</a></p>'
                    "<p>This link expires in 24 hours.</p>"
                ),
            })
        except Exception as exc:
            logger.exception("Failed to send verification email")
            sentry_sdk.capture_exception(exc)
    else:
        logger.warning("RESEND_API_KEY not set — verify link: %s", verify_link)

    token = create_access_token(
        data={"sub": str(new_user.id)}, settings=settings
    )
    return LoginResponse(
        access_token=token,
        user=_user_me_from_row(new_user),
    )


@router.post("/auth/forgot-password", response_model=MessageResponse)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    """Send a password reset link if the email exists. Always returns 200."""
    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email.lower())
    )
    user_row = result.scalar_one_or_none()

    if user_row is not None:
        raw_token = secrets.token_urlsafe(32)
        token_hash = pwd_context.hash(raw_token)

        reset_token = PasswordResetTokenModel(
            user_id=user_row.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset_token)
        await db.flush()

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

        if settings.RESEND_API_KEY:
            try:
                import resend

                resend.api_key = settings.RESEND_API_KEY
                await asyncio.to_thread(resend.Emails.send, {
                    "from": "Sage Radar AI <noreply@radar.sagemaster.com>",
                    "to": [body.email],
                    "subject": "Reset your password",
                    "html": (
                        "<p>Click the link below to reset your password. "
                        "This link expires in 1 hour.</p>"
                        f'<p><a href="{reset_link}">Reset Password</a></p>'
                    ),
                })
            except Exception as exc:
                logger.exception("Failed to send password reset email")
                sentry_sdk.capture_exception(exc)
        else:
            logger.warning(
                "RESEND_API_KEY not set — reset link: %s", reset_link
            )

    return MessageResponse(
        message="If an account exists, a reset link has been sent."
    )


@router.post("/auth/reset-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Reset password using a valid token."""
    result = await db.execute(
        select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.expires_at > datetime.now(timezone.utc),
            PasswordResetTokenModel.used_at.is_(None),
        )
    )
    token_rows = result.scalars().all()

    matched_token: PasswordResetTokenModel | None = None
    for row in token_rows:
        if pwd_context.verify(body.token, row.token_hash):
            matched_token = row
            break

    if matched_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Update user password
    user_result = await db.execute(
        select(UserModel).where(UserModel.id == matched_token.user_id)
    )
    user_row = user_result.scalar_one()
    user_row.password_hash = pwd_context.hash(body.new_password)

    # Mark token as used
    matched_token.used_at = datetime.now(timezone.utc)

    return MessageResponse(message="Password has been reset successfully.")


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/auth/verify-email", response_model=MessageResponse)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Verify a user's email using the token from the verification link."""
    result = await db.execute(
        select(EmailVerificationTokenModel).where(
            EmailVerificationTokenModel.expires_at > datetime.now(timezone.utc),
            EmailVerificationTokenModel.used_at.is_(None),
        )
    )
    token_rows = result.scalars().all()

    matched_token: EmailVerificationTokenModel | None = None
    for row in token_rows:
        if pwd_context.verify(body.token, row.token_hash):
            matched_token = row
            break

    if matched_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Mark user as verified
    user_result = await db.execute(
        select(UserModel).where(UserModel.id == matched_token.user_id)
    )
    user_row = user_result.scalar_one()
    user_row.email_verified = True

    # Mark token as used
    matched_token.used_at = datetime.now(timezone.utc)

    return MessageResponse(message="Email verified successfully.")


@router.post("/auth/resend-verification", response_model=MessageResponse)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    """Resend the verification email for the current user."""
    if current_user.email_verified:
        return MessageResponse(message="Email is already verified.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = pwd_context.hash(raw_token)
    db.add(EmailVerificationTokenModel(
        user_id=current_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db.flush()

    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    if settings.RESEND_API_KEY:
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            await asyncio.to_thread(resend.Emails.send, {
                "from": "Sage Radar AI <noreply@radar.sagemaster.com>",
                "to": [current_user.email],
                "subject": "Verify your email",
                "html": (
                    "<p>Please verify your email address by clicking the link below.</p>"
                    f'<p><a href="{verify_link}">Verify Email</a></p>'
                    "<p>This link expires in 24 hours.</p>"
                ),
            })
        except Exception as exc:
            logger.exception("Failed to send verification email")
            sentry_sdk.capture_exception(exc)
    else:
        logger.warning("RESEND_API_KEY not set — verify link: %s", verify_link)

    return MessageResponse(message="Verification email sent.")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Change password for the authenticated user."""
    result = await db.execute(
        select(UserModel).where(UserModel.id == current_user.id)
    )
    user_row = result.scalar_one()

    if not pwd_context.verify(body.current_password, user_row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    user_row.password_hash = pwd_context.hash(body.new_password)
    return MessageResponse(message="Password changed successfully.")


@router.post("/auth/account/delete", response_model=MessageResponse)
@limiter.limit("3/minute")
async def delete_account(
    request: Request,
    body: DeleteAccountRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Permanently delete the authenticated user's account and all data."""
    result = await db.execute(
        select(UserModel).where(UserModel.id == current_user.id)
    )
    user_row = result.scalar_one()

    if not pwd_context.verify(body.current_password, user_row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    await db.delete(user_row)
    logger.info("User %s deleted their account", current_user.id)
    return MessageResponse(message="Account deleted successfully.")


@router.get("/auth/account/export")
@limiter.limit("3/minute")
async def export_account_data(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Export all user data as JSON for GDPR compliance."""
    # Profile
    profile = {
        "email": current_user.email,
        "subscription_tier": current_user.subscription_tier,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }

    # Routing rules
    rules_result = await db.execute(
        select(RoutingRuleModel)
        .where(RoutingRuleModel.user_id == current_user.id)
        .order_by(RoutingRuleModel.created_at.desc())
    )
    rules = [
        {
            "id": str(r.id),
            "source_channel_id": r.source_channel_id,
            "source_channel_name": r.source_channel_name,
            "destination_webhook_url": r.destination_webhook_url,
            "destination_type": r.destination_type,
            "rule_name": r.rule_name,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules_result.scalars().all()
    ]

    # Signal logs (capped at 10,000)
    logs_result = await db.execute(
        select(SignalLogModel)
        .where(SignalLogModel.user_id == current_user.id)
        .order_by(SignalLogModel.processed_at.desc())
        .limit(10_000)
    )
    logs = [
        {
            "id": str(l.id),
            "raw_message": l.raw_message,
            "parsed_data": l.parsed_data,
            "webhook_payload": l.webhook_payload,
            "status": l.status,
            "error_message": l.error_message,
            "processed_at": l.processed_at.isoformat() if l.processed_at else None,
        }
        for l in logs_result.scalars().all()
    ]

    # Telegram session metadata (not the encrypted session itself)
    tg_result = await db.execute(
        select(TelegramSessionModel)
        .where(TelegramSessionModel.user_id == current_user.id)
    )
    tg_row = tg_result.scalar_one_or_none()
    telegram = {
        "connected": tg_row is not None and tg_row.is_active,
        "phone_number": tg_row.phone_number if tg_row else None,
    }

    return {
        "profile": profile,
        "routing_rules": rules,
        "signal_logs": logs,
        "telegram": telegram,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Telegram endpoints
# ============================================================================

_telegram_auth_instance: "TelegramAuth | None" = None
_telegram_auth_lock = asyncio.Lock()


async def _get_telegram_auth(settings: Settings) -> "TelegramAuth":
    """Return a shared TelegramAuth singleton so pending clients persist across requests."""
    global _telegram_auth_instance
    async with _telegram_auth_lock:
        if _telegram_auth_instance is None:
            import os
            from src.adapters.telegram import TelegramAuth, parse_proxy_url

            _telegram_auth_instance = TelegramAuth(
                api_id=settings.TELEGRAM_API_ID,
                api_hash=settings.TELEGRAM_API_HASH,
                proxy=parse_proxy_url(os.environ.get("TELEGRAM_PROXY_URL")),
            )
    return _telegram_auth_instance


@router.post("/telegram/send-code", response_model=SendCodeResponse)
async def telegram_send_code(
    body: SendCodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SendCodeResponse:
    """Send a Telegram verification code to the given phone number."""
    from telethon.errors import FloodWaitError, PhoneNumberInvalidError

    auth = await _get_telegram_auth(settings)
    try:
        result = await auth.send_code(body.phone_number)
    except PhoneNumberInvalidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format.",
        )
    except FloodWaitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limited by Telegram. Retry after {exc.seconds} seconds.",
            headers={"Retry-After": str(exc.seconds)},
        )
    except Exception:
        logger.exception("Telegram send_code failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram service unavailable. Please try again later.",
        )
    return SendCodeResponse(phone_code_hash=result["phone_code_hash"])


@router.post("/telegram/verify-code", response_model=VerifyCodeResponse)
async def telegram_verify_code(
    body: VerifyCodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    session_store=Depends(get_session_store),
    cache=Depends(get_cache),
) -> VerifyCodeResponse:
    """Verify the Telegram code and persist the encrypted session string."""
    from telethon.errors import (
        FloodWaitError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        SessionPasswordNeededError,
    )

    auth = await _get_telegram_auth(settings)
    try:
        session_string = await auth.verify_code(
            phone_number=body.phone_number,
            code=body.code,
            phone_code_hash=body.phone_code_hash,
            password=body.password,
        )
    except (SessionPasswordNeededError, ValueError) as exc:
        if "password" in str(exc).lower() or isinstance(exc, SessionPasswordNeededError):
            return VerifyCodeResponse(status="2fa_required", requires_2fa=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except PhoneCodeInvalidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )
    except PhoneCodeExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one.",
        )
    except FloodWaitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limited by Telegram. Retry after {exc.seconds} seconds.",
            headers={"Retry-After": str(exc.seconds)},
        )
    except Exception:
        logger.exception("Telegram verify_code failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram verification failed. Please try again.",
        )

    # Encrypt the session string before storing
    from src.core.security import encrypt_session

    if not settings.ENCRYPTION_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY not configured",
        )
    try:
        encrypted = encrypt_session(session_string, settings.ENCRYPTION_KEY.encode())
    except Exception:
        logger.exception("Failed to encrypt Telegram session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt session. Check ENCRYPTION_KEY configuration.",
        )

    # Cross-user phone uniqueness check — prevent two different users from
    # connecting the same Telegram account (Telegram kills competing sessions).
    conflict = (await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.phone_number == body.phone_number,
            TelegramSessionModel.is_active.is_(True),
            TelegramSessionModel.user_id != current_user.id,
        ).limit(1)
    )).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already connected to another account.",
        )

    # Upsert the telegram session record
    result = await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.user_id == current_user.id,
            TelegramSessionModel.phone_number == body.phone_number,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.session_string_encrypted = encrypted
        existing.is_active = True
        existing.disconnected_reason = None
        existing.disconnected_at = None
    else:
        db.add(
            TelegramSessionModel(
                user_id=current_user.id,
                phone_number=body.phone_number,
                session_string_encrypted=encrypted,
                is_active=True,
            )
        )

    # Cache session for fast lookup by the listener
    try:
        await session_store.save_session(current_user.id, encrypted)
    except Exception:
        logger.warning("Failed to cache session — continuing without cache")

    # Invalidate telegram status cache
    await cache.delete(f"tg_status:{current_user.id}")

    return VerifyCodeResponse(status="ok")


@router.get("/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> TelegramStatusResponse:
    """Check whether the current user has an active Telegram session."""
    # Check cache first (30s TTL — matches frontend refetch interval)
    cache_key = f"tg_status:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached:
        import json as _json
        return TelegramStatusResponse(**_json.loads(cached))

    result = await db.execute(
        select(TelegramSessionModel)
        .where(
            TelegramSessionModel.user_id == current_user.id,
            TelegramSessionModel.is_active.is_(True),
        )
        .order_by(TelegramSessionModel.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is not None:
        response = TelegramStatusResponse(
            connected=True,
            phone_number=session.phone_number,
            connected_at=session.created_at.isoformat() if session.created_at else None,
        )
    else:
        # No active session — check for the most recent inactive session
        # to provide disconnection context to the frontend.
        result = await db.execute(
            select(TelegramSessionModel)
            .where(TelegramSessionModel.user_id == current_user.id)
            .order_by(TelegramSessionModel.updated_at.desc())
            .limit(1)
        )
        last_session = result.scalar_one_or_none()
        if last_session and last_session.disconnected_reason:
            response = TelegramStatusResponse(
                connected=False,
                phone_number=last_session.phone_number,
                disconnected_at=(
                    last_session.disconnected_at.isoformat()
                    if last_session.disconnected_at else None
                ),
                disconnected_reason=last_session.disconnected_reason,
            )
        else:
            response = TelegramStatusResponse(connected=False)

    # Cache for 30s (matches frontend refetch interval)
    await cache.set(cache_key, response.model_dump_json(), ttl_seconds=30)
    return response


@router.post("/telegram/disconnect", response_model=MessageResponse)
async def telegram_disconnect(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    session_store=Depends(get_session_store),
    cache=Depends(get_cache),
) -> MessageResponse:
    """Disconnect the user's Telegram account by deactivating all sessions."""
    result = await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.user_id == current_user.id,
            TelegramSessionModel.is_active.is_(True),
        )
    )
    sessions = result.scalars().all()
    if not sessions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Telegram session found.",
        )

    for session in sessions:
        session.is_active = False
        session.disconnected_reason = "user_disconnected"
        session.disconnected_at = datetime.now(timezone.utc)

    # Remove cached session and invalidate status cache
    try:
        await session_store.delete_session(current_user.id)
    except Exception:
        logger.warning("Failed to remove cached session")
    await cache.delete(f"tg_status:{current_user.id}")

    return MessageResponse(message="Telegram account disconnected successfully.")


# ============================================================================
# Channels
# ============================================================================


@router.get("/channels", response_model=list[ChannelInfo])
async def list_channels(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    session_store=Depends(get_session_store),
) -> list[ChannelInfo]:
    """List Telegram channels the user is subscribed to."""
    # Retrieve session string: try session store first, fall back to DB
    session_encrypted: str | None = None

    try:
        session_encrypted = await session_store.get_session(current_user.id)
    except Exception:
        logger.debug("Session store lookup failed, falling back to DB")

    if session_encrypted is None:
        result = await db.execute(
            select(TelegramSessionModel)
            .where(
                TelegramSessionModel.user_id == current_user.id,
                TelegramSessionModel.is_active.is_(True),
            )
            .order_by(TelegramSessionModel.created_at.desc())
            .limit(1)
        )
        session_row = result.scalar_one_or_none()
        if session_row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active Telegram session. Please connect Telegram first.",
            )
        session_encrypted = session_row.session_string_encrypted

    # Decrypt
    from src.core.security import decrypt_session_auto

    if not settings.ENCRYPTION_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY not configured",
        )
    try:
        session_string = decrypt_session_auto(session_encrypted, settings.ENCRYPTION_KEY.encode())
    except Exception:
        logger.exception("Failed to decrypt Telegram session for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram session is corrupted or invalid. Please disconnect and reconnect.",
        )

    # Fetch channels via adapter
    import os
    from src.adapters.telegram import get_user_channels, parse_proxy_url
    from telethon.errors import FloodWaitError

    try:
        raw_channels = await get_user_channels(
            session_string=session_string,
            api_id=settings.TELEGRAM_API_ID,
            api_hash=settings.TELEGRAM_API_HASH,
            proxy=parse_proxy_url(os.environ.get("TELEGRAM_PROXY_URL")),
        )
    except FloodWaitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limited by Telegram. Retry after {exc.seconds} seconds.",
            headers={"Retry-After": str(exc.seconds)},
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram session has expired. Please reconnect.",
        )
    except Exception:
        logger.exception("Failed to fetch Telegram channels for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch channels from Telegram. Please try again.",
        )
    return [
        ChannelInfo(id=ch["channel_id"], title=ch["channel_name"], username=ch.get("username"))
        for ch in raw_channels
    ]


# ============================================================================
# Routing Rules
# ============================================================================


def _rule_to_response(r: RoutingRuleModel) -> "RoutingRuleResponse":
    """Convert a RoutingRuleModel row to a RoutingRuleResponse."""
    return RoutingRuleResponse(
        id=r.id,
        user_id=r.user_id,
        source_channel_id=r.source_channel_id,
        source_channel_name=r.source_channel_name,
        destination_webhook_url=r.destination_webhook_url,
        payload_version=r.payload_version,
        symbol_mappings=r.symbol_mappings or {},
        risk_overrides=r.risk_overrides or {},
        webhook_body_template=r.webhook_body_template,
        rule_name=r.rule_name,
        destination_label=r.destination_label,
        destination_type=r.destination_type,
        custom_ai_instructions=r.custom_ai_instructions,
        enabled_actions=r.enabled_actions,
        keyword_blacklist=r.keyword_blacklist or [],
        is_active=r.is_active,
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


def _check_tier_limit(
    tier: SubscriptionTier,
    current_rule_count: int,
) -> None:
    """Raise 403 if the user has reached their destination limit."""
    if current_rule_count >= tier.max_destinations:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your {tier.value} plan allows up to "
                f"{tier.max_destinations} route(s). "
                "Please upgrade to add more."
            ),
        )


@router.get("/routing-rules", response_model=list[RoutingRuleResponse])
async def list_routing_rules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> list[RoutingRuleResponse]:
    """Return all routing rules belonging to the current user."""
    import json

    cache_key = f"rules:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return [RoutingRuleResponse(**r) for r in json.loads(cached)]

    result = await db.execute(
        select(RoutingRuleModel)
        .where(RoutingRuleModel.user_id == current_user.id)
        .order_by(RoutingRuleModel.created_at.desc())
    )
    rows = result.scalars().all()
    rules = [_rule_to_response(r) for r in rows]
    await cache.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in rules]),
        ttl_seconds=30,
    )
    return rules


@router.post(
    "/routing-rules",
    response_model=RoutingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_routing_rule(
    body: RoutingRuleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> RoutingRuleResponse:
    """Create a new routing rule after verifying the user's tier limit."""
    # Count existing active rules
    count_result = await db.execute(
        select(func.count())
        .select_from(RoutingRuleModel)
        .where(
            RoutingRuleModel.user_id == current_user.id,
            RoutingRuleModel.is_active.is_(True),
        )
    )
    current_count = count_result.scalar_one()

    _check_tier_limit(current_user.subscription_tier, current_count)

    # Template is required for SageMaster destinations (contains assistId)
    if body.destination_type in ("sagemaster_forex", "sagemaster_crypto") and not body.webhook_body_template:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Webhook body template is required for SageMaster destinations. "
                "Copy the JSON from your SageMaster Assists overview page > "
                "alert configuration in SageMaster."
            ),
        )

    new_rule = RoutingRuleModel(
        user_id=current_user.id,
        source_channel_id=body.source_channel_id,
        source_channel_name=body.source_channel_name,
        destination_webhook_url=body.destination_webhook_url,
        payload_version=body.payload_version,
        symbol_mappings=body.symbol_mappings,
        risk_overrides=body.risk_overrides,
        webhook_body_template=body.webhook_body_template,
        rule_name=body.rule_name,
        destination_label=body.destination_label,
        destination_type=body.destination_type,
        custom_ai_instructions=body.custom_ai_instructions,
        enabled_actions=body.enabled_actions,
        keyword_blacklist=body.keyword_blacklist,
        is_active=True,
    )
    db.add(new_rule)
    await db.flush()  # populate default values (id, timestamps)
    await cache.delete(f"rules:{current_user.id}")

    return _rule_to_response(new_rule)


@router.get("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def get_routing_rule(
    rule_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoutingRuleResponse:
    """Return a single routing rule by ID, scoped to the current user."""
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing rule not found")
    return _rule_to_response(row)


@router.put("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def update_routing_rule(
    rule_id: UUID,
    body: RoutingRuleUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> RoutingRuleResponse:
    """Update a routing rule by ID, scoped to the current user."""
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing rule not found")

    update_data = body.model_dump(exclude_unset=True)

    # Determine the effective destination_type and template after update
    effective_type = update_data.get("destination_type", row.destination_type)
    effective_template = update_data.get("webhook_body_template", row.webhook_body_template)
    if effective_type in ("sagemaster_forex", "sagemaster_crypto") and not effective_template:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Webhook body template is required for SageMaster destinations. "
                "Copy the JSON from your SageMaster Assists overview page > "
                "alert configuration in SageMaster."
            ),
        )

    for field, value in update_data.items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    await cache.delete(f"rules:{current_user.id}")

    return _rule_to_response(row)


@router.delete(
    "/routing-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_routing_rule(
    rule_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
):
    """Delete a routing rule by ID, scoped to the current user."""
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing rule not found")
    await db.delete(row)
    await cache.delete(f"rules:{current_user.id}")


@router.post("/webhook/test", response_model=TestWebhookResponse)
async def test_webhook(
    body: TestWebhookRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> TestWebhookResponse:
    """Send a test ping to a webhook URL to verify connectivity."""
    import httpx

    try:
        url = body.url
        # Validate URL format
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return TestWebhookResponse(
                success=False, error="URL must use http or https"
            )

        test_payload = {
            "type": "test",
            "source": "sagemaster-signal-copier",
            "message": "This is a test ping from SageMaster Signal Copier.",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=test_payload)
            return TestWebhookResponse(
                success=resp.status_code < 400,
                status_code=resp.status_code,
                error=None if resp.status_code < 400 else f"HTTP {resp.status_code}",
            )
    except httpx.TimeoutException:
        return TestWebhookResponse(success=False, error="Request timed out")
    except Exception as exc:
        return TestWebhookResponse(success=False, error=str(exc))


# ============================================================================
# Signal Logs
# ============================================================================


@router.get("/logs", response_model=PaginatedLogs)
async def list_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = Query(None, alias="status"),
    rule_id: UUID | None = Query(None),
) -> PaginatedLogs:
    """Return paginated signal logs for the current user."""
    # Base filter
    base_filter = [SignalLogModel.user_id == current_user.id]
    if status_filter and status_filter != "all":
        base_filter.append(SignalLogModel.status == status_filter)
    if rule_id:
        base_filter.append(SignalLogModel.routing_rule_id == rule_id)

    # Total count
    count_result = await db.execute(
        select(func.count())
        .select_from(SignalLogModel)
        .where(*base_filter)
    )
    total = count_result.scalar_one()

    # Fetch page
    result = await db.execute(
        select(SignalLogModel)
        .where(*base_filter)
        .order_by(SignalLogModel.processed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()

    items = [
        SignalLogResponse(
            id=r.id,
            user_id=r.user_id,
            routing_rule_id=r.routing_rule_id,
            raw_message=r.raw_message,
            parsed_data=r.parsed_data,
            webhook_payload=r.webhook_payload,
            status=r.status,
            error_message=r.error_message,
            processed_at=r.processed_at.isoformat() if r.processed_at else "",
            message_id=r.message_id,
            channel_id=r.channel_id,
            reply_to_msg_id=r.reply_to_msg_id,
        )
        for r in rows
    ]

    return PaginatedLogs(total=total, limit=limit, offset=offset, items=items)


class LogStatsResponse(BaseModel):
    total: int
    success: int
    failed: int
    ignored: int


@router.get("/logs/stats", response_model=LogStatsResponse)
async def log_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> LogStatsResponse:
    """Return signal log counts by status for the current user."""
    import json

    cache_key = f"log_stats:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return LogStatsResponse(**json.loads(cached))

    result = await db.execute(
        select(SignalLogModel.status, func.count())
        .where(SignalLogModel.user_id == current_user.id)
        .group_by(SignalLogModel.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())

    stats = LogStatsResponse(
        total=total,
        success=counts.get("success", 0),
        failed=counts.get("failed", 0),
        ignored=counts.get("ignored", 0),
    )
    await cache.set(cache_key, stats.model_dump_json(), ttl_seconds=15)
    return stats


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


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


@router.get("/settings/notifications", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferencesResponse:
    """Return the current user's notification preferences."""
    result = await db.execute(
        select(UserModel.notification_preferences).where(
            UserModel.id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none() or {}
    return NotificationPreferencesResponse(**prefs)


@router.put("/settings/notifications", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: NotificationPreferencesUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferencesResponse:
    """Update the current user's notification preferences."""
    result = await db.execute(
        select(UserModel).where(UserModel.id == current_user.id)
    )
    user_row = result.scalar_one()

    current_prefs = user_row.notification_preferences or {}
    updates = body.model_dump(exclude_none=True)
    current_prefs.update(updates)
    user_row.notification_preferences = current_prefs

    return NotificationPreferencesResponse(**current_prefs)


# ---------------------------------------------------------------------------
# Telegram Bot Notifications
# ---------------------------------------------------------------------------


class TelegramBotLinkResponse(BaseModel):
    bot_link: str


@router.get("/settings/telegram-bot-link", response_model=TelegramBotLinkResponse)
async def get_telegram_bot_link(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramBotLinkResponse:
    """Return a deep link to start the SGM notification bot.

    The link encodes the user's ID so the bot webhook can associate the
    Telegram ``chat_id`` with their account.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot notifications are not configured",
        )

    import base64

    token = base64.urlsafe_b64encode(str(current_user.id).encode()).decode().rstrip("=")
    bot_username = await _resolve_bot_username(settings.TELEGRAM_BOT_TOKEN)
    return TelegramBotLinkResponse(
        bot_link=f"https://t.me/{bot_username}?start={token}",
    )


async def _resolve_bot_username(bot_token: str) -> str:
    """Call getMe to resolve the bot's username (cached after first call)."""
    if not hasattr(_resolve_bot_username, "_cache"):
        _resolve_bot_username._cache = {}  # type: ignore[attr-defined]
    cache = _resolve_bot_username._cache  # type: ignore[attr-defined]
    if bot_token in cache:
        return cache[bot_token]

    import httpx

    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        data = resp.json()
        username = data.get("result", {}).get("username", "sgm_copier_bot")
        cache[bot_token] = username
        return username


class TelegramBotUpdate(BaseModel):
    """Minimal Telegram Bot update payload for /start command."""
    update_id: int
    message: dict | None = None


@router.post("/webhook/telegram-bot")
async def telegram_bot_webhook(
    body: TelegramBotUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Receive Telegram bot updates.

    When a user sends ``/start <token>``, decode the token to find the user
    and store their ``chat_id`` in notification preferences.
    """
    message = body.message
    if not message:
        return {"ok": True}

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not text.startswith("/start ") or not chat_id:
        return {"ok": True}

    token_part = text.split(" ", 1)[1].strip()

    import base64

    # Restore padding
    padded = token_part + "=" * (-len(token_part) % 4)
    try:
        user_id_str = base64.urlsafe_b64decode(padded).decode()
        user_id = UUID(user_id_str)
    except Exception:
        logger.warning("Invalid /start token: %s", token_part)
        return {"ok": True}

    result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user_row = result.scalar_one_or_none()
    if user_row is None:
        logger.warning("Telegram bot /start: user %s not found", user_id)
        return {"ok": True}

    prefs = user_row.notification_preferences or {}
    prefs["telegram_bot_chat_id"] = chat_id
    user_row.notification_preferences = prefs

    logger.info("Telegram bot linked for user %s, chat_id=%s", user_id, chat_id)
    return {"ok": True, "linked": True}
