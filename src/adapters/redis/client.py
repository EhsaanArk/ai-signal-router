"""Redis adapters implementing ``SessionStore`` and ``CachePort`` protocols.

Uses ``redis.asyncio`` for async Redis operations.  Includes in-memory
fallbacks for LOCAL_MODE when Redis is not available.
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS: int = 60 * 60 * 24  # 24 hours


# ---------------------------------------------------------------------------
# SessionStore implementations
# ---------------------------------------------------------------------------


class RedisSessionStore:
    """Concrete ``SessionStore`` backed by Redis.

    Parameters
    ----------
    redis_client:
        A shared ``redis.asyncio.Redis`` instance.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    @staticmethod
    def _key(user_id: UUID) -> str:
        return f"session:{user_id}"

    async def save_session(self, user_id: UUID, session_string: str) -> None:
        key = self._key(user_id)
        await self._redis.set(key, session_string, ex=_SESSION_TTL_SECONDS)
        logger.debug("Saved session for user %s (TTL=%ds)", user_id, _SESSION_TTL_SECONDS)

    async def get_session(self, user_id: UUID) -> str | None:
        key = self._key(user_id)
        value = await self._redis.get(key)
        if value is None:
            return None
        return str(value)

    async def delete_session(self, user_id: UUID) -> None:
        key = self._key(user_id)
        await self._redis.delete(key)
        logger.debug("Deleted session for user %s", user_id)

    async def close(self) -> None:
        await self._redis.aclose()


class InMemorySessionStore:
    """In-memory ``SessionStore`` fallback for LOCAL_MODE."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def save_session(self, user_id: UUID, session_string: str) -> None:
        self._store[str(user_id)] = session_string

    async def get_session(self, user_id: UUID) -> str | None:
        return self._store.get(str(user_id))

    async def delete_session(self, user_id: UUID) -> None:
        self._store.pop(str(user_id), None)

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# CachePort implementations
# ---------------------------------------------------------------------------


class RedisCacheAdapter:
    """Concrete ``CachePort`` backed by Redis.

    Parameters
    ----------
    redis_client:
        A shared ``redis.asyncio.Redis`` instance.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        value = await self._redis.get(key)
        if value is None:
            return None
        return str(value)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        await self._redis.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def close(self) -> None:
        await self._redis.aclose()


class InMemoryCacheAdapter:
    """In-memory ``CachePort`` fallback for LOCAL_MODE.

    Stores values as ``(value, expiry_timestamp)`` tuples.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry is not None and time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expiry = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def close(self) -> None:
        pass
