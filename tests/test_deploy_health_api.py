"""Tests for public/admin deploy health endpoint data exposure boundaries."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
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
from src.adapters.redis.client import InMemoryCacheAdapter, InMemorySessionStore
from src.adapters.telegram.deploy_snapshot import SNAPSHOT_KEY
from src.api.deps import Settings, _trusted_proxy_networks, get_admin_user, get_db, get_settings
from src.core.models import SubscriptionTier, User
from src.main import create_app


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
SAMPLE_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest_asyncio.fixture
async def test_app():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    old_db_url = os.environ.get("DATABASE_URL")
    old_trusted_proxies = os.environ.get("TRUSTED_PROXY_IPS")
    os.environ["DATABASE_URL"] = TEST_DB_URL
    os.environ["TRUSTED_PROXY_IPS"] = "127.0.0.1"
    _trusted_proxy_networks.cache_clear()

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
        return Settings(
            DATABASE_URL=TEST_DB_URL,
            JWT_SECRET_KEY="test-secret",
            LOCAL_MODE=True,
            REDIS_URL="redis://localhost:6379/0",
        )

    async def override_get_admin_user() -> User:
        return User(
            id=SAMPLE_USER_ID,
            email="admin@example.com",
            password_hash="x",
            subscription_tier=SubscriptionTier.elite,
            is_admin=True,
            created_at=datetime.now(timezone.utc),
        )

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_admin_user] = override_get_admin_user

    app.state.cache = InMemoryCacheAdapter()
    app.state.session_store = InMemorySessionStore()

    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=SAMPLE_USER_ID,
                email="admin@example.com",
                password_hash="x",
                is_admin=True,
                subscription_tier="elite",
            )
        )
        session.add(
            TelegramSessionModel(
                user_id=SAMPLE_USER_ID,
                phone_number="+447700900123",
                session_string_encrypted="encrypted",
                is_active=True,
            )
        )
        session.add(
            RoutingRuleModel(
                user_id=SAMPLE_USER_ID,
                source_channel_id="1001",
                destination_webhook_url="https://example.com/webhook",
                payload_version="V2",
                webhook_body_template={"assistId": "a", "type": "", "source": "", "symbol": "", "date": ""},
                is_active=True,
            )
        )
        session.add(
            SignalLogModel(
                user_id=SAMPLE_USER_ID,
                channel_id="1001",
                message_id=10,
                raw_message="EURUSD buy",
                status="success",
            )
        )
        await session.commit()

    await app.state.cache.set(
        SNAPSHOT_KEY,
        json.dumps(
            {
                "active_sessions": 1,
                "connected_listeners": 1,
                "channels_monitored": 1,
                "user_ids": [str(SAMPLE_USER_ID)],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        ttl_seconds=600,
    )

    with patch(
        "src.adapters.db.session.get_async_session_factory",
        return_value=async_session_factory,
    ):
        yield app

    await engine.dispose()
    if old_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old_db_url
    if old_trusted_proxies is None:
        os.environ.pop("TRUSTED_PROXY_IPS", None)
    else:
        os.environ["TRUSTED_PROXY_IPS"] = old_trusted_proxies
    _trusted_proxy_networks.cache_clear()


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_public_deploy_health_redacts_user_identifiers(client: AsyncClient):
    unique_ip = f"203.0.113.{(uuid.uuid4().int % 250) + 1}"
    response = await client.get(
        "/health/deploy",
        headers={"X-Forwarded-For": unique_ip},
    )
    assert response.status_code == 200
    payload = response.json()

    assert "user_ids" not in payload["current"]
    assert "user_ids" not in (payload["pre_deploy_snapshot"] or {})
    assert "lost_user_ids" not in (payload["comparison"] or {})
    assert "new_user_ids" not in (payload["comparison"] or {})


@pytest.mark.asyncio
async def test_admin_deploy_health_contains_detailed_identifiers(client: AsyncClient):
    response = await client.get("/api/v1/admin/deploy-health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["current"]["user_ids"] == [str(SAMPLE_USER_ID)]
