"""Application factory for the SGM Telegram Signal Copier."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "dev-secret-key-change-in-production"


def _validate_production_settings(settings) -> None:
    """Raise on missing or insecure settings when LOCAL_MODE is False."""
    errors: list[str] = []

    if settings.JWT_SECRET_KEY == _DEFAULT_JWT_SECRET:
        errors.append("JWT_SECRET_KEY is set to the default dev value — set a strong secret")

    if not settings.ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY is empty — Telegram sessions cannot be decrypted")

    if not settings.SUPABASE_JWT_SECRET:
        logger.warning(
            "SUPABASE_JWT_SECRET not set — Supabase tokens will not validate. "
            "Set it from Supabase Dashboard → Settings → API → JWT Secret."
        )

    if not settings.OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is empty — signal parsing will fail")

    if "localhost" in settings.DATABASE_URL:
        errors.append("DATABASE_URL points to localhost — set a production database URL")

    if "localhost" in settings.REDIS_URL:
        errors.append("REDIS_URL points to localhost — set a production Redis URL")

    if not settings.FRONTEND_URL or "localhost" in settings.FRONTEND_URL:
        errors.append("FRONTEND_URL is not set or points to localhost")

    if settings.TELEGRAM_API_ID == 0:
        errors.append("TELEGRAM_API_ID is not set — Telegram auth will fail")

    if settings.TELEGRAM_BOT_TOKEN:
        if not settings.TELEGRAM_BOT_WEBHOOK_SECRET:
            errors.append(
                "TELEGRAM_BOT_WEBHOOK_SECRET is required when TELEGRAM_BOT_TOKEN is set"
            )
        if not settings.TELEGRAM_BOT_LINK_SECRET:
            errors.append(
                "TELEGRAM_BOT_LINK_SECRET is required when TELEGRAM_BOT_TOKEN is set"
            )

    if errors:
        for err in errors:
            logger.error("PRODUCTION CONFIG ERROR: %s", err)
        raise RuntimeError(
            f"Production startup blocked — {len(errors)} config error(s): "
            + "; ".join(errors)
        )

    # Warnings for optional-but-recommended settings
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — email notifications will be disabled")

    if not settings.QSTASH_CURRENT_SIGNING_KEY:
        logger.warning("QSTASH_CURRENT_SIGNING_KEY not set — QStash signature validation will fail")

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot notifications will be disabled")


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance.

    Behaviour varies depending on ``LOCAL_MODE``:

    * **LOCAL_MODE=true** (default) — includes the dev router and auto-creates
      database tables on startup.
    * **LOCAL_MODE=false** — production mode; only public + workflow routers are
      mounted.  Database migrations are expected to be handled by Alembic.
    """
    local_mode = os.environ.get("LOCAL_MODE", "true").lower() in ("true", "1", "yes")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Initialise Sentry first (inside lifespan so uvicorn logging is ready)
        sentry_dsn = os.environ.get("SENTRY_DSN", "")
        if sentry_dsn:
            import sentry_sdk

            service_role = os.environ.get("SERVICE_ROLE", "api")
            sentry_env = os.environ.get(
                "SENTRY_ENVIRONMENT",
                "development" if local_mode else "staging",
            )
            sentry_sdk.init(
                dsn=sentry_dsn,
                send_default_pii=True,
                traces_sample_rate=0.1,
                environment=sentry_env,
                server_name=f"sgm-{service_role}",
            )
            sentry_sdk.set_tag("service.role", service_role)
            logger.info("Sentry initialised (role=%s)", service_role)

        # Initialise OpenTelemetry so auto-instrumentors can patch libraries
        # before they are first imported.
        from src.adapters.telemetry import init_telemetry

        init_telemetry()

        mode_label = "LOCAL / development" if local_mode else "PRODUCTION"
        logger.info("Starting SGM Telegram Signal Copier in %s mode", mode_label)

        from src.api.deps import get_settings

        settings_local = get_settings()

        if not local_mode:
            _validate_production_settings(settings_local)

        # Initialise cache and session store
        if local_mode:
            from src.adapters.redis.client import InMemoryCacheAdapter, InMemorySessionStore

            app.state.cache = InMemoryCacheAdapter()
            app.state.session_store = InMemorySessionStore()
        else:
            import redis.asyncio as aioredis

            from src.adapters.redis.client import RedisCacheAdapter, RedisSessionStore

            redis_client = aioredis.from_url(
                settings_local.REDIS_URL, decode_responses=True
            )
            app.state.cache = RedisCacheAdapter(redis_client)
            app.state.session_store = RedisSessionStore(redis_client)

        # Initialise shared webhook dispatcher
        from src.adapters.webhook import WebhookDispatcher

        app.state.dispatcher = WebhookDispatcher(timeout=15.0)

        # LOCAL_MODE: auto-create tables
        if local_mode:
            if not os.environ.get("DATABASE_URL"):
                os.environ["DATABASE_URL"] = settings_local.DATABASE_URL

            from src.adapters.db.session import init_db

            logger.info("Creating database tables (LOCAL_MODE) ...")
            try:
                await init_db()
                logger.info("Database tables ready.")
            except Exception as exc:
                logger.error("Failed to initialise database: %s", exc)
                raise

        # Auto-promote admin users from ADMIN_EMAILS env var
        admin_emails_raw = settings_local.ADMIN_EMAILS
        if admin_emails_raw:
            admin_emails = [e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()]
            if admin_emails:
                from sqlalchemy import update
                from sqlalchemy.ext.asyncio import AsyncSession as SASession
                from src.adapters.db.session import get_engine
                from src.adapters.db.models import UserModel

                admin_tier = settings_local.ADMIN_TIER

                engine = get_engine()
                async with SASession(engine, expire_on_commit=False) as db:
                    result = await db.execute(
                        update(UserModel)
                        .where(UserModel.email.in_(admin_emails))
                        .values(is_admin=True, subscription_tier=admin_tier)
                        .returning(UserModel.email)
                    )
                    promoted = [row[0] for row in result.all()]
                    await db.commit()
                if promoted:
                    logger.info("Admin bootstrap: %s → is_admin=True, tier=%s", promoted, admin_tier)

        yield

        # Shutdown
        if os.environ.get("SENTRY_DSN", ""):
            import sentry_sdk

            sentry_sdk.flush(timeout=2)

        from src.adapters.telemetry import shutdown_telemetry

        shutdown_telemetry()
        await app.state.dispatcher.close()
        await app.state.cache.close()
        if hasattr(app.state.session_store, "close"):
            await app.state.session_store.close()

    application = FastAPI(
        title="SGM Telegram Signal Copier",
        description="Intercepts trading signals from Telegram and routes them to SageMaster webhooks.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    from src.api.deps import limiter

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    from src.api.deps import get_settings

    settings = get_settings()
    if settings.ALLOWED_ORIGINS:
        origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
    elif local_mode:
        origins = ["http://localhost:5173", "http://localhost:3000"]
    else:
        origins = [settings.FRONTEND_URL]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ------------------------------------------------------------------
    # Security headers
    # ------------------------------------------------------------------
    from starlette.middleware.base import BaseHTTPMiddleware

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            if not local_mode:
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
            return response

    application.add_middleware(SecurityHeadersMiddleware)

    # ------------------------------------------------------------------
    # Health check (verifies DB connectivity)
    # ------------------------------------------------------------------
    @application.get("/health")
    async def health_check():
        db_status = "unknown"
        try:
            from sqlalchemy import text

            from src.adapters.db.session import get_async_session_factory

            factory = get_async_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as exc:
            db_status = f"unreachable: {exc}"
            if not local_mode:
                logger.error("Health check DB ping failed: %s", exc)
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "database": db_status},
                )
        return {"status": "ok", "database": db_status}

    # ------------------------------------------------------------------
    # Deploy health check (unauthenticated — aggregate counts only)
    # ------------------------------------------------------------------
    @application.get("/health/deploy")
    @limiter.limit("6/minute")
    async def deploy_health_check(request: Request):
        """Post-deploy verification endpoint.

        Returns current session/listener/channel counts plus a comparison
        against the pre-shutdown snapshot saved by the previous container.
        Public response contains only aggregate, non-PII information.
        """
        from sqlalchemy import func, select as sa_select

        from src.adapters.db.models import (
            RoutingRuleModel,
            SignalLogModel,
            TelegramSessionModel,
        )
        from src.adapters.db.session import get_async_session_factory
        from src.adapters.telegram.deploy_snapshot import (
            compare_snapshots,
            read_pre_deploy_snapshot,
        )

        # Current state from DB
        try:
            factory = get_async_session_factory()
            async with factory() as db:
                active_sessions = (await db.execute(
                    sa_select(func.count()).select_from(TelegramSessionModel)
                    .where(TelegramSessionModel.is_active.is_(True))
                )).scalar_one()

                active_session_users = (await db.execute(
                    sa_select(TelegramSessionModel.user_id)
                    .where(TelegramSessionModel.is_active.is_(True))
                )).scalars().all()

                active_channels = (await db.execute(
                    sa_select(func.count(func.distinct(
                        RoutingRuleModel.source_channel_id
                    ))).where(RoutingRuleModel.is_active.is_(True))
                )).scalar_one()

                last_signal = (await db.execute(
                    sa_select(SignalLogModel.processed_at)
                    .order_by(SignalLogModel.processed_at.desc())
                    .limit(1)
                )).scalar_one_or_none()
        except Exception as exc:
            logger.error("Deploy health check DB query failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(exc)},
            )

        current_internal = {
            "active_sessions": active_sessions,
            "connected_listeners": active_sessions,  # DB reflects connected state
            "channels_monitored": active_channels,
            "user_ids": [str(uid) for uid in active_session_users],
            "last_signal_at": last_signal.isoformat() if last_signal else None,
        }

        # Compare against pre-deploy snapshot
        cache = request.app.state.cache
        pre_snapshot = await read_pre_deploy_snapshot(cache)

        comparison = None
        deploy_health = "HEALTHY"
        if pre_snapshot:
            comparison = compare_snapshots(pre_snapshot, current_internal)
            deploy_health = comparison["verdict"]

        def _sanitize_snapshot(snapshot: dict | None) -> dict | None:
            if snapshot is None:
                return None
            return {
                "active_sessions": snapshot.get("active_sessions", 0),
                "connected_listeners": snapshot.get("connected_listeners", 0),
                "channels_monitored": snapshot.get("channels_monitored", 0),
                "timestamp": snapshot.get("timestamp"),
                "last_signal_at": snapshot.get("last_signal_at"),
            }

        def _sanitize_comparison(data: dict | None) -> dict | None:
            if data is None:
                return None
            return {
                "verdict": data.get("verdict"),
                "sessions_before": data.get("sessions_before", 0),
                "sessions_after": data.get("sessions_after", 0),
                "sessions_delta": data.get("sessions_delta", 0),
                "connected_before": data.get("connected_before", 0),
                "connected_after": data.get("connected_after", 0),
                "channels_before": data.get("channels_before", 0),
                "channels_after": data.get("channels_after", 0),
                "lost_user_count": len(data.get("lost_user_ids", [])),
                "new_user_count": len(data.get("new_user_ids", [])),
                "pre_deploy_timestamp": data.get("pre_deploy_timestamp"),
            }

        return {
            "status": "ok",
            "deploy_health": deploy_health,
            "current": _sanitize_snapshot(current_internal),
            "pre_deploy_snapshot": _sanitize_snapshot(pre_snapshot),
            "comparison": _sanitize_comparison(comparison),
        }

    # ------------------------------------------------------------------
    # Mount routers
    # ------------------------------------------------------------------
    from src.api.admin import admin_router
    from src.api.routes import router as v1_router
    from src.api.workflow import workflow_router

    application.include_router(v1_router)
    application.include_router(workflow_router)
    application.include_router(admin_router)

    if local_mode:
        from src.api.dev import dev_router

        application.include_router(dev_router)
        logger.info("DEV router mounted at /api/dev (LOCAL_MODE=true)")

    return application


# ------------------------------------------------------------------
# Module-level app instance for ``uvicorn src.main:app``
# ------------------------------------------------------------------
app = create_app()
