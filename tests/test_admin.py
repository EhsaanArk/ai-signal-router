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

from src.adapters.db.models import Base, GlobalSettingModel, RoutingRuleModel, SignalLogModel, UserModel
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
        # Seed global setting
        session.add(GlobalSettingModel(
            key="backfill_max_age_seconds",
            value="60",
            description="Test setting",
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


# ---------------------------------------------------------------------------
# Parser Manager
# ---------------------------------------------------------------------------


async def test_get_prompt_returns_default(admin_client):
    """GET /parser/prompt returns hardcoded default when no DB row exists."""
    resp = await admin_client.get("/api/v1/admin/parser/prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 0
    assert data["config_key"] == "system_prompt"
    assert data["change_note"] == "Hardcoded default"
    assert "trading signal parser" in data["system_prompt"].lower()


async def test_update_prompt_creates_version(admin_client):
    """PUT /parser/prompt creates a new version."""
    resp = await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={
            "system_prompt": "You are a test parser. Parse signals.",
            "change_note": "Test update",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert data["is_active"] is True
    assert data["system_prompt"] == "You are a test parser. Parse signals."
    assert data["change_note"] == "Test update"
    assert data["changed_by_email"] == "admin@test.com"


async def test_get_prompt_returns_db_version(admin_client):
    """After saving, GET returns the DB version, not the hardcoded default."""
    # Save a prompt first
    await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={"system_prompt": "Custom prompt for testing purposes."},
    )
    resp = await admin_client.get("/api/v1/admin/parser/prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert data["system_prompt"] == "Custom prompt for testing purposes."


async def test_prompt_history(admin_client):
    """GET /parser/prompt/history returns version history."""
    # Create two versions
    await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={"system_prompt": "First version of the prompt text."},
    )
    await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={"system_prompt": "Second version of the prompt text."},
    )

    resp = await admin_client.get("/api/v1/admin/parser/prompt/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # Ordered by version desc
    assert data["items"][0]["version"] == 2
    assert data["items"][1]["version"] == 1


async def test_revert_prompt(admin_client):
    """POST /parser/prompt/revert creates new version with old content."""
    # Create two versions
    r1 = await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={"system_prompt": "Original prompt for this test case."},
    )
    version_1_id = r1.json()["id"]

    await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={"system_prompt": "Updated prompt that replaces original."},
    )

    # Revert to version 1
    resp = await admin_client.post(
        f"/api/v1/admin/parser/prompt/revert/{version_1_id}",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 3  # New version created
    assert data["system_prompt"] == "Original prompt for this test case."
    assert "Reverted from version 1" in data["change_note"]


async def test_revert_invalid_version(admin_client):
    """POST /parser/prompt/revert with bad ID returns 404."""
    fake_id = uuid.uuid4()
    resp = await admin_client.post(
        f"/api/v1/admin/parser/prompt/revert/{fake_id}",
    )
    assert resp.status_code == 404


async def test_get_model_returns_defaults(admin_client):
    """GET /parser/model returns defaults when no DB row."""
    resp = await admin_client.get("/api/v1/admin/parser/model")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_name"] == "gpt-4o-mini"
    assert data["temperature"] == 0.0
    assert data["version"] == 0


async def test_update_model_config(admin_client):
    """PUT /parser/model saves new model configuration."""
    resp = await admin_client.put(
        "/api/v1/admin/parser/model",
        json={
            "model_name": "gpt-4o",
            "temperature": 0.2,
            "change_note": "Testing gpt-4o",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_name"] == "gpt-4o"
    assert data["temperature"] == 0.2
    assert data["version"] == 1
    assert data["changed_by_email"] == "admin@test.com"


async def test_update_model_invalid_name(admin_client):
    """PUT /parser/model rejects invalid model names."""
    resp = await admin_client.put(
        "/api/v1/admin/parser/model",
        json={"model_name": "gpt-5", "temperature": 0.0},
    )
    assert resp.status_code == 422


async def test_update_model_invalid_temperature(admin_client):
    """PUT /parser/model rejects out-of-range temperature."""
    resp = await admin_client.put(
        "/api/v1/admin/parser/model",
        json={"model_name": "gpt-4o-mini", "temperature": 1.5},
    )
    assert resp.status_code == 422


async def test_update_prompt_too_short(admin_client):
    """PUT /parser/prompt rejects prompts shorter than 10 chars."""
    resp = await admin_client.put(
        "/api/v1/admin/parser/prompt",
        json={"system_prompt": "short"},
    )
    assert resp.status_code == 422


async def test_non_admin_parser_endpoints(normal_client):
    """Non-admin gets 403 on all parser endpoints."""
    endpoints = [
        ("GET", "/api/v1/admin/parser/prompt"),
        ("PUT", "/api/v1/admin/parser/prompt"),
        ("GET", "/api/v1/admin/parser/prompt/history"),
        ("GET", "/api/v1/admin/parser/model"),
        ("PUT", "/api/v1/admin/parser/model"),
        ("GET", "/api/v1/admin/settings"),
        ("PUT", "/api/v1/admin/settings"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = await normal_client.get(path)
        else:
            resp = await normal_client.put(path, json={})
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}"


# ---------------------------------------------------------------------------
# Global Settings tests
# ---------------------------------------------------------------------------


async def test_get_global_settings(admin_client):
    """Admin can fetch all global settings."""
    resp = await admin_client.get("/api/v1/admin/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    setting = next(s for s in data if s["key"] == "backfill_max_age_seconds")
    assert setting["value"] == "60"
    assert setting["description"] is not None


async def test_update_global_setting(admin_client):
    """Admin can update a known setting with valid value."""
    resp = await admin_client.put(
        "/api/v1/admin/settings",
        json={"settings": {"backfill_max_age_seconds": "90"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    setting = next(s for s in data if s["key"] == "backfill_max_age_seconds")
    assert setting["value"] == "90"
    assert setting["updated_by"] == "admin@test.com"


async def test_update_setting_rejects_invalid_value(admin_client):
    """Out-of-range values are rejected with 422."""
    resp = await admin_client.put(
        "/api/v1/admin/settings",
        json={"settings": {"backfill_max_age_seconds": "9999"}},
    )
    assert resp.status_code == 422


async def test_update_setting_rejects_unknown_key(admin_client):
    """Unknown setting keys are rejected."""
    resp = await admin_client.put(
        "/api/v1/admin/settings",
        json={"settings": {"nonexistent_key": "123"}},
    )
    assert resp.status_code == 422
