"""Telegram endpoints — auth flow, status, disconnect, channels, bot webhook, bot link."""

import asyncio
import hmac
import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
import jwt
from jwt import InvalidTokenError
from sqlalchemy import BigInteger, cast, func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

import sentry_sdk

from src.adapters.db.models import (
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.adapters.openai import OpenAISignalParser
from src.adapters.telegram.notifier import TelegramNotifier, _escape_md
from src.adapters.webhook import WebhookDispatcher
from src.api.deps import (
    Settings,
    get_cache,
    get_current_user,
    get_db,
    get_dispatcher,
    get_session_store,
    get_settings,
)
from src.api.workflow import _get_parser_config, _process_single_rule
from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    ExternalServiceError,
    InputValidationError,
)
from src.core.models import (
    DispatchResult,
    ParsedSignal,
    RawSignal,
    RoutingRule,
    User,
    normalize_enabled_actions,
)

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
        raise ExternalServiceError("Telegram service unavailable. Please try again later.")
    return SendCodeResponse(phone_code_hash=result["phone_code_hash"])


@router.post("/telegram/verify-code", response_model=VerifyCodeResponse)
async def telegram_verify_code(
    request: Request,
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
        raise ExternalServiceError("Telegram verification failed. Please try again.")

    # Encrypt the session string before storing
    from src.core.security import encrypt_session

    if not settings.ENCRYPTION_KEY:
        raise ExternalServiceError("ENCRYPTION_KEY not configured")
    try:
        encrypted = encrypt_session(session_string, settings.ENCRYPTION_KEY.encode())
    except Exception:
        logger.exception("Failed to encrypt Telegram session")
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
            notifier = request.app.state.notifier
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
            cache=cache,
            user_id=str(current_user.id),
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
        raise ExternalServiceError("Telegram bot notifications are not configured")
    token = _create_telegram_bot_link_token(current_user.id, settings)
    bot_username = await _resolve_bot_username(settings.TELEGRAM_BOT_TOKEN)
    return TelegramBotLinkResponse(
        bot_link=f"https://t.me/{bot_username}?start={token}",
    )


async def _get_user_by_bot_chat_id(db: AsyncSession, chat_id: int) -> UserModel | None:
    """Look up a user by their linked Telegram bot chat_id (JSONB query).

    Telegram chat_id values are 64-bit integers — cast to BigInteger to avoid
    int32 overflow which causes a 500 for any chat_id > 2^31.
    """
    result = await db.execute(
        select(UserModel).where(
            cast(UserModel.notification_preferences["telegram_bot_chat_id"], BigInteger) == chat_id
        )
    )
    return result.scalar_one_or_none()


async def _get_user_by_tg_user_id(db: AsyncSession, tg_user_id: int) -> UserModel | None:
    """Look up a user by their linked Telegram user ID (JSONB query).

    Telegram user IDs are 64-bit integers — cast to BigInteger to avoid
    int32 overflow which causes a 500 for any user_id > 2^31.
    """
    result = await db.execute(
        select(UserModel).where(
            cast(UserModel.notification_preferences["telegram_user_id"], BigInteger) == tg_user_id
        )
    )
    return result.scalar_one_or_none()


def _bot_channel_id(telegram_user_id: int) -> str:
    """Synthetic channel ID for bot DM signals."""
    return f"bot_dm_{telegram_user_id}"


_CONFIRM_TTL = 300  # 5 minutes
_CONFIRM_PREFIX = "bot:confirm:"

_HELP_TEXT = (
    "*Sage Radar AI — Vibe Trading Bot*\n\n"
    "Send me a trading signal as a text message and I'll route it to your SageMaster account.\n\n"
    "*Examples:*\n"
    "`Buy EURUSD @ 1.0850 SL 1.0800 TP 1.0950`\n"
    "`Sell XAUUSD market SL 2350 TP 2300`\n"
    "`Close GBPUSD`\n\n"
    "*Commands:*\n"
    "/help — Show this message\n"
    "/status — Check your linked account\n"
    "/unlink — Remove bot link"
)


@router.post("/webhook/telegram-bot")
async def telegram_bot_webhook(
    request: Request,
    body: TelegramBotUpdate,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Receive Telegram bot updates — commands, signals, and confirmations."""

    # --- Webhook secret verification ---
    if not settings.LOCAL_MODE:
        required_secret = settings.TELEGRAM_BOT_WEBHOOK_SECRET
        if not required_secret:
            logger.error("Telegram bot webhook secret not configured in production mode")
            raise ExternalServiceError("Telegram bot webhook secret is not configured")
        provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not provided_secret or not hmac.compare_digest(provided_secret, required_secret):
            raise AuthenticationError("Invalid Telegram webhook secret")

    bot = TelegramNotifier(bot_token=settings.TELEGRAM_BOT_TOKEN)

    # --- Callback query handling (confirm/cancel) ---
    if body.callback_query:
        await _handle_callback_query(body.callback_query, bot, db, settings, request)
        return {"ok": True}

    # --- Message handling ---
    message = body.message
    if not message:
        return {"ok": True}

    chat_id = message.chat.id
    chat_type = message.chat.type
    tg_user = message.from_user
    text = message.text

    # Only support private DMs — group/supergroup deferred to Phase 2
    if chat_type in ("group", "supergroup"):
        return {"ok": True}

    # Non-text messages
    if text is None:
        await bot.send_message(chat_id, "I can only process text messages containing trading signals.")
        return {"ok": True}

    # --- Command routing ---
    if text.startswith("/start"):
        return await _handle_start(text, chat_id, tg_user, bot, db, settings)

    if text.strip() == "/help":
        await bot.send_message(chat_id, _HELP_TEXT)
        return {"ok": True}

    if text.strip() == "/status":
        return await _handle_status(chat_id, bot, db)

    if text.strip() == "/unlink":
        return await _handle_unlink(chat_id, bot, db)

    # --- BOT_ENABLED gate (only for signal processing, not commands) ---
    if not settings.BOT_ENABLED:
        await bot.send_message(chat_id, "Vibe trading is not yet enabled. Stay tuned!")
        return {"ok": True}

    # --- Signal processing ---
    if not tg_user:
        return {"ok": True}

    user_row = await _get_user_by_bot_chat_id(db, chat_id)

    if not user_row:
        await bot.send_message(
            chat_id,
            "Your Telegram account is not linked. Use the Sage Radar dashboard to get a /start link.",
        )
        return {"ok": True}

    await _handle_signal_message(text, chat_id, tg_user.id, user_row, bot, db, settings, request)
    return {"ok": True}


async def _handle_start(
    text: str, chat_id: int, tg_user, bot, db: AsyncSession, settings: Settings,
) -> dict:
    """Handle /start with optional deep-link token for account linking."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await bot.send_message(chat_id, _HELP_TEXT)
        return {"ok": True}

    token_part = parts[1].strip()
    user_id = _decode_telegram_bot_link_token(token_part, settings)
    if user_id is None:
        await bot.send_message(chat_id, "This link has expired or is invalid. Please generate a new one from the dashboard.")
        return {"ok": True}

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user_row = result.scalar_one_or_none()
    if user_row is None:
        logger.warning("Telegram bot /start: user %s not found", user_id)
        return {"ok": True}

    # Uniqueness check: ensure this Telegram user isn't already linked to another account
    if tg_user:
        existing_owner = await _get_user_by_tg_user_id(db, tg_user.id)
        if existing_owner and existing_owner.id != user_row.id:
            await bot.send_message(
                chat_id,
                "This Telegram account is already linked to another Sage Radar account. "
                "Please unlink it first.",
            )
            return {"ok": True}

    prefs = user_row.notification_preferences or {}
    prefs["telegram_bot_chat_id"] = chat_id
    prefs["telegram_user_id"] = tg_user.id if tg_user else None
    user_row.notification_preferences = prefs

    # Auto-create bot routing rule if user has existing rules but none for bot_dm_
    if tg_user:
        tg_uid = tg_user.id
        bot_channel = _bot_channel_id(tg_uid)
        existing_bot_rule = (await db.execute(
            select(RoutingRuleModel.id).where(
                RoutingRuleModel.user_id == user_id,
                RoutingRuleModel.source_channel_id == bot_channel,
            ).limit(1)
        )).scalar_one_or_none()

        if existing_bot_rule is None:
            # Clone from user's first active routing rule
            first_rule = (await db.execute(
                select(RoutingRuleModel).where(
                    RoutingRuleModel.user_id == user_id,
                    RoutingRuleModel.is_active.is_(True),
                ).order_by(RoutingRuleModel.created_at.asc()).limit(1)
            )).scalar_one_or_none()

            if first_rule:
                db.add(RoutingRuleModel(
                    id=_uuid.uuid4(),
                    user_id=user_id,
                    source_channel_id=bot_channel,
                    source_channel_name="Vibe Trading Bot",
                    destination_webhook_url=first_rule.destination_webhook_url,
                    payload_version=first_rule.payload_version,
                    symbol_mappings=first_rule.symbol_mappings or {},
                    risk_overrides=first_rule.risk_overrides or {},
                    webhook_body_template=first_rule.webhook_body_template,
                    rule_name="Vibe Trading (Bot DM)",
                    destination_label=first_rule.destination_label,
                    destination_type=first_rule.destination_type,
                    custom_ai_instructions=first_rule.custom_ai_instructions,
                    enabled_actions=first_rule.enabled_actions,
                    keyword_blacklist=first_rule.keyword_blacklist or [],
                    is_active=True,
                ))
                logger.info("Auto-created bot routing rule for user %s", user_id)

    await db.commit()
    logger.info("Telegram bot linked for user %s, chat_id=%s", user_id, chat_id)
    await bot.send_message(
        chat_id,
        "Account linked successfully! Send me a trading signal to get started.\n\nType /help to see what I can do.",
    )
    return {"ok": True, "linked": True}


async def _handle_status(chat_id: int, bot, db: AsyncSession) -> dict:
    """Handle /status — show linked account info (DMs only)."""
    user_row = await _get_user_by_bot_chat_id(db, chat_id)
    if not user_row:
        await bot.send_message(chat_id, "No linked account found. Use the dashboard to link your account.")
        return {"ok": True}

    # Use func.count() for efficient rule counting
    prefs = user_row.notification_preferences or {}
    tg_user_id = prefs.get("telegram_user_id")
    rule_count = 0
    if tg_user_id:
        bot_channel = _bot_channel_id(tg_user_id)
        count_result = await db.execute(
            select(func.count())
            .select_from(RoutingRuleModel)
            .where(
                RoutingRuleModel.user_id == user_row.id,
                RoutingRuleModel.source_channel_id == bot_channel,
                RoutingRuleModel.is_active.is_(True),
            )
        )
        rule_count = count_result.scalar_one()

    lines = [
        "*Linked Account*",
        f"Email: {_escape_md(user_row.email)}",
        f"Tier: {_escape_md(user_row.subscription_tier or 'free')}",
        f"Bot routes: {rule_count}",
    ]
    await bot.send_message(chat_id, "\n".join(lines))
    return {"ok": True}


async def _handle_unlink(chat_id: int, bot, db: AsyncSession) -> dict:
    """Handle /unlink — remove telegram_bot_chat_id and telegram_user_id from user prefs."""
    user_row = await _get_user_by_bot_chat_id(db, chat_id)
    if not user_row:
        await bot.send_message(chat_id, "No linked account found.")
        return {"ok": True}

    prefs = user_row.notification_preferences or {}
    prefs.pop("telegram_bot_chat_id", None)
    prefs.pop("telegram_user_id", None)
    user_row.notification_preferences = prefs
    await db.commit()

    logger.info("Telegram bot unlinked for user %s", user_row.id)
    await bot.send_message(chat_id, "Account unlinked. You can re-link anytime from the dashboard.")
    return {"ok": True}


async def _handle_signal_message(
    text: str,
    chat_id: int,
    tg_user_id: int,
    user_row: UserModel,
    bot,
    db: AsyncSession,
    settings: Settings,
    request: Request,
) -> None:
    """Parse a text message as a trading signal and show confirmation."""
    bot_channel = _bot_channel_id(tg_user_id)

    # Check for routing rules
    rules = (await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.source_channel_id == bot_channel,
            RoutingRuleModel.user_id == user_row.id,
            RoutingRuleModel.is_active.is_(True),
        )
    )).scalars().all()

    if not rules:
        await bot.send_message(
            chat_id,
            "You don't have a routing rule set up for bot trading. "
            "Please create one in the Sage Radar dashboard with channel ID: "
            f"`{_bot_channel_id(tg_user_id)}`",
        )
        return

    # Parse signal via OpenAI
    sys_prompt, model_name, temp = await _get_parser_config(request, db)
    custom_instructions = next((r.custom_ai_instructions for r in rules if r.custom_ai_instructions), None)
    raw_signal = RawSignal(
        user_id=user_row.id,
        channel_id=bot_channel,
        raw_message=text,
        message_id=0,
        source_type="telegram_bot",
    )

    try:
        parser = OpenAISignalParser(
            api_key=settings.OPENAI_API_KEY,
            model=model_name,
            temperature=temp,
        )
        parsed = await parser.parse(raw_signal, custom_instructions=custom_instructions, system_prompt=sys_prompt)
    except Exception as exc:
        logger.error("Bot signal parse error: %s", exc)
        sentry_sdk.capture_exception(exc)
        await bot.send_message(chat_id, "Failed to parse your message. Please try again.")
        return

    if not parsed.is_valid_signal:
        hint = parsed.ignore_reason or "Not recognized as a trading signal"
        await bot.send_message(
            chat_id,
            f"Not a valid signal: {_escape_md(hint)}\n\nType /help for examples.",
        )
        return

    # Store confirmation state in Redis (with error handling)
    cache = request.app.state.cache
    confirm_token = str(_uuid.uuid4())
    confirm_data = json.dumps({
        "user_id": str(user_row.id),
        "tg_user_id": tg_user_id,
        "chat_id": chat_id,
        "parsed_signal": parsed.model_dump(),
        "routing_rule_ids": [str(r.id) for r in rules],
        "raw_message": text,
        "bot_channel": bot_channel,
    })
    try:
        await cache.set(f"{_CONFIRM_PREFIX}{confirm_token}", confirm_data, ttl_seconds=_CONFIRM_TTL)
    except Exception as exc:
        logger.error("Failed to store confirmation in Redis: %s", exc)
        sentry_sdk.capture_exception(exc)
        await bot.send_message(chat_id, "Something went wrong, please try again.")
        return

    # Build confirmation preview
    preview_lines = [
        "*Signal Preview*",
        f"Action: {_escape_md(parsed.action)}",
        f"Symbol: {_escape_md(parsed.symbol)}",
        f"Direction: {_escape_md(parsed.direction)}",
    ]
    if parsed.entry_price:
        preview_lines.append(f"Entry: {parsed.entry_price}")
    if parsed.stop_loss:
        preview_lines.append(f"SL: {parsed.stop_loss}")
    if parsed.take_profits:
        preview_lines.append(f"TP: {', '.join(str(tp) for tp in parsed.take_profits)}")
    preview_lines.append(f"\nRouting to {len(rules)} destination(s).")

    reply_markup = {
        "inline_keyboard": [[
            {"text": "Confirm", "callback_data": f"confirm:{confirm_token}"},
            {"text": "Cancel", "callback_data": f"cancel:{confirm_token}"},
        ]]
    }
    await bot.send_message(
        chat_id,
        "\n".join(preview_lines),
        reply_markup=reply_markup,
    )


async def _handle_callback_query(callback_query, bot, db: AsyncSession, settings: Settings, request: Request) -> None:
    """Handle confirm/cancel callback from inline keyboard."""
    cb_data = callback_query.data or ""
    cb_user = callback_query.from_user
    cb_message = callback_query.message

    chat_id = cb_message.chat.id if cb_message else None
    message_id = cb_message.message_id if cb_message else None

    # Acknowledge the callback immediately
    await bot.answer_callback_query(callback_query.id)

    if not chat_id or not message_id:
        return

    if cb_data.startswith("cancel:"):
        token = cb_data[7:]
        cache = request.app.state.cache
        await cache.delete(f"{_CONFIRM_PREFIX}{token}")
        await bot.edit_message_text(chat_id, message_id, "Trade cancelled.")
        return

    if not cb_data.startswith("confirm:"):
        return

    token = cb_data[8:]
    cache = request.app.state.cache

    # Atomic GETDEL for idempotency — prevents double-dispatch on double-tap
    try:
        confirm_json = await cache.getdel(f"{_CONFIRM_PREFIX}{token}")
    except Exception as exc:
        logger.error("Redis getdel failed during confirmation: %s", exc)
        sentry_sdk.capture_exception(exc)
        await bot.edit_message_text(chat_id, message_id, "Something went wrong. Please send your signal again.")
        return

    if not confirm_json:
        await bot.edit_message_text(chat_id, message_id, "This confirmation has expired. Please send your signal again.")
        return

    data = json.loads(confirm_json)

    # Verify the callback user is the signal owner
    if cb_user.id != data.get("tg_user_id"):
        await bot.edit_message_text(chat_id, message_id, "Only the original sender can confirm this trade.")
        return

    parsed = ParsedSignal(**data["parsed_signal"])
    user_id = UUID(data["user_id"])
    bot_channel = data["bot_channel"]
    raw_message = data["raw_message"]

    # Dispatch to all routing rules — wrapped in timeout guard
    dispatcher = request.app.state.dispatcher

    async def _do_dispatch() -> list[DispatchResult]:
        results: list[DispatchResult] = []
        for rule_id_str in data["routing_rule_ids"]:
            rule_row = (await db.execute(
                select(RoutingRuleModel).where(RoutingRuleModel.id == UUID(rule_id_str))
            )).scalar_one_or_none()

            if not rule_row or not rule_row.is_active:
                results.append(DispatchResult(routing_rule_id=UUID(rule_id_str), status="ignored", error_message="Rule no longer active"))
                continue

            raw_signal = RawSignal(
                user_id=user_id,
                channel_id=bot_channel,
                raw_message=raw_message,
                message_id=0,
                source_type="telegram_bot",
            )
            try:
                dispatch_result, log_kwargs = await _process_single_rule(rule_row, raw_signal, parsed, dispatcher)
                results.append(dispatch_result)
                db.add(SignalLogModel(**log_kwargs))
            except Exception as exc:
                logger.error("Bot dispatch failed for rule %s: %s", rule_id_str, exc)
                sentry_sdk.capture_exception(exc)
                results.append(DispatchResult(routing_rule_id=UUID(rule_id_str), status="failed", error_message=str(exc)))
                db.add(SignalLogModel(
                    user_id=user_id,
                    message_id=0,
                    channel_id=bot_channel,
                    raw_message=raw_message,
                    parsed_data=parsed.model_dump(),
                    status="failed",
                    error_message=str(exc),
                    source_type="telegram_bot",
                ))
        return results

    try:
        results = await asyncio.wait_for(_do_dispatch(), timeout=15.0)
    except asyncio.TimeoutError:
        logger.warning("Bot dispatch timed out for user %s", user_id)
        await bot.edit_message_text(
            chat_id, message_id,
            "Dispatch timed out — your signal may still be processing. Check your SageMaster dashboard.",
        )
        return

    # Build result message
    succeeded = sum(1 for r in results if r.status == "success")
    failed = [r for r in results if r.status == "failed"]

    if succeeded and not failed:
        result_text = f"Trade dispatched to {succeeded} destination(s)."
    elif failed and not succeeded:
        err = _escape_md(failed[0].error_message or "Unknown error")
        result_text = f"Dispatch failed: {err}"
    else:
        result_text = f"{succeeded} succeeded, {len(failed)} failed."

    await bot.edit_message_text(chat_id, message_id, result_text)
