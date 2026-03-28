"""Tests for the Telegram Bot notification adapter and bot webhook endpoint."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import Base, UserModel
from src.adapters.telegram.notifier import TelegramNotifier
from src.api.deps import Settings, get_current_user, get_db, get_settings
from src.api.routes import _create_bot_link_token
from src.core.models import DispatchResult, SubscriptionTier, User
from src.main import create_app


# ---------------------------------------------------------------------------
# SQLite compat
# ---------------------------------------------------------------------------

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
BOT_WEBHOOK_SECRET = "test-telegram-webhook-secret"
BOT_LINK_SECRET = "test-telegram-link-secret"
SAMPLE_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_USER = User(
    id=SAMPLE_USER_ID,
    email="test@example.com",
    password_hash="$2b$12$fakehashedpassword",
    subscription_tier=SubscriptionTier.starter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_app():
    engine = create_async_engine(TEST_DB_URL, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_user() -> User:
        return SAMPLE_USER

    def override_get_settings() -> Settings:
        return Settings(
            DATABASE_URL=TEST_DB_URL,
            JWT_SECRET_KEY="test-secret",
            LOCAL_MODE=False,
            TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            TELEGRAM_BOT_WEBHOOK_SECRET=BOT_WEBHOOK_SECRET,
            TELEGRAM_BOT_LINK_SECRET=BOT_LINK_SECRET,
        )

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings

    # Provide a mock Redis cache on app.state for bot webhook tests
    _cache_store: dict[str, str] = {}

    mock_cache = AsyncMock()

    async def _mock_set(key, value, ttl_seconds=None):
        _cache_store[key] = value

    async def _mock_get(key):
        return _cache_store.get(key)

    async def _mock_getdel(key):
        return _cache_store.pop(key, None)

    async def _mock_delete(key):
        _cache_store.pop(key, None)

    mock_cache.set = _mock_set
    mock_cache.get = _mock_get
    mock_cache.getdel = _mock_getdel
    mock_cache.delete = _mock_delete
    app.state.cache = mock_cache

    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=SAMPLE_USER_ID,
                email="test@example.com",
                password_hash="$2b$12$fakehashedpassword",
                subscription_tier="starter",
            )
        )
        await session.commit()

    yield app, async_session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_app):
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def session_factory(test_app):
    _, factory = test_app
    return factory


# ---------------------------------------------------------------------------
# TelegramNotifier unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_dispatch_summary_success():
    """Should POST to Telegram Bot API with the right payload."""
    notifier = TelegramNotifier(bot_token="fake-token")
    results = [
        DispatchResult(status="success", routing_rule_id=uuid.uuid4()),
        DispatchResult(status="failed", routing_rule_id=uuid.uuid4(), error_message="HTTP 500"),
    ]

    mock_response = httpx.Response(200, json={"ok": True})

    with patch("src.adapters.telegram.notifier.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        await notifier.send_dispatch_summary(
            chat_id=123456789,
            signal_symbol="EURUSD",
            results=results,
        )

        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["chat_id"] == 123456789
        assert "EURUSD" in payload["text"]


@pytest.mark.asyncio
async def test_send_dispatch_summary_no_token():
    """Should silently skip when bot_token is empty."""
    notifier = TelegramNotifier(bot_token="")
    results = [DispatchResult(status="success", routing_rule_id=uuid.uuid4())]

    with patch("src.adapters.telegram.notifier.httpx.AsyncClient") as MockClient:
        await notifier.send_dispatch_summary(
            chat_id=123,
            signal_symbol="EURUSD",
            results=results,
        )
        MockClient.assert_not_called()


# ---------------------------------------------------------------------------
# Bot webhook /start flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_bot_start_links_chat_id(client, test_app, session_factory):
    """POST to /webhook/telegram-bot with /start token should store chat_id."""
    app, _ = test_app
    cache = app.state.cache
    token = await _create_bot_link_token(SAMPLE_USER_ID, cache)

    resp = await client.post(
        "/api/v1/webhook/telegram-bot",
        json={
            "update_id": 1,
            "message": {
                "text": f"/start {token}",
                "chat": {"id": 987654321},
                "from": {"id": 987654321, "first_name": "Test"},
                "message_id": 1,
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": BOT_WEBHOOK_SECRET},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("linked") is True

    # Verify chat_id was stored
    async with session_factory() as session:
        result = await session.execute(
            select(UserModel.notification_preferences).where(
                UserModel.id == SAMPLE_USER_ID
            )
        )
        prefs = result.scalar_one()
        assert prefs["telegram_bot_chat_id"] == 987654321


@pytest.mark.asyncio
async def test_telegram_bot_invalid_token(client):
    """Invalid token should not crash, just return ok."""
    resp = await client.post(
        "/api/v1/webhook/telegram-bot",
        json={
            "update_id": 2,
            "message": {
                "text": "/start invalid-garbage",
                "chat": {"id": 111},
                "message_id": 2,
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": BOT_WEBHOOK_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json().get("linked") is None


@pytest.mark.asyncio
async def test_telegram_bot_no_message(client):
    """Update without message should just return ok."""
    resp = await client.post(
        "/api/v1/webhook/telegram-bot",
        json={"update_id": 3},
        headers={"X-Telegram-Bot-Api-Secret-Token": BOT_WEBHOOK_SECRET},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_telegram_bot_webhook_secret_required(client):
    """In non-local mode, webhook requests without secret header are rejected."""
    resp = await client.post(
        "/api/v1/webhook/telegram-bot",
        json={
            "update_id": 4,
            "message": {
                "text": "/start some_token",
                "chat": {"id": 333},
                "message_id": 4,
            },
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_telegram_bot_unknown_token_rejected(client):
    """Tokens not in Redis must not link chat IDs."""
    resp = await client.post(
        "/api/v1/webhook/telegram-bot",
        json={
            "update_id": 5,
            "message": {
                "text": "/start unknown_token_not_in_redis",
                "chat": {"id": 444},
                "message_id": 5,
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": BOT_WEBHOOK_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json().get("linked") is None


# ---------------------------------------------------------------------------
# Notification preferences round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notification_prefs_include_telegram_fields(client):
    """GET /settings/notifications should include telegram fields."""
    resp = await client.get("/api/v1/settings/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert "telegram_on_success" in data
    assert "telegram_on_failure" in data
    assert "telegram_bot_chat_id" in data


@pytest.mark.asyncio
async def test_update_telegram_notification_prefs(client):
    """PUT /settings/notifications should accept telegram toggle updates."""
    resp = await client.put(
        "/api/v1/settings/notifications",
        json={"telegram_on_failure": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_on_failure"] is True
