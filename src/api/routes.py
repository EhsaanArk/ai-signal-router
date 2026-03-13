"""Public API router — /api/v1 endpoints for the SGM Telegram Signal Copier."""

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
    PasswordResetTokenModel,
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.api.deps import (
    Settings,
    create_access_token,
    get_current_user,
    get_db,
    get_settings,
    limiter,
)
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
    created_at: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


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


# --- Channels ---------------------------------------------------------------

class ChannelInfo(BaseModel):
    id: str
    title: str
    username: str | None = None


# --- Routing Rules ----------------------------------------------------------

class RoutingRuleUpdate(BaseModel):
    source_channel_name: str | None = None
    destination_webhook_url: str | None = None
    payload_version: Literal["V1", "V2"] | None = None
    symbol_mappings: dict[str, str] | None = None
    risk_overrides: dict[str, Any] | None = None
    is_active: bool | None = None


class RoutingRuleCreate(BaseModel):
    source_channel_id: str
    source_channel_name: str | None = None
    destination_webhook_url: str
    payload_version: Literal["V1", "V2"] = "V1"
    symbol_mappings: dict[str, str] = Field(default_factory=dict)
    risk_overrides: dict[str, Any] = Field(default_factory=dict)


class RoutingRuleResponse(BaseModel):
    id: UUID
    user_id: UUID
    source_channel_id: str
    source_channel_name: str | None
    destination_webhook_url: str
    payload_version: str
    symbol_mappings: dict[str, str]
    risk_overrides: dict[str, Any]
    is_active: bool


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
        select(UserModel).where(UserModel.email == form_data.username)
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

    token = create_access_token(
        data={"sub": str(user_row.id)}, settings=settings
    )
    return TokenResponse(access_token=token)


@router.post("/auth/login-json", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_json(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """JSON-based login endpoint (convenience wrapper around the form login)."""
    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email)
    )
    user_row = result.scalar_one_or_none()

    if user_row is None or not pwd_context.verify(
        body.password, user_row.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(
        data={"sub": str(user_row.id)}, settings=settings
    )
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=UserMeResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserMeResponse:
    """Return the current authenticated user's profile."""
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        subscription_tier=current_user.subscription_tier.value,
        created_at=current_user.created_at.isoformat(),
    )


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Register a new user and return a JWT."""
    # Check email uniqueness
    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    hashed = pwd_context.hash(body.password)
    new_user = UserModel(email=body.email, password_hash=hashed)
    db.add(new_user)
    await db.flush()

    token = create_access_token(
        data={"sub": str(new_user.id)}, settings=settings
    )
    return TokenResponse(access_token=token)


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
        select(UserModel).where(UserModel.email == body.email)
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
                resend.Emails.send(
                    {
                        "from": "SageMaster <noreply@sagemaster.io>",
                        "to": [body.email],
                        "subject": "Reset your password",
                        "html": (
                            f"<p>Click the link below to reset your password. "
                            f"This link expires in 1 hour.</p>"
                            f'<p><a href="{reset_link}">Reset Password</a></p>'
                        ),
                    }
                )
            except Exception:
                logger.exception("Failed to send password reset email")
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


# ============================================================================
# Telegram endpoints
# ============================================================================

_telegram_auth_instance: "TelegramAuth | None" = None


def _get_telegram_auth(settings: Settings) -> "TelegramAuth":
    """Return a shared TelegramAuth singleton so pending clients persist across requests."""
    global _telegram_auth_instance
    if _telegram_auth_instance is None:
        from src.adapters.telegram import TelegramAuth

        _telegram_auth_instance = TelegramAuth(
            api_id=settings.TELEGRAM_API_ID,
            api_hash=settings.TELEGRAM_API_HASH,
        )
    return _telegram_auth_instance


@router.post("/telegram/send-code", response_model=SendCodeResponse)
async def telegram_send_code(
    body: SendCodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SendCodeResponse:
    """Send a Telegram verification code to the given phone number."""
    auth = _get_telegram_auth(settings)
    result = await auth.send_code(body.phone_number)
    return SendCodeResponse(phone_code_hash=result["phone_code_hash"])


@router.post("/telegram/verify-code", response_model=VerifyCodeResponse)
async def telegram_verify_code(
    body: VerifyCodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerifyCodeResponse:
    """Verify the Telegram code and persist the encrypted session string."""
    from telethon.errors import SessionPasswordNeededError

    auth = _get_telegram_auth(settings)
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
        raise

    # Encrypt the session string before storing
    from cryptography.fernet import Fernet

    if not settings.ENCRYPTION_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY not configured",
        )
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted = fernet.encrypt(session_string.encode()).decode()

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
    else:
        db.add(
            TelegramSessionModel(
                user_id=current_user.id,
                phone_number=body.phone_number,
                session_string_encrypted=encrypted,
                is_active=True,
            )
        )

    # Cache session in Redis for fast lookup by the listener
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.set(
            f"tg_session:{current_user.id}",
            encrypted,
            ex=86400 * 30,  # 30-day TTL
        )
        await r.aclose()
    except Exception:
        logger.warning("Failed to cache session in Redis — continuing without cache")

    return VerifyCodeResponse(status="ok")


@router.get("/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramStatusResponse:
    """Check whether the current user has an active Telegram session."""
    result = await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.user_id == current_user.id,
            TelegramSessionModel.is_active.is_(True),
        )
    )
    session = result.scalar_one_or_none()
    return TelegramStatusResponse(connected=session is not None)


# ============================================================================
# Channels
# ============================================================================


@router.get("/channels", response_model=list[ChannelInfo])
async def list_channels(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ChannelInfo]:
    """List Telegram channels the user is subscribed to."""
    # Retrieve session string: try Redis first, fall back to DB
    session_encrypted: str | None = None

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        cached = await r.get(f"tg_session:{current_user.id}")
        await r.aclose()
        if cached:
            session_encrypted = cached if isinstance(cached, str) else cached.decode()
    except Exception:
        logger.debug("Redis lookup failed, falling back to DB")

    if session_encrypted is None:
        result = await db.execute(
            select(TelegramSessionModel).where(
                TelegramSessionModel.user_id == current_user.id,
                TelegramSessionModel.is_active.is_(True),
            )
        )
        session_row = result.scalar_one_or_none()
        if session_row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active Telegram session. Please connect Telegram first.",
            )
        session_encrypted = session_row.session_string_encrypted

    # Decrypt
    from cryptography.fernet import Fernet

    if not settings.ENCRYPTION_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY not configured",
        )
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    session_string = fernet.decrypt(session_encrypted.encode()).decode()

    # Fetch channels via adapter
    from src.adapters.telegram import get_user_channels

    raw_channels = await get_user_channels(
        session_string=session_string,
        api_id=settings.TELEGRAM_API_ID,
        api_hash=settings.TELEGRAM_API_HASH,
    )
    return [
        ChannelInfo(id=ch["channel_id"], title=ch["channel_name"], username=ch.get("username"))
        for ch in raw_channels
    ]


# ============================================================================
# Routing Rules
# ============================================================================


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
                f"{tier.max_destinations} routing rule(s). "
                "Please upgrade to add more."
            ),
        )


@router.get("/routing-rules", response_model=list[RoutingRuleResponse])
async def list_routing_rules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RoutingRuleResponse]:
    """Return all routing rules belonging to the current user."""
    result = await db.execute(
        select(RoutingRuleModel)
        .where(RoutingRuleModel.user_id == current_user.id)
        .order_by(RoutingRuleModel.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        RoutingRuleResponse(
            id=r.id,
            user_id=r.user_id,
            source_channel_id=r.source_channel_id,
            source_channel_name=r.source_channel_name,
            destination_webhook_url=r.destination_webhook_url,
            payload_version=r.payload_version,
            symbol_mappings=r.symbol_mappings or {},
            risk_overrides=r.risk_overrides or {},
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.post(
    "/routing-rules",
    response_model=RoutingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_routing_rule(
    body: RoutingRuleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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

    new_rule = RoutingRuleModel(
        user_id=current_user.id,
        source_channel_id=body.source_channel_id,
        source_channel_name=body.source_channel_name,
        destination_webhook_url=body.destination_webhook_url,
        payload_version=body.payload_version,
        symbol_mappings=body.symbol_mappings,
        risk_overrides=body.risk_overrides,
        is_active=True,
    )
    db.add(new_rule)
    await db.flush()  # populate default values (id, timestamps)

    return RoutingRuleResponse(
        id=new_rule.id,
        user_id=new_rule.user_id,
        source_channel_id=new_rule.source_channel_id,
        source_channel_name=new_rule.source_channel_name,
        destination_webhook_url=new_rule.destination_webhook_url,
        payload_version=new_rule.payload_version,
        symbol_mappings=new_rule.symbol_mappings or {},
        risk_overrides=new_rule.risk_overrides or {},
        is_active=new_rule.is_active,
    )


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
    return RoutingRuleResponse(
        id=row.id,
        user_id=row.user_id,
        source_channel_id=row.source_channel_id,
        source_channel_name=row.source_channel_name,
        destination_webhook_url=row.destination_webhook_url,
        payload_version=row.payload_version,
        symbol_mappings=row.symbol_mappings or {},
        risk_overrides=row.risk_overrides or {},
        is_active=row.is_active,
    )


@router.put("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def update_routing_rule(
    rule_id: UUID,
    body: RoutingRuleUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
    for field, value in update_data.items():
        setattr(row, field, value)
    await db.flush()

    return RoutingRuleResponse(
        id=row.id,
        user_id=row.user_id,
        source_channel_id=row.source_channel_id,
        source_channel_name=row.source_channel_name,
        destination_webhook_url=row.destination_webhook_url,
        payload_version=row.payload_version,
        symbol_mappings=row.symbol_mappings or {},
        risk_overrides=row.risk_overrides or {},
        is_active=row.is_active,
    )


@router.delete(
    "/routing-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_routing_rule(
    rule_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
) -> PaginatedLogs:
    """Return paginated signal logs for the current user."""
    # Base filter
    base_filter = [SignalLogModel.user_id == current_user.id]
    if status_filter and status_filter != "all":
        base_filter.append(SignalLogModel.status == status_filter)

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
        )
        for r in rows
    ]

    return PaginatedLogs(total=total, limit=limit, offset=offset, items=items)
