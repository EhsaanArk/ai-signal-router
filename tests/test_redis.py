"""Tests for ``src.adapters.redis.client.RedisSessionStore``.

Covers save, get (hit + miss), delete, and verifies that the encryption
helpers from ``src.core.security`` can be composed with the store to
protect session data at rest.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.redis.client import RedisSessionStore, _SESSION_TTL_SECONDS
from src.core.security import decrypt_session, encrypt_session, generate_key

SAMPLE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_SESSION_STRING = "BQAz1234FakeSessionString=="


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store_with_mock() -> tuple[RedisSessionStore, AsyncMock]:
    """Return a ``RedisSessionStore`` whose internal Redis client is mocked."""
    store = object.__new__(RedisSessionStore)
    mock_redis = AsyncMock()
    store._redis = mock_redis
    return store, mock_redis


# ---------------------------------------------------------------------------
# save_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_session_calls_redis_set_with_ttl():
    """``save_session`` should SET the value with the 24-hour TTL."""
    store, mock_redis = _make_store_with_mock()

    await store.save_session(SAMPLE_USER_ID, SAMPLE_SESSION_STRING)

    mock_redis.set.assert_awaited_once_with(
        f"session:{SAMPLE_USER_ID}",
        SAMPLE_SESSION_STRING,
        ex=_SESSION_TTL_SECONDS,
    )


@pytest.mark.asyncio
async def test_save_session_stores_encrypted_data():
    """When the caller encrypts before saving, the stored value must be
    the ciphertext — not the plaintext session string."""
    store, mock_redis = _make_store_with_mock()
    key = generate_key()
    encrypted = encrypt_session(SAMPLE_SESSION_STRING, key)

    await store.save_session(SAMPLE_USER_ID, encrypted)

    stored_value = mock_redis.set.call_args[0][1]
    assert stored_value != SAMPLE_SESSION_STRING
    assert stored_value == encrypted


# ---------------------------------------------------------------------------
# get_session — cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_returns_stored_value():
    """``get_session`` should return the raw string stored in Redis."""
    store, mock_redis = _make_store_with_mock()
    mock_redis.get.return_value = SAMPLE_SESSION_STRING

    result = await store.get_session(SAMPLE_USER_ID)

    mock_redis.get.assert_awaited_once_with(f"session:{SAMPLE_USER_ID}")
    assert result == SAMPLE_SESSION_STRING


@pytest.mark.asyncio
async def test_get_session_returns_decryptable_value():
    """When encrypted data is stored, ``get_session`` returns ciphertext that
    the caller can successfully decrypt back to the original session string."""
    store, mock_redis = _make_store_with_mock()
    key = generate_key()
    encrypted = encrypt_session(SAMPLE_SESSION_STRING, key)
    mock_redis.get.return_value = encrypted

    result = await store.get_session(SAMPLE_USER_ID)

    assert result is not None
    decrypted = decrypt_session(result, key)
    assert decrypted == SAMPLE_SESSION_STRING


# ---------------------------------------------------------------------------
# get_session — cache miss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_returns_none_on_cache_miss():
    """``get_session`` should return ``None`` when Redis has no key."""
    store, mock_redis = _make_store_with_mock()
    mock_redis.get.return_value = None

    result = await store.get_session(SAMPLE_USER_ID)

    assert result is None


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_session_calls_redis_delete():
    """``delete_session`` should call ``DELETE`` on the correct key."""
    store, mock_redis = _make_store_with_mock()

    await store.delete_session(SAMPLE_USER_ID)

    mock_redis.delete.assert_awaited_once_with(f"session:{SAMPLE_USER_ID}")


# ---------------------------------------------------------------------------
# Encryption round-trip with the store
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_encryption_roundtrip_through_store():
    """Full round-trip: encrypt -> save -> get -> decrypt yields the
    original plaintext, proving the encryption key works correctly."""
    store, mock_redis = _make_store_with_mock()
    key = generate_key()

    # Encrypt and save
    encrypted = encrypt_session(SAMPLE_SESSION_STRING, key)
    await store.save_session(SAMPLE_USER_ID, encrypted)

    # Simulate Redis returning the same encrypted value
    mock_redis.get.return_value = encrypted

    # Retrieve and decrypt
    retrieved = await store.get_session(SAMPLE_USER_ID)
    assert retrieved is not None
    decrypted = decrypt_session(retrieved, key)

    assert decrypted == SAMPLE_SESSION_STRING
    assert encrypted != SAMPLE_SESSION_STRING  # ciphertext differs from plaintext
