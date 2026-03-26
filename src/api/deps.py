"""FastAPI dependency injection — settings, DB sessions, auth helpers."""

from __future__ import annotations

import json
import ipaddress
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import InvalidTokenError
from pydantic_settings import BaseSettings
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import UserModel
from src.adapters.db.session import get_async_session_factory
from src.core.constants import ACCESS_TOKEN_EXPIRE_DAYS as _ACCESS_TOKEN_EXPIRE_DAYS
from src.core.constants import USER_CACHE_TTL_SECONDS
from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.models import SubscriptionTier, User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

@lru_cache
def _trusted_proxy_networks() -> tuple[ipaddress._BaseNetwork, ...]:
    """Parse TRUSTED_PROXY_IPS settings into CIDR networks."""
    raw = get_settings().TRUSTED_PROXY_IPS or ""
    networks: list[ipaddress._BaseNetwork] = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        try:
            if "/" in value:
                networks.append(ipaddress.ip_network(value, strict=False))
            else:
                ip_obj = ipaddress.ip_address(value)
                bits = 32 if ip_obj.version == 4 else 128
                networks.append(ipaddress.ip_network(f"{value}/{bits}", strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXY_IPS entry: %s", value)
    return tuple(networks)


def _is_trusted_proxy(remote_ip: str) -> bool:
    """Return True if *remote_ip* belongs to a trusted proxy network."""
    try:
        ip_obj = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return any(ip_obj in network for network in _trusted_proxy_networks())


def _get_real_ip(request: Request) -> str:
    """Extract client IP, trusting proxy headers only from trusted peers."""
    remote_ip = request.client.host if request.client else "127.0.0.1"

    if _is_trusted_proxy(remote_ip):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            parsed_chain: list[str] = []
            for part in forwarded.split(","):
                candidate = part.strip()
                if not candidate:
                    continue
                try:
                    ipaddress.ip_address(candidate)
                    parsed_chain.append(candidate)
                except ValueError:
                    logger.debug("Ignoring invalid X-Forwarded-For value: %s", candidate)

            if parsed_chain:
                # Remove trusted proxy hops from the right side of the chain.
                while parsed_chain and _is_trusted_proxy(parsed_chain[-1]):
                    parsed_chain.pop()

                if parsed_chain:
                    # Use the closest untrusted hop (right-most remaining IP)
                    # to prevent spoofing via forged left-most values.
                    return parsed_chain[-1]

    return remote_ip


def _get_rate_limit_storage() -> str | None:
    """Return Redis URL for rate limit storage, or None for in-memory fallback.

    Redis-backed storage ensures rate limits work correctly across multiple
    API instances behind a load balancer. In LOCAL_MODE or when Redis is
    unavailable, falls back to in-memory (single-instance only).
    """
    import os
    if os.environ.get("LOCAL_MODE", "").lower() == "true":
        return None
    redis_url = os.environ.get("REDIS_URL", "")
    return redis_url if redis_url else None


_storage_uri = _get_rate_limit_storage()
limiter = Limiter(
    key_func=_get_real_ip,
    storage_uri=_storage_uri,
    in_memory_fallback_enabled=True,  # graceful degradation if Redis is down
)

# ---------------------------------------------------------------------------
# OAuth2 scheme
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = _ACCESS_TOKEN_EXPIRE_DAYS


class Settings(BaseSettings):
    """Application-wide settings populated from environment / .env file."""

    LOCAL_MODE: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sgm_copier"
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    ENCRYPTION_KEY: str = ""
    QSTASH_TOKEN: str = ""
    QSTASH_URL: str = ""
    RESEND_API_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: str = ""
    QSTASH_CURRENT_SIGNING_KEY: str = ""
    QSTASH_NEXT_SIGNING_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    SENTRY_DSN: str = ""
    ADMIN_EMAILS: str = ""
    ADMIN_TIER: str = "elite"
    TELEGRAM_BOT_WEBHOOK_SECRET: str = ""
    TELEGRAM_BOT_LINK_SECRET: str = ""
    TRUSTED_PROXY_IPS: str = ""

    # Vibe Trading Bot feature flag
    BOT_ENABLED: bool = False

    # Two-stage dispatch pipeline (marketplace scale)
    TWO_STAGE_DISPATCH: bool = False
    BACKEND_URL: str = "http://localhost:8000"

    # Supabase settings
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Lazy singleton for Supabase admin client
_supabase_admin_client = None


def _get_supabase_admin():
    """Return a cached Supabase admin client (service role)."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        settings = get_settings()
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            return None
        from supabase import create_client
        _supabase_admin_client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _supabase_admin_client


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` singleton."""
    return Settings()


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------


async def get_db(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` for use as a FastAPI dependency.

    The session factory is obtained from the shared ``session`` module which
    already handles the ``postgresql://`` → ``postgresql+asyncpg://``
    conversion.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Cache and session store dependencies
# ---------------------------------------------------------------------------


def get_cache(request: Request):
    """Return the shared CachePort instance from app state."""
    return request.app.state.cache


def get_session_store(request: Request):
    """Return the shared SessionStore instance from app state."""
    return request.app.state.session_store


def get_dispatcher(request: Request):
    """Return the shared WebhookDispatcher instance from app state."""
    return request.app.state.dispatcher


def get_notifier(request: Request):
    """Return the shared ResendNotifier instance from app state."""
    return request.app.state.notifier


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(data: dict, settings: Settings) -> str:
    """Create a signed JWT with a 7-day expiry.

    Parameters
    ----------
    data:
        Payload dict — must include ``"sub"`` (user id as string).
    settings:
        Application settings providing the secret key.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------


_USER_CACHE_TTL = USER_CACHE_TTL_SECONDS


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    background_tasks: BackgroundTasks = None,
) -> User:
    """Decode the bearer token and return the corresponding :class:`User`.

    Supports both Supabase JWTs (via API verification) and legacy JWTs.
    When a Supabase user hits the API for the first time, a UserModel row
    is auto-created.

    Uses Redis cache (5-min TTL) to avoid a DB query on every protected request.
    """
    if not token:
        raise AuthenticationError("Not authenticated")

    credentials_exception = AuthenticationError("Could not validate credentials")

    user_id: UUID | None = None

    # 1. Try Supabase API verification (no JWT secret needed)
    sb = _get_supabase_admin()
    if sb is not None:
        try:
            sb_user = sb.auth.get_user(token)
            if sb_user and sb_user.user:
                user_id = UUID(sb_user.user.id)
                logger.debug("Supabase token verified for user %s", user_id)
        except Exception as exc:
            logger.debug("Supabase token verification failed: %s", exc)

    # 2. Fallback: legacy JWT decode
    if user_id is None:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["sub", "exp"]},
            )
            user_id_str: str | None = payload.get("sub")
            if user_id_str is None:
                raise credentials_exception
            user_id = UUID(user_id_str)
        except (InvalidTokenError, ValueError) as exc:
            logger.debug("Legacy JWT decode also failed: %s", exc)
            raise credentials_exception from exc

    # Try Redis cache first
    cache = getattr(request.app.state, "cache", None)
    cache_key = f"user:{user_id}"
    if cache:
        try:
            cached = await cache.get(cache_key)
            if cached:
                data = json.loads(cached)
                user = User(
                    id=UUID(data["id"]),
                    email=data["email"],
                    password_hash="",  # Not cached for security
                    subscription_tier=SubscriptionTier(data["subscription_tier"]),
                    is_admin=data.get("is_admin", False),
                    is_disabled=data.get("is_disabled", False),
                    email_verified=data.get("email_verified", False),
                    accepted_tos_version=data.get("accepted_tos_version"),
                    accepted_risk_waiver=data.get("accepted_risk_waiver", False),
                    created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
                )
                if user.is_disabled:
                    raise AuthorizationError("Account is disabled")
                return user
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.debug("User cache parse error for %s, falling back to DB", user_id)
        except AuthorizationError:
            raise
        except Exception:
            logger.debug("User cache read failed for %s, falling back to DB", user_id)

    # Cache miss — query DB
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user_row = result.scalar_one_or_none()

    # Auto-create user on first Supabase-authenticated API call
    if user_row is None and sb is not None:
        try:
            sb_user_data = sb.auth.admin.get_user_by_id(str(user_id))
            email = sb_user_data.user.email or ""

            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
            is_admin = email.lower() in admin_emails
            tier = settings.ADMIN_TIER if is_admin else "free"

            user_row = UserModel(
                id=user_id,
                email=email,
                password_hash="!",
                subscription_tier=tier,
                is_admin=is_admin,
                email_verified=sb_user_data.user.email_confirmed_at is not None,
            )
            db.add(user_row)
            await db.flush()
            logger.info("Auto-created user %s (%s) from Supabase", user_id, email)

            # Fire welcome email as a background task so it doesn't block
            # the auth dependency (avoids I/O in the request path).
            if settings.RESEND_API_KEY and background_tasks is not None:
                async def _send_welcome_bg(api_key: str, to: str, url: str) -> None:
                    try:
                        from src.adapters.email import ResendNotifier
                        notifier = ResendNotifier(api_key=api_key)
                        await notifier.send_welcome(to, url)
                    except Exception:
                        logger.debug("Welcome email failed for new user (bg)")

                background_tasks.add_task(
                    _send_welcome_bg, settings.RESEND_API_KEY, email, settings.FRONTEND_URL
                )
        except IntegrityError:
            # Email already exists with a different UUID — this happens when a
            # user registered via /register (local UUID) then logs in via
            # Supabase (different UUID). Look up the existing row by email
            # and return it directly, bypassing the normal user_row flow.
            await db.rollback()
            email = sb_user_data.user.email
            result = await db.execute(
                select(UserModel).where(UserModel.email == email)
            )
            user_row = result.scalar_one_or_none()
            if user_row is None:
                logger.error("Auto-create conflict but no row for email %s", email)
                raise credentials_exception

            logger.info(
                "Supabase UUID %s matched existing user %s (email=%s) via email fallback",
                user_id, user_row.id, user_row.email,
            )

            # Build User and return immediately — skip the normal flow below
            # which may fail due to session state after rollback
            user = User(
                id=user_row.id,
                email=user_row.email,
                password_hash=user_row.password_hash,
                subscription_tier=SubscriptionTier(user_row.subscription_tier),
                is_admin=getattr(user_row, "is_admin", False),
                is_disabled=getattr(user_row, "is_disabled", False),
                email_verified=getattr(user_row, "email_verified", False),
                accepted_tos_version=getattr(user_row, "accepted_tos_version", None),
                accepted_risk_waiver=getattr(user_row, "accepted_risk_waiver", False),
                created_at=user_row.created_at,
            )
            if user.is_disabled:
                raise AuthorizationError("Account is disabled")
            # Cache under Supabase UUID so next request hits cache
            if cache:
                try:
                    cache_data = json.dumps({
                        "id": str(user.id),
                        "email": user.email,
                        "subscription_tier": user.subscription_tier.value,
                        "is_admin": user.is_admin,
                        "is_disabled": user.is_disabled,
                        "email_verified": user.email_verified,
                        "accepted_tos_version": user.accepted_tos_version,
                        "accepted_risk_waiver": user.accepted_risk_waiver,
                        "created_at": user.created_at.isoformat() if user.created_at else "",
                    })
                    await cache.set(f"user:{user_id}", cache_data, ex=_USER_CACHE_TTL)
                except Exception:
                    pass
            return user
        except Exception as exc:
            logger.error("Failed to auto-create user %s: %s", user_id, exc)
            raise credentials_exception from exc

    if user_row is None:
        raise credentials_exception

    if getattr(user_row, "is_disabled", False):
        raise AuthorizationError("Account is disabled")

    user = User(
        id=user_row.id,
        email=user_row.email,
        password_hash=user_row.password_hash,
        subscription_tier=SubscriptionTier(user_row.subscription_tier),
        is_admin=getattr(user_row, "is_admin", False),
        is_disabled=getattr(user_row, "is_disabled", False),
        email_verified=getattr(user_row, "email_verified", False),
        accepted_tos_version=getattr(user_row, "accepted_tos_version", None),
        accepted_risk_waiver=getattr(user_row, "accepted_risk_waiver", False),
        created_at=user_row.created_at,
    )

    # Store in cache
    if cache:
        try:
            await cache.set(cache_key, json.dumps({
                "id": str(user.id),
                "email": user.email,
                "subscription_tier": user.subscription_tier.value,
                "is_admin": user.is_admin,
                "is_disabled": user.is_disabled,
                "email_verified": user.email_verified,
                "accepted_tos_version": user.accepted_tos_version,
                "accepted_risk_waiver": user.accepted_risk_waiver,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }), ttl_seconds=_USER_CACHE_TTL)
        except Exception:
            logger.debug("Failed to cache user %s", user_id)

    return user


async def get_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the current user to be an admin."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required")
    return current_user
