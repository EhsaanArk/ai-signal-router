"""Async database engine, session factory, and dependency injection helpers."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.adapters.db.models import Base

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """Read DATABASE_URL from environment and ensure it uses the asyncpg driver.

    Neon and most PostgreSQL providers expose a ``postgresql://`` URL.
    This helper transparently rewrites the scheme to
    ``postgresql+asyncpg://`` so SQLAlchemy uses the async driver.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Please configure it in your .env or environment."
        )

    # Normalise the scheme for asyncpg
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


# ---------------------------------------------------------------------------
# Engine & session factory (lazy singletons)
# ---------------------------------------------------------------------------


def get_engine() -> AsyncEngine:
    """Return the lazily-created async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
            pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
            pool_pre_ping=True,
        )
    return _engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the lazily-created async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


# Convenience aliases so callers can import directly
engine = property(get_engine)  # type: ignore[assignment]
async_session_factory = property(get_async_session_factory)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` for use as a FastAPI dependency (``Depends``).

    The session is committed on success and rolled back on exception, then
    always closed.
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
# Dev / testing helper
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables defined in ``Base.metadata``.

    Intended for local development and test harnesses.
    **Do not use in production** — use Alembic migrations instead.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
