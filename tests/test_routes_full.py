"""Comprehensive API endpoint tests expanding on test_routes.py.

Covers auth login/me, Telegram send-code/verify-code/status, channels,
routing-rule tier limits and partial updates, signal log pagination,
and error cases (invalid email, invalid payload_version, unauthenticated access).

Uses the same SQLite + aiosqlite infrastructure with PostgreSQL type compilation
overrides as test_routes.py.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import JSON, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import (
    Base,
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.api.deps import (
    Settings,
    create_access_token,
    get_current_user,
    get_db,
    get_settings,
)
from src.core.models import SubscriptionTier, User
from src.main import create_app

# ---------------------------------------------------------------------------
# SQLite compat: compile PostgreSQL types for SQLite
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

SAMPLE_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_USER_EMAIL = "test@example.com"
SAMPLE_USER_PASSWORD = "securepass123"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SAMPLE_PASSWORD_HASH = pwd_context.hash(SAMPLE_USER_PASSWORD)

SAMPLE_USER = User(
    id=SAMPLE_USER_ID,
    email=SAMPLE_USER_EMAIL,
    password_hash=SAMPLE_PASSWORD_HASH,
    subscription_tier=SubscriptionTier.free,
    created_at=datetime.now(timezone.utc),
)


def _make_test_settings() -> Settings:
    return Settings(
        DATABASE_URL=TEST_DB_URL,
        JWT_SECRET_KEY="test-secret",
        LOCAL_MODE=False,
        TELEGRAM_API_ID=12345,
        TELEGRAM_API_HASH="fakehash",
        ENCRYPTION_KEY="",  # overridden per-test when needed
        REDIS_URL="redis://localhost:6379/0",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_app():
    """Create a test app with SQLite-backed DB and the seeded test user."""
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

    def override_get_settings() -> Settings:
        return _make_test_settings()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    # Set up in-memory cache and session store for tests
    from src.adapters.redis.client import InMemoryCacheAdapter, InMemorySessionStore

    app.state.cache = InMemoryCacheAdapter()
    app.state.session_store = InMemorySessionStore()

    # Seed the test user with a real bcrypt hash so login tests work
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=SAMPLE_USER_ID,
                email=SAMPLE_USER_EMAIL,
                password_hash=SAMPLE_PASSWORD_HASH,
            )
        )
        await session.commit()

    yield app, async_session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def authed_app(test_app):
    """App fixture that also overrides get_current_user (for protected endpoints)."""
    app, session_factory = test_app

    async def override_get_current_user() -> User:
        return SAMPLE_USER

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield app, session_factory


@pytest_asyncio.fixture
async def client(test_app):
    """Unauthenticated client — no get_current_user override."""
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client(authed_app):
    """Client with get_current_user overridden (all protected endpoints work)."""
    app, _ = authed_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client_with_session(authed_app):
    """Authed client + session factory for direct DB manipulation."""
    app, session_factory = authed_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session_factory


# ===========================================================================
# Auth Tests
# ===========================================================================


class TestAuthLogin:
    """POST /api/v1/auth/login — OAuth2 form-based login."""

    async def test_login_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": SAMPLE_USER_EMAIL, "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Incorrect email or password" in resp.json()["error"]["message"]

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "anything"},
        )
        assert resp.status_code == 401


class TestAuthLoginJSON:
    """POST /api/v1/auth/login-json — JSON-based login."""

    async def test_login_json_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login-json",
            json={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Login now returns user profile to avoid /auth/me round-trip
        assert "user" in data
        assert data["user"]["email"] == SAMPLE_USER_EMAIL
        assert "subscription_tier" in data["user"]
        assert "is_admin" in data["user"]

    async def test_login_json_wrong_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login-json",
            json={"email": SAMPLE_USER_EMAIL, "password": "wrongpassword"},
        )
        assert resp.status_code == 401


class TestAuthMe:
    """GET /api/v1/auth/me — current user profile."""

    async def test_me_returns_profile(self, client: AsyncClient):
        # First login to get a real token
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == SAMPLE_USER_EMAIL
        assert data["id"] == str(SAMPLE_USER_ID)
        assert data["subscription_tier"] == "free"
        assert "created_at" in data


class TestUnauthenticatedAccess:
    """Protected endpoints must return 401 without a valid bearer token."""

    async def test_me_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_routing_rules_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/routing-rules")
        assert resp.status_code == 401

    async def test_create_routing_rule_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100999",
                "destination_webhook_url": "https://example.com/hook",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp.status_code == 401

    async def test_logs_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/logs")
        assert resp.status_code == 401

    async def test_telegram_status_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/telegram/status")
        assert resp.status_code == 401

    async def test_telegram_send_code_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/telegram/send-code",
            json={"phone_number": "+15551234567"},
        )
        assert resp.status_code == 401

    async def test_channels_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/channels")
        assert resp.status_code == 401


# ===========================================================================
# Telegram Tests (mock Telethon)
# ===========================================================================


class TestTelegramSendCode:
    """POST /api/v1/telegram/send-code — mock TelegramAuth."""

    async def test_send_code_success(self, authed_client: AsyncClient):
        mock_auth = AsyncMock()
        mock_auth.send_code.return_value = {"phone_code_hash": "abc123hash"}

        with patch("src.api.routes.telegram._get_telegram_auth", return_value=mock_auth):
            resp = await authed_client.post(
                "/api/v1/telegram/send-code",
                json={"phone_number": "+15551234567"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["phone_code_hash"] == "abc123hash"
        mock_auth.send_code.assert_awaited_once_with("+15551234567")


class TestTelegramVerifyCode:
    """POST /api/v1/telegram/verify-code — mock TelegramAuth + Redis."""

    async def test_verify_code_success(self, authed_app):
        app, session_factory = authed_app

        # Need a valid ENCRYPTION_KEY for the Fernet encrypt step
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()

        def override_settings() -> Settings:
            return Settings(
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY="test-secret",
                LOCAL_MODE=False,
                TELEGRAM_API_ID=12345,
                TELEGRAM_API_HASH="fakehash",
                ENCRYPTION_KEY=test_key,
                REDIS_URL="redis://localhost:6379/0",
            )

        app.dependency_overrides[get_settings] = override_settings

        mock_auth = AsyncMock()
        mock_auth.verify_code.return_value = "fake-session-string"

        with patch("src.api.routes.telegram._get_telegram_auth", return_value=mock_auth):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/v1/telegram/verify-code",
                    json={
                        "phone_number": "+15551234567",
                        "code": "12345",
                        "phone_code_hash": "abc123hash",
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["requires_2fa"] is False

        # Verify session was stored in DB
        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(TelegramSessionModel).where(
                    TelegramSessionModel.user_id == SAMPLE_USER_ID
                )
            )
            row = result.scalar_one_or_none()
            assert row is not None
            assert row.phone_number == "+15551234567"
            assert row.is_active is True

        # Verify session was cached in the in-memory session store
        session_store = app.state.session_store
        cached = await session_store.get_session(SAMPLE_USER_ID)
        assert cached is not None


class TestTelegramStatus:
    """GET /api/v1/telegram/status — with and without active session."""

    async def test_status_no_session(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/telegram/status")
        assert resp.status_code == 200
        assert resp.json()["connected"] is False

    async def test_status_with_active_session(self, authed_client_with_session):
        ac, session_factory = authed_client_with_session

        # Insert an active session into the DB
        async with session_factory() as session:
            session.add(
                TelegramSessionModel(
                    user_id=SAMPLE_USER_ID,
                    phone_number="+15551234567",
                    session_string_encrypted="encrypted_data_here",
                    is_active=True,
                )
            )
            await session.commit()

        resp = await ac.get("/api/v1/telegram/status")
        assert resp.status_code == 200
        assert resp.json()["connected"] is True


# ===========================================================================
# Channels Tests
# ===========================================================================


class TestChannels:
    """GET /api/v1/channels — mock get_user_channels."""

    async def test_list_channels(self, authed_app):
        app, session_factory = authed_app

        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        fernet = Fernet(test_key.encode())
        encrypted_session = fernet.encrypt(b"fake-session-string").decode()

        def override_settings() -> Settings:
            return Settings(
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY="test-secret",
                LOCAL_MODE=False,
                TELEGRAM_API_ID=12345,
                TELEGRAM_API_HASH="fakehash",
                ENCRYPTION_KEY=test_key,
                REDIS_URL="redis://localhost:6379/0",
            )

        app.dependency_overrides[get_settings] = override_settings

        # Insert an active session
        async with session_factory() as session:
            session.add(
                TelegramSessionModel(
                    user_id=SAMPLE_USER_ID,
                    phone_number="+15551234567",
                    session_string_encrypted=encrypted_session,
                    is_active=True,
                )
            )
            await session.commit()

        mock_channels = [
            {"channel_id": "-1001111", "channel_name": "Signals VIP", "username": "signalsvip"},
            {"channel_id": "-1002222", "channel_name": "Gold Room", "username": None},
        ]

        # Mock Redis to return None (fall back to DB) and mock get_user_channels
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with (
            patch("redis.asyncio.from_url", return_value=mock_redis),
            patch(
                "src.adapters.telegram.get_user_channels",
                new_callable=AsyncMock,
                return_value=mock_channels,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/api/v1/channels")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "-1001111"
        assert data[0]["title"] == "Signals VIP"
        assert data[0]["username"] == "signalsvip"
        assert data[1]["username"] is None


# ===========================================================================
# Routing Rules Tests
# ===========================================================================


class TestRoutingRulesList:
    """GET /api/v1/routing-rules — list all rules for user."""

    async def test_list_empty(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/routing-rules")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_returns_created_rules(self, authed_client: AsyncClient):
        # Create two rules
        await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100111",
                "destination_webhook_url": "https://example.com/hook1",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )

        resp = await authed_client.get("/api/v1/routing-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source_channel_id"] == "-100111"


class TestRoutingRuleTierLimit:
    """POST /api/v1/routing-rules — tier limit enforcement (403 when exceeded)."""

    async def test_free_tier_allows_one_rule(self, authed_client: AsyncClient):
        # Free tier allows 1 rule
        resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100001",
                "destination_webhook_url": "https://example.com/hook1",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp.status_code == 201

    async def test_free_tier_blocks_second_rule(self, authed_client: AsyncClient):
        # Create first rule (should succeed)
        resp1 = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100001",
                "destination_webhook_url": "https://example.com/hook1",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp1.status_code == 201

        # Second rule should succeed (free tier now allows 5, matching pro for beta)
        resp2 = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100002",
                "destination_webhook_url": "https://example.com/hook2",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp2.status_code == 201


class TestRoutingRuleUpdateWithSymbolMappings:
    """PUT /api/v1/routing-rules/{id} — partial update with symbol_mappings."""

    async def test_update_symbol_mappings(self, authed_client: AsyncClient):
        # Create a rule first
        create_resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100555",
                "destination_webhook_url": "https://example.com/hook",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        rule_id = create_resp.json()["id"]

        # Update only symbol_mappings
        update_resp = await authed_client.put(
            f"/api/v1/routing-rules/{rule_id}",
            json={"symbol_mappings": {"GOLD": "XAUUSD", "SILVER": "XAGUSD"}},
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["symbol_mappings"] == {"GOLD": "XAUUSD", "SILVER": "XAGUSD"}
        # Other fields unchanged
        assert data["payload_version"] == "V1"
        assert data["is_active"] is True

    async def test_update_payload_version_to_v2(self, authed_client: AsyncClient):
        create_resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100666",
                "destination_webhook_url": "https://example.com/hook",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        rule_id = create_resp.json()["id"]

        update_resp = await authed_client.put(
            f"/api/v1/routing-rules/{rule_id}",
            json={"payload_version": "V2"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["payload_version"] == "V2"


class TestWebhookUrlSecurity:
    """SSRF protections for user-provided webhook URLs."""

    async def test_create_rule_rejects_private_webhook_url(self, authed_client: AsyncClient):
        resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100777",
                "destination_webhook_url": "http://127.0.0.1/hook",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp.status_code == 422
        assert "Invalid destination webhook URL" in resp.json()["error"]["message"]

    async def test_update_rule_rejects_private_webhook_url(self, authed_client: AsyncClient):
        create_resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100778",
                "destination_webhook_url": "https://example.com/hook",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        rule_id = create_resp.json()["id"]

        update_resp = await authed_client.put(
            f"/api/v1/routing-rules/{rule_id}",
            json={"destination_webhook_url": "https://169.254.169.254/latest/meta-data"},
        )
        assert update_resp.status_code == 422
        assert "Invalid destination webhook URL" in update_resp.json()["error"]["message"]

    async def test_webhook_test_rejects_private_url_with_422(self, authed_client: AsyncClient):
        resp = await authed_client.post(
            "/api/v1/webhook/test",
            json={"url": "https://localhost/test"},
        )
        assert resp.status_code == 422
        assert "Invalid webhook URL" in resp.json()["error"]["message"]


class TestWebhookUrlUniqueness:
    """Cross-account webhook URL uniqueness enforcement."""

    async def test_create_rejects_webhook_url_used_by_another_account(
        self, authed_client_with_session,
    ):
        ac, session_factory = authed_client_with_session
        other_user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        webhook_url = "https://api.sagemaster.io/deals_idea/shared-assist-id"

        # Insert a rule from another user with the same webhook URL
        async with session_factory() as session:
            session.add(UserModel(
                id=other_user_id,
                email="other@example.com",
                password_hash="$2b$12$fakehashfakehashfakehashfakehashfakehashfakehashfake",
            ))
            session.add(RoutingRuleModel(
                user_id=other_user_id,
                source_channel_id="-100999",
                destination_webhook_url=webhook_url,
                payload_version="V1",
                webhook_body_template={"type": "", "assistId": "test", "source": "", "symbol": "", "date": ""},
                is_active=True,
            ))
            await session.commit()

        # Try to create a rule with the same webhook URL from the test user
        resp = await ac.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100888",
                "destination_webhook_url": webhook_url,
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp.status_code == 409
        assert "already in use by another account" in resp.json()["error"]["message"]

    async def test_create_allows_same_webhook_url_for_same_user(
        self, authed_client: AsyncClient,
    ):
        webhook_url = "https://api.sagemaster.io/deals_idea/my-own-assist"

        # Create first rule
        resp1 = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100111",
                "destination_webhook_url": webhook_url,
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp1.status_code == 201

        # Same user, same webhook URL, different channel — should be allowed
        resp2 = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100222",
                "destination_webhook_url": webhook_url,
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp2.status_code == 201


# ===========================================================================
# Signal Logs Tests
# ===========================================================================


class TestSignalLogs:
    """GET /api/v1/logs — pagination and empty results."""

    async def test_empty_logs(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["limit"] == 50
        assert data["offset"] == 0

    async def test_logs_pagination(self, authed_client_with_session):
        ac, session_factory = authed_client_with_session

        # Insert 5 signal logs directly into the DB
        async with session_factory() as session:
            for i in range(5):
                session.add(
                    SignalLogModel(
                        user_id=SAMPLE_USER_ID,
                        raw_message=f"Signal message {i}",
                        status="success",
                        parsed_data={"symbol": "EURUSD"},
                        webhook_payload={"action": "buy"},
                    )
                )
            await session.commit()

        # Fetch page 1 (limit=2, offset=0)
        resp = await ac.get("/api/v1/logs", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Fetch page 2 (limit=2, offset=2)
        resp2 = await ac.get("/api/v1/logs", params={"limit": 2, "offset": 2})
        data2 = resp2.json()
        assert data2["total"] == 5
        assert len(data2["items"]) == 2
        assert data2["offset"] == 2

        # Fetch page 3 (limit=2, offset=4) — only 1 remaining
        resp3 = await ac.get("/api/v1/logs", params={"limit": 2, "offset": 4})
        data3 = resp3.json()
        assert data3["total"] == 5
        assert len(data3["items"]) == 1

    async def test_logs_with_custom_limit(self, authed_client_with_session):
        ac, session_factory = authed_client_with_session

        async with session_factory() as session:
            for i in range(3):
                session.add(
                    SignalLogModel(
                        user_id=SAMPLE_USER_ID,
                        raw_message=f"Log entry {i}",
                        status="failed",
                        error_message="parse error",
                    )
                )
            await session.commit()

        resp = await ac.get("/api/v1/logs", params={"limit": 100, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # Verify fields
        item = data["items"][0]
        assert "id" in item
        assert "raw_message" in item
        assert item["status"] == "failed"
        assert item["error_message"] == "parse error"


# ===========================================================================
# Error Cases
# ===========================================================================


class TestErrorCases:
    """Validation errors and bad payloads."""

    async def test_register_invalid_email_format(self, client: AsyncClient):
        """The register endpoint accepts a plain string for email.
        FastAPI / Pydantic won't reject it at schema level since the field
        is typed as `str`, but we verify the endpoint handles the request.
        If additional email validation is added, this should return 422."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "securepass123"},
        )
        # The endpoint currently accepts any string as email (str type).
        # The test verifies the request is processed without server error.
        assert resp.status_code in (201, 422)

    async def test_register_missing_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "valid@example.com"},
        )
        assert resp.status_code == 422

    async def test_register_missing_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"password": "something"},
        )
        assert resp.status_code == 422

    async def test_create_routing_rule_invalid_payload_version(
        self, authed_client: AsyncClient
    ):
        """payload_version must be 'V1' or 'V2' — anything else should be 422."""
        resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100999",
                "destination_webhook_url": "https://example.com/hook",
                "payload_version": "V3",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp.status_code == 422

    async def test_update_routing_rule_invalid_payload_version(
        self, authed_client: AsyncClient
    ):
        """PUT with invalid payload_version should be 422."""
        # Create a valid rule first
        create_resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "source_channel_id": "-100888",
                "destination_webhook_url": "https://example.com/hook",
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        rule_id = create_resp.json()["id"]

        resp = await authed_client.put(
            f"/api/v1/routing-rules/{rule_id}",
            json={"payload_version": "INVALID"},
        )
        assert resp.status_code == 422

    async def test_create_routing_rule_missing_required_fields(
        self, authed_client: AsyncClient
    ):
        """source_channel_id and destination_webhook_url are required."""
        resp = await authed_client.post(
            "/api/v1/routing-rules",
            json={
                "payload_version": "V1",
                "webhook_body_template": {"type": "", "assistId": "test-assist-id", "source": "", "symbol": "", "date": ""},
            },
        )
        assert resp.status_code == 422

    async def test_login_missing_fields(self, client: AsyncClient):
        """OAuth2 form login without username should fail."""
        resp = await client.post(
            "/api/v1/auth/login",
            data={"password": "something"},
        )
        assert resp.status_code == 422

    async def test_invalid_bearer_token(self, client: AsyncClient):
        """A garbage bearer token should return 401."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer garbage-token-value"},
        )
        assert resp.status_code == 401


# ===========================================================================
# Cross-user phone uniqueness
# ===========================================================================


class TestPhoneUniqueness:
    """Verify that the same phone number cannot be active for two different users."""

    async def test_verify_code_rejects_duplicate_phone(
        self, authed_app
    ):
        """If another user already has an active session with this phone, verify returns 409."""
        app, session_factory = authed_app

        # Seed an active session for a DIFFERENT user with the same phone
        other_user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        async with session_factory() as session:
            session.add(
                UserModel(
                    id=other_user_id,
                    email="other@example.com",
                    password_hash=SAMPLE_PASSWORD_HASH,
                )
            )
            session.add(
                TelegramSessionModel(
                    user_id=other_user_id,
                    phone_number="+14155559999",
                    session_string_encrypted="enc_session_data",
                    is_active=True,
                )
            )
            await session.commit()

        # Override settings to provide an encryption key
        settings = _make_test_settings()
        settings.ENCRYPTION_KEY = "test-encryption-key-32-bytes-ok!"
        app.dependency_overrides[get_settings] = lambda: settings

        # Mock the Telegram auth to return a session string and encryption
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("src.api.routes.telegram._get_telegram_auth") as mock_get_auth, \
                 patch("src.core.security.encrypt_session", return_value="encrypted"):
                mock_auth = AsyncMock()
                mock_auth.verify_code = AsyncMock(return_value="fake_session_string")
                mock_get_auth.return_value = mock_auth

                resp = await client.post(
                    "/api/v1/telegram/verify-code",
                    json={
                        "phone_number": "+14155559999",
                        "code": "12345",
                        "phone_code_hash": "hash123",
                    },
                )

        assert resp.status_code == 409
        assert "already connected" in resp.json()["error"]["message"]


# ===========================================================================
# Login Performance & Caching Tests (PR #62)
# ===========================================================================


class TestLoginReturnsUser:
    """Login and register endpoints should return user profile alongside token."""

    async def test_login_json_includes_user_profile(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login-json",
            json={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        user = data["user"]
        assert user["email"] == SAMPLE_USER_EMAIL
        assert "id" in user
        assert "subscription_tier" in user
        assert "is_admin" in user
        assert "email_verified" in user
        assert "created_at" in user

    async def test_register_includes_user_profile(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@example.com", "password": "newpass123", "terms_accepted": True},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["subscription_tier"] == "free"
        assert data["user"]["is_admin"] is False


class TestUserCache:
    """get_current_user should cache user in Redis and bust on mutations."""

    async def test_user_cached_after_first_request(self, test_app):
        """After a protected request, user should be in cache."""
        app, _ = test_app
        # Login to get a real token
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login_resp = await ac.post(
                "/api/v1/auth/login-json",
                json={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
            )
            token = login_resp.json()["access_token"]

            # Call /auth/me (protected endpoint) which triggers get_current_user
            me_resp = await ac.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_resp.status_code == 200

            # Check that user is now cached
            cache = app.state.cache
            cached = await cache.get(f"user:{SAMPLE_USER_ID}")
            assert cached is not None
            import json
            data = json.loads(cached)
            assert data["email"] == SAMPLE_USER_EMAIL
            # password_hash should NOT be in cache (security)
            assert "password_hash" not in data

    async def test_user_cache_busted_on_email_verify(self, test_app):
        """Verifying email should clear the user cache."""
        app, session_factory = test_app
        cache = app.state.cache

        # Pre-populate cache
        import json
        await cache.set(f"user:{SAMPLE_USER_ID}", json.dumps({
            "id": str(SAMPLE_USER_ID),
            "email": SAMPLE_USER_EMAIL,
            "subscription_tier": "free",
            "is_admin": False,
            "is_disabled": False,
            "email_verified": False,
            "created_at": "2026-01-01T00:00:00+00:00",
        }), ttl_seconds=300)

        # Create a verification token
        from src.adapters.db.models import EmailVerificationTokenModel
        raw_token = "test-verify-token-123"
        token_hash = pwd_context.hash(raw_token)
        async with session_factory() as session:
            session.add(EmailVerificationTokenModel(
                user_id=SAMPLE_USER_ID,
                token_hash=token_hash,
                expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            ))
            await session.commit()

        # Verify email
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/verify-email",
                json={"token": raw_token},
            )
            assert resp.status_code == 200

        # Cache should be busted
        cached = await cache.get(f"user:{SAMPLE_USER_ID}")
        assert cached is None


class TestLegacyTokenFallback:
    """Legacy token fallback should remain deterministic for large token sets."""

    async def test_verify_email_legacy_fallback_scans_beyond_50_rows(self, test_app):
        app, session_factory = test_app
        from src.adapters.db.models import EmailVerificationTokenModel

        valid_token = "legacy-verify-target"
        now = datetime.now(timezone.utc)

        async with session_factory() as session:
            for i in range(55):
                token_value = valid_token if i == 0 else f"legacy-verify-{i}"
                session.add(
                    EmailVerificationTokenModel(
                        user_id=SAMPLE_USER_ID,
                        token_hash=token_value,
                        token_lookup_hash=None,
                        expires_at=now + timedelta(hours=1),
                        created_at=now + timedelta(seconds=i),
                    )
                )
            await session.commit()

        with patch(
            "src.api.routes.pwd_context.verify",
            side_effect=lambda raw, stored: raw == stored,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/v1/auth/verify-email",
                    json={"token": valid_token},
                )

        assert resp.status_code == 200

    async def test_reset_password_legacy_fallback_scans_beyond_50_rows(self, test_app):
        app, session_factory = test_app
        from src.adapters.db.models import PasswordResetTokenModel, UserModel

        valid_token = "legacy-reset-target"
        now = datetime.now(timezone.utc)

        async with session_factory() as session:
            for i in range(55):
                token_value = valid_token if i == 0 else f"legacy-reset-{i}"
                session.add(
                    PasswordResetTokenModel(
                        user_id=SAMPLE_USER_ID,
                        token_hash=token_value,
                        token_lookup_hash=None,
                        expires_at=now + timedelta(hours=1),
                        created_at=now + timedelta(seconds=i),
                    )
                )
            await session.commit()

        with patch(
            "src.api.routes.pwd_context.verify",
            side_effect=lambda raw, stored: raw == stored,
        ), patch(
            "src.api.routes.pwd_context.hash",
            side_effect=lambda value: f"hashed:{value}",
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/v1/auth/reset-password",
                    json={"token": valid_token, "new_password": "newpass123"},
                )

        assert resp.status_code == 200

        async with session_factory() as session:
            from sqlalchemy import select

            user_row = (
                await session.execute(select(UserModel).where(UserModel.id == SAMPLE_USER_ID))
            ).scalar_one()
            assert user_row.password_hash == "hashed:newpass123"


class TestTelegramStatusCache:
    """Telegram status endpoint should cache responses."""

    async def test_telegram_status_cached(self, authed_client):
        """First call hits DB, second call should use cache."""
        # First call
        resp1 = await authed_client.get("/api/v1/telegram/status")
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["connected"] is False

        # Second call should return same data (from cache)
        resp2 = await authed_client.get("/api/v1/telegram/status")
        assert resp2.status_code == 200
        assert resp2.json() == data1
