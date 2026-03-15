"""Tests for admin API endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import Base, RoutingRuleModel, SignalLogModel, UserModel
from src.api.deps import Settings, get_current_user, get_db, get_settings
from src.core.models import SubscriptionTier, User
from src.main import create_app


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
NORMAL_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

ADMIN_USER = User(
    id=ADMIN_USER_ID,
    email="admin@test.com",
    password_hash="$2b$12$fakehashedpassword",
    subscription_tier=SubscriptionTier.pro,
    is_admin=True,
)
NORMAL_USER = User(
    id=NORMAL_USER_ID,
    email="user@test.com",
    password_hash="$2b$12$fakehashedpassword",
    subscription_tier=SubscriptionTier.free,
    is_admin=False,
)


@pytest_asyncio.fixture
async def admin_app():
    """Create app with admin user override."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_settings() -> Settings:
        return Settings(DATABASE_URL=TEST_DB_URL, JWT_SECRET_KEY="test", LOCAL_MODE=False)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    from src.adapters.redis.client import InMemoryCacheAdapter, InMemorySessionStore
    app.state.cache = InMemoryCacheAdapter()
    app.state.session_store = InMemorySessionStore()

    # Seed users
    async with factory() as session:
        session.add(UserModel(
            id=ADMIN_USER_ID, email="admin@test.com",
            password_hash="$2b$12$fake", subscription_tier="pro",
            is_admin=True,
        ))
        session.add(UserModel(
            id=NORMAL_USER_ID, email="user@test.com",
            password_hash="$2b$12$fake", subscription_tier="free",
        ))
        # Add a routing rule for the normal user
        session.add(RoutingRuleModel(
            user_id=NORMAL_USER_ID,
            source_channel_id="-100123",
            destination_webhook_url="https://example.com/hook",
            payload_version="V1",
            webhook_body_template={"type": "", "assistId": "test", "source": "", "symbol": "", "date": ""},
        ))
        # Add a signal log
        session.add(SignalLogModel(
            user_id=NORMAL_USER_ID,
            raw_message="BUY GOLD",
            status="success",
            channel_id="-100123",
            message_id=1,
        ))
        await session.commit()

    yield app, factory

    await engine.dispose()


@pytest_asyncio.fixture
async def admin_client(admin_app):
    app, _ = admin_app
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def normal_client(admin_app):
    app, _ = admin_app
    app.dependency_overrides[get_current_user] = lambda: NORMAL_USER
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

async def test_non_admin_gets_403(normal_client):
    """Non-admin user should get 403 on all admin endpoints."""
    endpoints = [
        ("GET", "/api/v1/admin/users"),
        ("GET", f"/api/v1/admin/users/{NORMAL_USER_ID}"),
        ("PATCH", f"/api/v1/admin/users/{NORMAL_USER_ID}"),
        ("GET", "/api/v1/admin/signals"),
        ("GET", "/api/v1/admin/signals/stats"),
        ("GET", "/api/v1/admin/health"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = await normal_client.get(path)
        else:
            resp = await normal_client.patch(path, json={})
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}"


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

async def test_admin_list_users(admin_client):
    """Admin can list all users."""
    resp = await admin_client.get("/api/v1/admin/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    emails = {u["email"] for u in data["items"]}
    assert "admin@test.com" in emails
    assert "user@test.com" in emails


async def test_admin_list_users_search(admin_client):
    """Admin can search users by email."""
    resp = await admin_client.get("/api/v1/admin/users?search=admin")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "admin@test.com"


async def test_admin_get_user_detail(admin_client):
    """Admin can view user detail with rules and signals."""
    resp = await admin_client.get(f"/api/v1/admin/users/{NORMAL_USER_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@test.com"
    assert data["rule_count"] == 1
    assert len(data["routing_rules"]) == 1
    assert len(data["recent_signals"]) == 1


async def test_admin_update_user_tier(admin_client):
    """Admin can change a user's tier."""
    resp = await admin_client.patch(
        f"/api/v1/admin/users/{NORMAL_USER_ID}",
        json={"subscription_tier": "pro"},
    )
    assert resp.status_code == 200
    assert resp.json()["subscription_tier"] == "pro"


async def test_admin_disable_user(admin_client):
    """Admin can disable a user."""
    resp = await admin_client.patch(
        f"/api/v1/admin/users/{NORMAL_USER_ID}",
        json={"is_disabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["is_disabled"] is True


async def test_admin_update_invalid_tier(admin_client):
    """Invalid tier should return 422."""
    resp = await admin_client.patch(
        f"/api/v1/admin/users/{NORMAL_USER_ID}",
        json={"subscription_tier": "invalid"},
    )
    assert resp.status_code == 422


async def test_admin_user_not_found(admin_client):
    """Non-existent user should return 404."""
    fake_id = uuid.uuid4()
    resp = await admin_client.get(f"/api/v1/admin/users/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Global signals
# ---------------------------------------------------------------------------

async def test_admin_list_signals(admin_client):
    """Admin can list all signals across users."""
    resp = await admin_client.get("/api/v1/admin/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["user_email"] == "user@test.com"


async def test_admin_list_signals_filter_status(admin_client):
    """Admin can filter signals by status."""
    resp = await admin_client.get("/api/v1/admin/signals?status=success")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "success"


async def test_admin_signal_stats(admin_client):
    """Admin can get signal stats."""
    resp = await admin_client.get("/api/v1/admin/signals/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_today" in data
    assert "success_rate_24h" in data
    assert "top_failing_channels" in data


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

async def test_admin_health(admin_client):
    """Admin can get system health stats."""
    resp = await admin_client.get("/api/v1/admin/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == 2
    assert "active_routing_rules" in data
    assert "success_rate_24h" in data
    assert "signals_today" in data
