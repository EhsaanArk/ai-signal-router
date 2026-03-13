"""Redis adapter implementing the ``SessionStore`` protocol.

Uses ``redis.asyncio`` for async Redis operations.  Session strings are stored
under the key pattern ``session:{user_id}`` with a 24-hour TTL.
"""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS: int = 60 * 60 * 24  # 24 hours


class RedisSessionStore:
    """Concrete ``SessionStore`` backed by Redis.

    Parameters
    ----------
    redis_url:
        A full Redis connection string, e.g.
        ``redis://localhost:6379/0`` or an Upstash Redis URL.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(
            redis_url,
            decode_responses=True,
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _key(user_id: UUID) -> str:
        return f"session:{user_id}"

    # -- SessionStore protocol -----------------------------------------------

    async def save_session(self, user_id: UUID, session_string: str) -> None:
        """Persist *session_string* under ``session:{user_id}`` with a 24 h TTL."""
        key = self._key(user_id)
        await self._redis.set(
            key,
            session_string,
            ex=_SESSION_TTL_SECONDS,
        )
        logger.debug("Saved session for user %s (TTL=%ds)", user_id, _SESSION_TTL_SECONDS)

    async def get_session(self, user_id: UUID) -> str | None:
        """Return the session string for *user_id*, or ``None`` if missing/expired."""
        key = self._key(user_id)
        value = await self._redis.get(key)
        if value is None:
            return None
        return str(value)

    async def delete_session(self, user_id: UUID) -> None:
        """Remove the session key for *user_id*."""
        key = self._key(user_id)
        await self._redis.delete(key)
        logger.debug("Deleted session for user %s", user_id)

    # -- lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Cleanly shut down the underlying Redis connection pool."""
        await self._redis.aclose()
