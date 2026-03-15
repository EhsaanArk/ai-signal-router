"""Application factory for the SGM Telegram Signal Copier."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
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
        # Initialise OpenTelemetry before anything else so auto-instrumentors
        # can patch libraries before they are first imported.
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

        yield

        # Shutdown
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
