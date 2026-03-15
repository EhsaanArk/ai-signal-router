"""API endpoint tests using httpx AsyncClient with dependency overrides.

Uses SQLite + aiosqlite with PostgreSQL type compilation overrides.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import Base, UserModel
from src.api.deps import get_current_user, get_db, get_settings, Settings
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
SAMPLE_USER = User(
    id=SAMPLE_USER_ID,
    email="test@example.com",
    password_hash="$2b$12$fakehashedpassword",
    subscription_tier=SubscriptionTier.free,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_app():
    """Create a test app with SQLite-backed DB overrides."""
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
        )

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings

    # Set up in-memory cache and session store for tests
    from src.adapters.redis.client import InMemoryCacheAdapter, InMemorySessionStore

    app.state.cache = InMemoryCacheAdapter()
    app.state.session_store = InMemorySessionStore()

    # Seed a test user for duplicate-email checks
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=SAMPLE_USER_ID,
                email="test@example.com",
                password_hash="$2b$12$fakehashedpassword",
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


# ===========================================================================
# Tests
# ===========================================================================


async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "anything"},
    )
    assert resp.status_code == 409


_DEFAULT_TEMPLATE = {
    "type": "",
    "assistId": "test-assist-id",
    "source": "",
    "symbol": "",
    "date": "",
}


async def test_create_and_get_routing_rule(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/routing-rules",
        json={
            "source_channel_id": "-100999",
            "source_channel_name": "Test Channel",
            "destination_webhook_url": "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307",
            "payload_version": "V1",
            "webhook_body_template": _DEFAULT_TEMPLATE,
        },
    )
    assert create_resp.status_code == 201
    rule = create_resp.json()
    rule_id = rule["id"]

    get_resp = await client.get(f"/api/v1/routing-rules/{rule_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == rule_id
    assert get_resp.json()["source_channel_name"] == "Test Channel"


async def test_get_routing_rule_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/routing-rules/{fake_id}")
    assert resp.status_code == 404


async def test_update_routing_rule(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/routing-rules",
        json={
            "source_channel_id": "-100888",
            "destination_webhook_url": "https://api.sagemaster.io/deals_idea/aac79d52-1ab9-4d3b-a7ca-125b2f5e0307",
            "payload_version": "V1",
            "webhook_body_template": _DEFAULT_TEMPLATE,
        },
    )
    rule_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/routing-rules/{rule_id}",
        json={"source_channel_name": "Updated Name", "is_active": False},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["source_channel_name"] == "Updated Name"
    assert update_resp.json()["is_active"] is False


async def test_delete_routing_rule(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/routing-rules",
        json={
            "source_channel_id": "-100777",
            "destination_webhook_url": "https://api.sagemaster.io/deals_idea/bbc79d52-1ab9-4d3b-a7ca-125b2f5e0307",
            "payload_version": "V1",
            "webhook_body_template": _DEFAULT_TEMPLATE,
        },
    )
    rule_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/routing-rules/{rule_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/routing-rules/{rule_id}")
    assert get_resp.status_code == 404


async def test_delete_routing_rule_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.delete(f"/api/v1/routing-rules/{fake_id}")
    assert resp.status_code == 404
