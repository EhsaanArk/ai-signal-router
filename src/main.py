"""Application factory for the SGM Telegram Signal Copier."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance.

    Behaviour varies depending on ``LOCAL_MODE``:

    * **LOCAL_MODE=true** (default) — includes the dev router and auto-creates
      database tables on startup.
    * **LOCAL_MODE=false** — production mode; only public + workflow routers are
      mounted.  Database migrations are expected to be handled by Alembic.
    """
    local_mode = os.environ.get("LOCAL_MODE", "true").lower() in ("true", "1", "yes")

    application = FastAPI(
        title="SGM Telegram Signal Copier",
        description="Intercepts trading signals from Telegram and routes them to SageMaster webhooks.",
        version="0.1.0",
    )

    # ------------------------------------------------------------------
    # Mount routers
    # ------------------------------------------------------------------
    from src.api.routes import router as v1_router
    from src.api.workflow import workflow_router

    application.include_router(v1_router)
    application.include_router(workflow_router)

    if local_mode:
        from src.api.dev import dev_router

        application.include_router(dev_router)
        logger.info("DEV router mounted at /api/dev (LOCAL_MODE=true)")

    # ------------------------------------------------------------------
    # Startup event
    # ------------------------------------------------------------------
    @application.on_event("startup")
    async def on_startup() -> None:
        mode_label = "LOCAL / development" if local_mode else "PRODUCTION"
        logger.info("Starting SGM Telegram Signal Copier in %s mode", mode_label)

        if local_mode:
            # Ensure DATABASE_URL is set for the session module
            from src.api.deps import get_settings

            settings = get_settings()
            # Expose DATABASE_URL to the session module if not already set
            if not os.environ.get("DATABASE_URL"):
                os.environ["DATABASE_URL"] = settings.DATABASE_URL

            from src.adapters.db.session import init_db

            logger.info("Creating database tables (LOCAL_MODE) ...")
            try:
                await init_db()
                logger.info("Database tables ready.")
            except Exception as exc:
                logger.error("Failed to initialise database: %s", exc)
                raise

    return application


# ------------------------------------------------------------------
# Module-level app instance for ``uvicorn src.main:app``
# ------------------------------------------------------------------
app = create_app()
