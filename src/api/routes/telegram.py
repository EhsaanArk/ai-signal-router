"""Telegram endpoints — auth flow, status, disconnect, channels, bot webhook, bot link."""

import asyncio
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import sentry_sdk

from src.adapters.db.models import (
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.api.deps import (
    Settings,
    get_cache,
    get_current_user,
    get_db,
    get_session_store,
    get_settings,
)
from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    InputValidationError,
)
from src.core.models import User

from src.api.routes.schemas import (
    ChannelInfo,
    MessageResponse,
    SendCodeRequest,
    SendCodeResponse,
    TelegramBotLinkResponse,
    TelegramBotUpdate,
    TelegramStatusResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

_BOT_LINK_PURPOSE = "telegram_bot_link"
_BOT_LINK_EXP_MINUTES = 30


# ============================================================================
# Telegram auth singleton
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


# ============================================================================
# Telegram auth endpoints
# ============================================================================


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
        raise InputValidationError("Invalid phone number format.")
    except FloodWaitError as exc:
        raise InputValidationError(f"Rate limited by Telegram. Retry after {exc.seconds} seconds.")
    except Exception:
        logger.exception("Telegram send_code failed")
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("Telegram service unavailable. Please try again later.")
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
        raise InputValidationError(str(exc))
    except PhoneCodeInvalidError:
        raise InputValidationError("Invalid verification code.")
    except PhoneCodeExpiredError:
        raise InputValidationError("Verification code has expired. Please request a new one.")
    except FloodWaitError as exc:
        raise InputValidationError(f"Rate limited by Telegram. Retry after {exc.seconds} seconds.")
    except Exception:
        logger.exception("Telegram verify_code failed")
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("Telegram verification failed. Please try again.")

    # Encrypt the session string before storing
    from src.core.security import encrypt_session

    if not settings.ENCRYPTION_KEY:
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("ENCRYPTION_KEY not configured")
    try:
        encrypted = encrypt_session(session_string, settings.ENCRYPTION_KEY.encode())
    except Exception:
        logger.exception("Failed to encrypt Telegram session")
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("Failed to encrypt session. Check ENCRYPTION_KEY configuration.")

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
        raise ConflictError("This phone number is already connected to another account.")

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

    # Send "Telegram connected" milestone email (non-blocking)
    if settings.RESEND_API_KEY:
        try:
            from src.adapters.email import ResendNotifier
            notifier = ResendNotifier(api_key=settings.RESEND_API_KEY)
            await notifier.send_telegram_connected(
                current_user.email, settings.FRONTEND_URL,
            )
        except Exception as exc:
            logger.error("Telegram connected email failed (non-blocking): %s", exc)
            sentry_sdk.capture_exception(exc)

    return VerifyCodeResponse(status="ok")


@router.get("/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> TelegramStatusResponse:
    """Check whether the current user has an active Telegram session."""
    # Check cache first (10s TTL — matches frontend refetch interval)
    cache_key = f"tg_status:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached:
        return TelegramStatusResponse(**json.loads(cached))

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

    # Attach last signal timestamp for pipeline health visibility
    last_signal = (
        await db.execute(
            select(SignalLogModel.processed_at)
            .where(SignalLogModel.user_id == current_user.id)
            .order_by(SignalLogModel.processed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_signal:
        response.last_signal_at = last_signal.isoformat()

    # Cache for 10s (matches frontend refetch interval)
    await cache.set(cache_key, response.model_dump_json(), ttl_seconds=10)
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
        raise InputValidationError("No active Telegram session found.")

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


async def _deactivate_stale_session(
    db: AsyncSession,
    session_store,
    cache,
    user_id,
) -> None:
    """Mark a user's Telegram session as inactive when Telegram rejects it.

    This keeps the DB in sync with reality so ``/telegram/status`` stops
    reporting *connected* for a session that no longer works.
    """
    result = await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.user_id == user_id,
            TelegramSessionModel.is_active.is_(True),
        )
    )
    for session in result.scalars().all():
        session.is_active = False
        session.disconnected_reason = "session_expired"
        session.disconnected_at = datetime.now(timezone.utc)
    await db.commit()

    # Clear caches so status endpoint reflects the change immediately
    try:
        await session_store.delete_session(user_id)
    except Exception:
        pass
    try:
        await cache.delete(f"tg_status:{user_id}")
    except Exception:
        pass
    logger.info("Auto-deactivated stale Telegram session for user %s", user_id)


@router.get("/channels", response_model=list[ChannelInfo])
async def list_channels(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    session_store=Depends(get_session_store),
    cache=Depends(get_cache),
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
            raise InputValidationError("No active Telegram session. Please connect Telegram first.")
        session_encrypted = session_row.session_string_encrypted

    # Decrypt
    from src.core.security import decrypt_session_auto

    if not settings.ENCRYPTION_KEY:
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("ENCRYPTION_KEY not configured")
    try:
        session_string = decrypt_session_auto(session_encrypted, settings.ENCRYPTION_KEY.encode())
    except Exception:
        logger.exception("Failed to decrypt Telegram session for user %s", current_user.id)
        await _deactivate_stale_session(db, session_store, cache, current_user.id)
        raise InputValidationError("Telegram session is corrupted. Please reconnect your Telegram account.")

    # Fetch channels via adapter
    import os
    from src.adapters.telegram import get_user_channels, parse_proxy_url
    from telethon.errors import FloodWaitError

    proxy_url = os.environ.get("TELEGRAM_PROXY_URL")
    proxy = parse_proxy_url(proxy_url)
    logger.info(
        "Fetching channels for user %s (proxy=%s)",
        current_user.id,
        "configured" if proxy else "none",
    )

    try:
        raw_channels = await get_user_channels(
            session_string=session_string,
            api_id=settings.TELEGRAM_API_ID,
            api_hash=settings.TELEGRAM_API_HASH,
            proxy=proxy,
        )
    except FloodWaitError as exc:
        raise InputValidationError(f"Rate limited by Telegram. Retry after {exc.seconds} seconds.")
    except RuntimeError as exc:
        logger.warning(
            "Telegram session expired for user %s: %s", current_user.id, exc
        )
        # Auto-deactivate the stale session so the frontend reflects reality
        await _deactivate_stale_session(db, session_store, cache, current_user.id)
        raise AuthenticationError("Telegram session has expired. Please reconnect your Telegram account.")
    except Exception:
        logger.exception("Failed to fetch Telegram channels for user %s", current_user.id)
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("Failed to fetch channels from Telegram. Please try again.")

    logger.info(
        "Fetched %d channels for user %s", len(raw_channels), current_user.id
    )
    return [
        ChannelInfo(id=ch["channel_id"], title=ch["channel_name"], username=ch.get("username"))
        for ch in raw_channels
    ]


# ============================================================================
# Telegram Bot Notifications
# ============================================================================


def _create_telegram_bot_link_token(user_id: UUID, settings: Settings) -> str:
    """Create a signed short-lived token for Telegram bot linking."""
    if not settings.TELEGRAM_BOT_LINK_SECRET:
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("Telegram bot link signing is not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "purpose": _BOT_LINK_PURPOSE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_BOT_LINK_EXP_MINUTES)).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.TELEGRAM_BOT_LINK_SECRET,
        algorithm="HS256",
    )


def _decode_telegram_bot_link_token(token: str, settings: Settings) -> UUID | None:
    """Decode and validate a Telegram bot link token."""
    if not settings.TELEGRAM_BOT_LINK_SECRET:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.TELEGRAM_BOT_LINK_SECRET,
            algorithms=["HS256"],
            options={"require": ["sub", "purpose", "iat", "exp"]},
        )
        if payload.get("purpose") != _BOT_LINK_PURPOSE:
            return None
        return UUID(str(payload["sub"]))
    except (InvalidTokenError, ValueError, TypeError):
        return None


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
        from src.core.exceptions import ExternalServiceError
        raise ExternalServiceError("Telegram bot notifications are not configured")
    token = _create_telegram_bot_link_token(current_user.id, settings)
    bot_username = await _resolve_bot_username(settings.TELEGRAM_BOT_TOKEN)
    return TelegramBotLinkResponse(
        bot_link=f"https://t.me/{bot_username}?start={token}",
    )


@router.post("/webhook/telegram-bot")
async def telegram_bot_webhook(
    request: Request,
    body: TelegramBotUpdate,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Receive Telegram bot updates.

    When a user sends ``/start <token>``, decode the token to find the user
    and store their ``chat_id`` in notification preferences.
    """
    message = body.message
    if not message:
        return {"ok": True}

    if not settings.LOCAL_MODE:
        required_secret = settings.TELEGRAM_BOT_WEBHOOK_SECRET
        if not required_secret:
            logger.error("Telegram bot webhook secret not configured in production mode")
            from src.core.exceptions import ExternalServiceError
            raise ExternalServiceError("Telegram bot webhook secret is not configured")
        provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not provided_secret or not hmac.compare_digest(provided_secret, required_secret):
            raise AuthenticationError("Invalid Telegram webhook secret")

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not text.startswith("/start ") or not chat_id:
        return {"ok": True}

    token_part = text.split(" ", 1)[1].strip()

    user_id = _decode_telegram_bot_link_token(token_part, settings)
    if user_id is None:
        logger.warning("Invalid /start token received for Telegram bot webhook")
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
