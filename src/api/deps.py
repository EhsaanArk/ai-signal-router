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

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import InvalidTokenError
from pydantic_settings import BaseSettings
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import UserModel
from src.adapters.db.session import get_async_session_factory
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


limiter = Limiter(key_func=_get_real_ip)

# ---------------------------------------------------------------------------
# OAuth2 scheme
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


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

    # Supabase settings
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


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


# ---------------------------------------------------------------------------
# JWT helpers (kept for backward compatibility during migration)
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
# Current-user dependency (Supabase JWT + auto-sync)
# ---------------------------------------------------------------------------


_USER_CACHE_TTL = 300  # 5 minutes


def _extract_supabase_user_id(token: str, settings: Settings) -> UUID:
    """Decode a Supabase JWT and return the user UUID.

    Tries Supabase JWT secret first, falls back to legacy JWT secret.
    """
    # Try Supabase JWT secret
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
            return UUID(payload["sub"])
        except (InvalidTokenError, ValueError):
            pass

    # Fallback: legacy JWT secret (for backward compatibility during migration)
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return UUID(payload["sub"])
    except (InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Decode the bearer token and return the corresponding :class:`User`.

    Supports both Supabase JWTs and legacy JWTs. When a Supabase user hits
    the API for the first time, a UserModel row is auto-created.

    Uses Redis cache (5-min TTL) to avoid a DB query on every protected request.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = _extract_supabase_user_id(token, settings)

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
                    password_hash="",
                    subscription_tier=SubscriptionTier(data["subscription_tier"]),
                    is_admin=data.get("is_admin", False),
                    is_disabled=data.get("is_disabled", False),
                    email_verified=data.get("email_verified", False),
                    created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
                )
                if user.is_disabled:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account is disabled",
                    )
                return user
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.debug("User cache parse error for %s, falling back to DB", user_id)
        except HTTPException:
            raise
        except Exception:
            logger.debug("User cache read failed for %s, falling back to DB", user_id)

    # Cache miss — query DB
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user_row = result.scalar_one_or_none()

    # Auto-create user on first Supabase-authenticated API call
    if user_row is None and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            from supabase import create_client
            sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            sb_user = sb.auth.admin.get_user_by_id(str(user_id))
            email = sb_user.user.email or ""

            # Check admin list
            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
            is_admin = email.lower() in admin_emails
            tier = settings.ADMIN_TIER if is_admin else "free"

            user_row = UserModel(
                id=user_id,
                email=email,
                password_hash="supabase_managed",
                subscription_tier=tier,
                is_admin=is_admin,
                email_verified=sb_user.user.email_confirmed_at is not None,
                terms_accepted_at=datetime.now(timezone.utc),
            )
            db.add(user_row)
            await db.flush()
            logger.info("Auto-created user %s (%s) from Supabase", user_id, email)

            # Send welcome email for new Supabase users (non-blocking)
            if settings.RESEND_API_KEY:
                try:
                    from src.adapters.email import ResendNotifier
                    notifier = ResendNotifier(api_key=settings.RESEND_API_KEY)
                    import asyncio
                    asyncio.ensure_future(notifier.send_welcome(email, settings.FRONTEND_URL))
                except Exception:
                    logger.debug("Welcome email failed for new user %s", user_id)
        except Exception as exc:
            logger.error("Failed to auto-create user %s: %s", user_id, exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if getattr(user_row, "is_disabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    user = User(
        id=user_row.id,
        email=user_row.email,
        password_hash=user_row.password_hash,
        subscription_tier=SubscriptionTier(user_row.subscription_tier),
        is_admin=getattr(user_row, "is_admin", False),
        is_disabled=getattr(user_row, "is_disabled", False),
        email_verified=getattr(user_row, "email_verified", False),
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
