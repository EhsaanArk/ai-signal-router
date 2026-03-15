"""Tests for the development signal injection endpoint (/api/dev/inject-signal).

Uses SQLite + aiosqlite with PostgreSQL type compilation overrides,
following the same infrastructure as test_routes.py.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import Base, RoutingRuleModel, UserModel
from src.adapters.webhook.dispatcher import WebhookDispatcher
from src.api.deps import Settings, get_current_user, get_db, get_dispatcher, get_settings
from src.core.models import (
    DispatchResult,
    ParsedSignal,
    SubscriptionTier,
    User,
)

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

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SAMPLE_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_RULE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_WEBHOOK_URL = (
    "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
)

SAMPLE_USER = User(
    id=SAMPLE_USER_ID,
    email="test@example.com",
    password_hash="$2b$12$fakehashedpassword",
    subscription_tier=SubscriptionTier.free,
)

SAMPLE_PARSED_SIGNAL = ParsedSignal(
    symbol="EURUSD",
    direction="long",
    order_type="market",
    entry_price=1.1000,
    stop_loss=1.0950,
    take_profits=[1.1050, 1.1100],
    source_asset_class="forex",
    is_valid_signal=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_engine_and_factory():
    """Create a fresh in-memory SQLite engine + async session factory."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


def _override_deps(app, session_factory):
    """Wire up dependency overrides on the given FastAPI app."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
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
            LOCAL_MODE=True,
        )

    test_dispatcher = WebhookDispatcher.__new__(WebhookDispatcher)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = httpx.Response(200, json={"status": "ok"})
    test_dispatcher._client = mock_client

    def override_get_dispatcher() -> WebhookDispatcher:
        return test_dispatcher

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_dispatcher] = override_get_dispatcher


async def _seed_user(session_factory, user_id=DEV_USER_ID):
    """Insert a user row so that foreign-key constraints are satisfied."""
    async with session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@test.com",
                password_hash="$2b$12$fakehashedpassword",
            )
        )
        await session.commit()


async def _seed_routing_rule(session_factory, user_id=DEV_USER_ID, channel_id="dev-channel"):
    """Insert an active routing rule for the given user/channel."""
    async with session_factory() as session:
        session.add(
            RoutingRuleModel(
                id=SAMPLE_RULE_ID,
                user_id=user_id,
                source_channel_id=channel_id,
                source_channel_name="Test Channel",
                destination_webhook_url=SAMPLE_WEBHOOK_URL,
                payload_version="V1",
                symbol_mappings={},
                risk_overrides={},
                webhook_body_template={
                    "type": "",
                    "assistId": "test-assist-id",
                    "source": "",
                    "symbol": "",
                    "date": "",
                },
                is_active=True,
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def dev_app():
    """Create a test app with LOCAL_MODE=true so the dev router is mounted."""
    with patch.dict(os.environ, {"LOCAL_MODE": "true"}, clear=False):
        from src.main import create_app

        app = create_app()

    engine, factory = await _make_engine_and_factory()
    _override_deps(app, factory)
    await _seed_user(factory)

    yield app, factory

    await engine.dispose()


@pytest_asyncio.fixture
async def dev_client(dev_app):
    app, _ = dev_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def dev_app_with_rule(dev_app):
    """dev_app with a seeded routing rule for the default dev-channel."""
    app, factory = dev_app
    await _seed_routing_rule(factory)
    return app, factory


@pytest_asyncio.fixture
async def dev_client_with_rule(dev_app_with_rule):
    app, _ = dev_app_with_rule
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# Tests
# ===========================================================================


class TestInjectSignalEndpoint:
    """POST /api/dev/inject-signal — basic request/response tests."""

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_inject_signal_creates_raw_signal_and_processes(
        self,
        MockParser,
        dev_client_with_rule: AsyncClient,
    ):
        """The endpoint accepts text + channel_id, creates a RawSignal, and
        invokes process_signal (requires a routing rule to reach the parser)."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client_with_rule.post(
            "/api/dev/inject-signal",
            json={"text": "BUY EURUSD @ 1.1000", "channel_id": "dev-channel"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "raw_signal" in data
        assert data["raw_signal"]["raw_message"] == "BUY EURUSD @ 1.1000"
        assert data["raw_signal"]["channel_id"] == "dev-channel"
        assert "results" in data

        # Parser was called (routing rule exists, so pipeline reaches parser)
        mock_parser_instance.parse.assert_called_once()

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_inject_signal_uses_default_channel_id(
        self,
        MockParser,
        dev_client: AsyncClient,
    ):
        """When channel_id is omitted, it defaults to 'dev-channel'."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client.post(
            "/api/dev/inject-signal",
            json={"text": "BUY EURUSD"},
        )

        assert resp.status_code == 200
        assert resp.json()["raw_signal"]["channel_id"] == "dev-channel"

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_inject_signal_uses_dev_user_id_by_default(
        self,
        MockParser,
        dev_client: AsyncClient,
    ):
        """The default user_id is the fixed DEV user ID."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client.post(
            "/api/dev/inject-signal",
            json={"text": "BUY EURUSD"},
        )

        assert resp.status_code == 200
        assert resp.json()["raw_signal"]["user_id"] == str(DEV_USER_ID)


class TestSuccessfulInjection:
    """Full pipeline: parse -> route -> dispatch with mocked externals."""

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_full_pipeline_with_routing_rule(
        self,
        MockParser,
        dev_client_with_rule: AsyncClient,
    ):
        """With a seeded routing rule, the full pipeline executes and
        dispatches to the webhook."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client_with_rule.post(
            "/api/dev/inject-signal",
            json={"text": "EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050"},
        )

        assert resp.status_code == 200
        data = resp.json()

        # Should have exactly one dispatch result
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["status"] == "success"
        assert result["routing_rule_id"] == str(SAMPLE_RULE_ID)
        assert result["webhook_payload"] is not None

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_pipeline_returns_raw_signal_in_response(
        self,
        MockParser,
        dev_client_with_rule: AsyncClient,
    ):
        """The response includes the full RawSignal that was created."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client_with_rule.post(
            "/api/dev/inject-signal",
            json={"text": "BUY GOLD NOW", "channel_id": "dev-channel"},
        )

        assert resp.status_code == 200
        raw = resp.json()["raw_signal"]
        assert raw["raw_message"] == "BUY GOLD NOW"
        assert raw["channel_id"] == "dev-channel"
        assert raw["message_id"] == 0
        assert "timestamp" in raw


class TestInjectionNoRoutingRules:
    """Injection when no routing rules are configured for the channel."""

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_no_routing_rules_returns_empty_results(
        self,
        MockParser,
        dev_client: AsyncClient,
    ):
        """When there are no routing rules for the channel, the pipeline
        returns an empty results list and does not dispatch."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client.post(
            "/api/dev/inject-signal",
            json={"text": "BUY EURUSD @ 1.1000", "channel_id": "no-rules-channel"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_no_routing_rules_still_returns_raw_signal(
        self,
        MockParser,
        dev_client: AsyncClient,
    ):
        """Even with no routing rules, the raw_signal is still returned."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = SAMPLE_PARSED_SIGNAL
        MockParser.return_value = mock_parser_instance

        resp = await dev_client.post(
            "/api/dev/inject-signal",
            json={"text": "SELL GBPUSD"},
        )

        assert resp.status_code == 200
        assert resp.json()["raw_signal"]["raw_message"] == "SELL GBPUSD"


class TestDevEndpointAvailability:
    """Verify the dev router is mounted/unmounted based on LOCAL_MODE."""

    async def test_dev_endpoint_available_when_local_mode_true(
        self, dev_client: AsyncClient,
    ):
        """When LOCAL_MODE=true, /api/dev/inject-signal should be reachable
        (not 404). We send an invalid body to confirm the route exists --
        we expect 422 (validation error), NOT 404."""
        resp = await dev_client.post(
            "/api/dev/inject-signal",
            json={},
        )
        # 422 = route exists but body validation failed (missing 'text')
        assert resp.status_code == 422

    async def test_dev_endpoint_not_available_when_local_mode_false(self):
        """When LOCAL_MODE=false, the dev router must NOT be mounted,
        resulting in a 404 for /api/dev/inject-signal."""
        with patch.dict(os.environ, {"LOCAL_MODE": "false"}, clear=False):
            from src.main import create_app

            app = create_app()

        engine, factory = await _make_engine_and_factory()
        _override_deps(app, factory)

        # Override LOCAL_MODE in settings as well
        def override_get_settings() -> Settings:
            return Settings(
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY="test-secret",
                LOCAL_MODE=False,
            )

        app.dependency_overrides[get_settings] = override_get_settings

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/dev/inject-signal",
                json={"text": "BUY EURUSD"},
            )
            assert resp.status_code == 404

        await engine.dispose()


class TestInvalidSignalHandling:
    """Edge cases: invalid signals, parse failures."""

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_invalid_signal_returns_ignored_result(
        self,
        MockParser,
        dev_client_with_rule: AsyncClient,
    ):
        """When the parser returns is_valid_signal=False, the pipeline
        returns an 'ignored' result without dispatching.
        Requires a routing rule so the pipeline reaches the parser."""
        invalid_parsed = ParsedSignal(
            symbol="",
            direction="long",
            is_valid_signal=False,
            ignore_reason="Not a trading signal",
        )
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.return_value = invalid_parsed
        MockParser.return_value = mock_parser_instance

        resp = await dev_client_with_rule.post(
            "/api/dev/inject-signal",
            json={"text": "Hello everyone, good morning!"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "ignored"
        assert data["results"][0]["error_message"] == "Not a trading signal"

    @patch("src.adapters.openai.OpenAISignalParser")
    async def test_parse_failure_returns_422(
        self,
        MockParser,
        dev_client_with_rule: AsyncClient,
    ):
        """When the OpenAI parser raises an exception, the endpoint
        returns 422. Requires a routing rule so the pipeline reaches
        the parser."""
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse.side_effect = RuntimeError("OpenAI API down")
        MockParser.return_value = mock_parser_instance

        resp = await dev_client_with_rule.post(
            "/api/dev/inject-signal",
            json={"text": "BUY EURUSD"},
        )

        assert resp.status_code == 422
        assert "Failed to parse signal" in resp.json()["detail"]
