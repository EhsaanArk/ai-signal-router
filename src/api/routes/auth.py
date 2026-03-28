"""Auth endpoints — register, login, password reset, email verification, etc."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import sentry_sdk

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
    _get_real_ip,
    create_access_token,
    get_current_user,
    get_db,
    get_settings,
    limiter,
)
from src.core.constants import CURRENT_TOS_VERSION, LEGACY_TOKEN_SCAN_LIMIT
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    InputValidationError,
)
from src.core.models import User
from src.core.security import sha256_hex

from src.api.routes.schemas import (
    AcceptTermsRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserMeResponse,
    VerifyEmailRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_LEGACY_TOKEN_SCAN_LIMIT = LEGACY_TOKEN_SCAN_LIMIT


def _build_verification_email_html(verify_link: str, welcome_line: str = "") -> str:
    """Build styled HTML for email verification with a clickable button and fallback URL."""
    intro = f"<p>{welcome_line}</p>" if welcome_line else ""
    return (
        '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
        'max-width:480px;margin:0 auto;padding:20px">'
        f"{intro}"
        "<p>Please verify your email address by clicking the button below:</p>"
        f'<p style="text-align:center;margin:24px 0"><a href="{verify_link}" target="_blank" '
        'style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;'
        'border-radius:6px;text-decoration:none;font-weight:600">Verify Email</a></p>'
        '<p style="font-size:13px;color:#666">Or copy and paste this link into your browser:</p>'
        f'<p style="font-size:12px;word-break:break-all;color:#2563eb">{verify_link}</p>'
        '<p style="font-size:13px;color:#666">This link expires in 24 hours.</p>'
        "</body></html>"
    )


def _user_me_from_row(row: UserModel) -> UserMeResponse:
    """Build a UserMeResponse from a DB row — DRY helper for login, register, and /me."""
    return UserMeResponse(
        id=row.id,
        email=row.email,
        subscription_tier=row.subscription_tier,
        is_admin=getattr(row, "is_admin", False),
        email_verified=getattr(row, "email_verified", False),
        created_at=row.created_at.isoformat() if row.created_at else "",
        accepted_tos_version=getattr(row, "accepted_tos_version", None),
        accepted_risk_waiver=getattr(row, "accepted_risk_waiver", False),
    )


async def _find_valid_token_row(
    db: AsyncSession,
    token_model: type[PasswordResetTokenModel] | type[EmailVerificationTokenModel],
    raw_token: str,
) -> tuple[PasswordResetTokenModel | EmailVerificationTokenModel | None, bool]:
    """Resolve token via lookup hash with deterministic legacy fallback.

    Returns (matched_row_or_None, was_verified_by_bcrypt). When the token is
    found via the SHA-256 lookup hash the match is deterministic and no
    additional bcrypt verify is needed at the call site.
    """
    now = datetime.now(timezone.utc)
    token_lookup_hash = sha256_hex(raw_token)
    result = await db.execute(
        select(token_model).where(
            token_model.token_lookup_hash == token_lookup_hash,
            token_model.expires_at > now,
            token_model.used_at.is_(None),
        ).limit(1)
    )
    matched_token = result.scalar_one_or_none()
    if matched_token is not None:
        # SHA-256 is a deterministic match — no bcrypt needed.
        return matched_token, True

    # Backward compatibility for legacy rows created before token_lookup_hash.
    legacy_rows = (
        await db.execute(
            select(token_model).where(
                token_model.token_lookup_hash.is_(None),
                token_model.expires_at > now,
                token_model.used_at.is_(None),
            )
            .order_by(token_model.created_at.desc())
            .limit(_LEGACY_TOKEN_SCAN_LIMIT)
        )
    ).scalars().all()
    for row in legacy_rows:
        if pwd_context.verify(raw_token, row.token_hash):
            return row, True
    return None, False


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

    # Reject if no user, no hash, or hash is a placeholder (Supabase-only users
    # have "!" as a placeholder — they must login via Supabase, not this endpoint).
    if user_row is None or not user_row.password_hash or not user_row.password_hash.startswith("$2b$"):
        raise AuthenticationError("Incorrect email or password")
    if not pwd_context.verify(form_data.password, user_row.password_hash):
        raise AuthenticationError("Incorrect email or password")

    if getattr(user_row, "is_disabled", False):
        raise AuthorizationError("Account is disabled")

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
        select(UserModel).where(UserModel.email == str(body.email).lower())
    )
    user_row = result.scalar_one_or_none()

    if user_row is None or not user_row.password_hash or not user_row.password_hash.startswith("$2b$"):
        raise AuthenticationError("Incorrect email or password")
    if not pwd_context.verify(body.password, user_row.password_hash):
        raise AuthenticationError("Incorrect email or password")

    if getattr(user_row, "is_disabled", False):
        raise AuthorizationError("Account is disabled")

    token = create_access_token(
        data={"sub": str(user_row.id)}, settings=settings
    )
    return LoginResponse(
        access_token=token,
        user=_user_me_from_row(user_row),
    )


@router.post("/auth/accept-terms", response_model=MessageResponse)
@limiter.limit("5/minute")
async def accept_terms(
    request: Request,
    body: AcceptTermsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Record terms/privacy/risk waiver acceptance with full audit trail."""
    from src.adapters.db.models import TermsAcceptanceLogModel

    if not body.tos_accepted or not body.privacy_accepted or not body.risk_waiver_accepted:
        raise InputValidationError("You must accept the Terms of Service, Privacy Policy, and Risk Waiver")

    # Extract audit data (uses trusted proxy validation for accurate IP)
    ip = _get_real_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")

    # Log each document acceptance
    for doc_type in ["tos", "privacy", "risk_waiver"]:
        db.add(TermsAcceptanceLogModel(
            user_id=current_user.id,
            document_type=doc_type,
            document_version=CURRENT_TOS_VERSION,
            ip_address=ip,
            user_agent=user_agent,
        ))

    # Update user record
    result = await db.execute(
        select(UserModel).where(UserModel.id == current_user.id)
    )
    user_row = result.scalar_one()
    user_row.accepted_tos_version = CURRENT_TOS_VERSION
    user_row.accepted_risk_waiver = True
    user_row.terms_accepted_at = datetime.now(timezone.utc)

    await db.flush()

    # Bust user cache (non-fatal — cache expires in 5min anyway)
    try:
        cache = request.app.state.cache
        await cache.delete(f"user:{current_user.id}")
    except Exception:
        logger.debug("Cache bust failed for user %s after terms acceptance", current_user.id)

    logger.info("Terms accepted by user %s (v%s, IP: %s)", current_user.id, CURRENT_TOS_VERSION, ip)
    return MessageResponse(message="Terms accepted successfully")


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
    # Require terms acceptance
    if not body.terms_accepted:
        raise InputValidationError("You must accept the Terms of Service and Privacy Policy")

    # Check email uniqueness (case-insensitive)
    normalised_email = str(body.email).lower()
    result = await db.execute(
        select(UserModel).where(UserModel.email == normalised_email)
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictError("A user with this email already exists")

    hashed = pwd_context.hash(body.password)
    new_user = UserModel(
        email=normalised_email,
        password_hash=hashed,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    await db.flush()

    # Send email verification
    raw_verify_token = secrets.token_urlsafe(32)
    verify_token_hash = pwd_context.hash(raw_verify_token)
    db.add(EmailVerificationTokenModel(
        user_id=new_user.id,
        token_hash=verify_token_hash,
        token_lookup_hash=sha256_hex(raw_verify_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db.flush()

    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_verify_token}"
    email_sent = False
    if settings.RESEND_API_KEY:
        notifier = request.app.state.notifier
        try:
            await notifier.send_raw_email(
                to=str(body.email),
                subject="Verify your email",
                html=_build_verification_email_html(
                    verify_link, "Welcome to Sage Radar AI!"
                ),
            )
            email_sent = True
        except Exception as exc:
            logger.exception("Failed to send verification email")
            sentry_sdk.capture_exception(exc)
        # Send welcome email (separate from verification)
        try:
            await notifier.send_welcome(str(body.email), settings.FRONTEND_URL)
        except Exception as exc:
            logger.error("Welcome email failed (non-blocking): %s", exc)
            sentry_sdk.capture_exception(exc)
    else:
        logger.warning("RESEND_API_KEY not set — verification email not sent")

    token = create_access_token(
        data={"sub": str(new_user.id)}, settings=settings
    )
    return LoginResponse(
        access_token=token,
        user=_user_me_from_row(new_user),
        email_sent=email_sent,
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
        select(UserModel).where(UserModel.email == str(body.email).lower())
    )
    user_row = result.scalar_one_or_none()

    if user_row is not None:
        raw_token = secrets.token_urlsafe(32)
        token_hash = pwd_context.hash(raw_token)

        reset_token = PasswordResetTokenModel(
            user_id=user_row.id,
            token_hash=token_hash,
            token_lookup_hash=sha256_hex(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset_token)
        await db.flush()

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

        if settings.RESEND_API_KEY:
            try:
                notifier = request.app.state.notifier
                await notifier.send_raw_email(
                    to=body.email,
                    subject="Reset your password",
                    html=(
                        "<p>Click the link below to reset your password. "
                        "This link expires in 1 hour.</p>"
                        f'<p><a href="{reset_link}">Reset Password</a></p>'
                    ),
                )
            except Exception as exc:
                logger.exception("Failed to send password reset email")
                sentry_sdk.capture_exception(exc)
        else:
            logger.warning("RESEND_API_KEY not set — password reset email not sent")

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
    matched_token, _verified = await _find_valid_token_row(
        db=db,
        token_model=PasswordResetTokenModel,
        raw_token=body.token,
    )

    if matched_token is None:
        raise InputValidationError("Invalid or expired reset token")

    # Update user password
    user_result = await db.execute(
        select(UserModel).where(UserModel.id == matched_token.user_id)
    )
    user_row = user_result.scalar_one()
    user_row.password_hash = pwd_context.hash(body.new_password)

    # Mark token as used
    matched_token.used_at = datetime.now(timezone.utc)

    return MessageResponse(message="Password has been reset successfully.")


@router.post("/auth/verify-email", response_model=MessageResponse)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Verify a user's email using the token from the verification link."""
    matched_token, _verified = await _find_valid_token_row(
        db=db,
        token_model=EmailVerificationTokenModel,
        raw_token=body.token,
    )

    if matched_token is None:
        raise InputValidationError("Invalid or expired verification token")

    # Mark user as verified
    user_result = await db.execute(
        select(UserModel).where(UserModel.id == matched_token.user_id)
    )
    user_row = user_result.scalar_one()
    user_row.email_verified = True

    # Mark token as used
    matched_token.used_at = datetime.now(timezone.utc)

    # Bust user cache so the verified status is reflected immediately
    cache = request.app.state.cache
    await cache.delete(f"user:{matched_token.user_id}")

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
        token_lookup_hash=sha256_hex(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db.flush()

    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    if settings.RESEND_API_KEY:
        try:
            notifier = request.app.state.notifier
            await notifier.send_raw_email(
                to=current_user.email,
                subject="Verify your email",
                html=_build_verification_email_html(verify_link),
            )
        except Exception as exc:
            logger.exception("Failed to send verification email")
            sentry_sdk.capture_exception(exc)
            raise ExternalServiceError("Failed to send verification email. Please try again later.")
    else:
        logger.warning("RESEND_API_KEY not set — verification email not sent")
        raise ExternalServiceError("Email service is not configured. Please contact support.")

    return MessageResponse(message="Verification email sent.")


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

    if not user_row.password_hash or user_row.password_hash == "!":
        raise InputValidationError("Password changes are managed through your sign-in provider (Google or Magic Link). Use Forgot Password to set a new password.")

    if not pwd_context.verify(body.current_password, user_row.password_hash):
        raise AuthenticationError("Current password is incorrect")

    if len(body.new_password) < 8:
        raise InputValidationError("New password must be at least 8 characters")

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

    if not user_row.password_hash or user_row.password_hash == "!":
        raise InputValidationError("Account deletion for OAuth users is not yet supported. Contact support@sagemaster.com.")

    if not pwd_context.verify(body.current_password, user_row.password_hash):
        raise AuthenticationError("Password is incorrect")

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
            "id": str(log.id),
            "raw_message": log.raw_message,
            "parsed_data": log.parsed_data,
            "webhook_payload": log.webhook_payload,
            "status": log.status,
            "error_message": log.error_message,
            "processed_at": log.processed_at.isoformat() if log.processed_at else None,
        }
        for log in logs_result.scalars().all()
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
