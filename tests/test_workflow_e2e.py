"""End-to-end tests for the signal processing workflow pipeline.

Tests the full flow: POST raw signal -> parse (mocked OpenAI) -> route ->
dispatch (mocked webhook) -> persist signal_log.

Uses SQLite + aiosqlite with the same PostgreSQL type compilation overrides
as test_routes.py.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import (
    Base,
    RoutingRuleModel,
    SignalLogModel,
    UserModel,
)
from src.adapters.webhook.dispatcher import WebhookDispatcher
from src.api.deps import Settings, get_current_user, get_db, get_dispatcher, get_settings
from src.api.qstash_auth import verify_qstash_signature
from src.core.models import ParsedSignal, SubscriptionTier, User
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
    subscription_tier=SubscriptionTier.pro,  # pro tier allows 5 destinations
)

CHANNEL_ID = "-1001234567890"

WEBHOOK_URL_1 = "https://app.sagemaster.com/api/webhook/aaa11111-1111-1111-1111-111111111111"
WEBHOOK_URL_2 = "https://app.sagemaster.com/api/webhook/bbb22222-2222-2222-2222-222222222222"
WEBHOOK_URL_3 = "https://app.sagemaster.com/api/webhook/ccc33333-3333-3333-3333-333333333333"

DEFAULT_TEMPLATE = {
    "type": "",
    "assistId": "test-assist-id",
    "source": "",
    "symbol": "",
    "date": "",
}


def _make_valid_parsed_signal(
    symbol: str = "EURUSD",
    direction: str = "long",
) -> ParsedSignal:
    """Return a valid ParsedSignal for mocking the OpenAI parser."""
    return ParsedSignal(
        symbol=symbol,
        direction=direction,
        order_type="market",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profits=[1.1050, 1.1100],
        source_asset_class="forex",
        is_valid_signal=True,
    )


def _make_ignored_parsed_signal() -> ParsedSignal:
    """Return an ignored (invalid) ParsedSignal for news messages."""
    return ParsedSignal(
        symbol="",
        direction="long",
        order_type="market",
        source_asset_class="forex",
        is_valid_signal=False,
        ignore_reason="Message is a news update, not an actionable trade signal",
    )


def _raw_signal_payload(
    user_id: uuid.UUID = SAMPLE_USER_ID,
    channel_id: str = CHANNEL_ID,
    raw_message: str = "EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050\nTP2: 1.1100",
) -> dict:
    """Build a JSON-serialisable dict matching the RawSignal schema."""
    return {
        "user_id": str(user_id),
        "channel_id": channel_id,
        "raw_message": raw_message,
        "message_id": 42,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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
            OPENAI_API_KEY="sk-test-fake-key",
        )

    async def override_qstash_auth():
        return None  # skip signature validation in tests

    # Create a shared mock dispatcher for the test
    test_dispatcher = WebhookDispatcher(timeout=15.0)

    def override_get_dispatcher() -> WebhookDispatcher:
        return test_dispatcher

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[verify_qstash_signature] = override_qstash_auth
    app.dependency_overrides[get_dispatcher] = override_get_dispatcher

    # Seed the test user
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=SAMPLE_USER_ID,
                email="test@example.com",
                password_hash="$2b$12$fakehashedpassword",
                subscription_tier="pro",
            )
        )
        await session.commit()

    yield app, async_session_factory, test_dispatcher

    await test_dispatcher.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_app):
    app, _, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def session_factory(test_app):
    _, factory, _ = test_app
    return factory


@pytest_asyncio.fixture
async def test_dispatcher(test_app):
    _, _, dispatcher = test_app
    return dispatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_routing_rule(
    session_factory,
    user_id: uuid.UUID = SAMPLE_USER_ID,
    channel_id: str = CHANNEL_ID,
    webhook_url: str = WEBHOOK_URL_1,
    symbol_mappings: dict | None = None,
    payload_version: str = "V1",
    webhook_body_template: dict | None = None,
) -> uuid.UUID:
    """Insert a routing rule and return its id."""
    rule_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            RoutingRuleModel(
                id=rule_id,
                user_id=user_id,
                source_channel_id=channel_id,
                destination_webhook_url=webhook_url,
                payload_version=payload_version,
                symbol_mappings=symbol_mappings or {},
                risk_overrides={},
                webhook_body_template=webhook_body_template or DEFAULT_TEMPLATE.copy(),
                is_active=True,
            )
        )
        await session.commit()
    return rule_id


async def _get_signal_logs(
    session_factory, user_id: uuid.UUID = SAMPLE_USER_ID
) -> list[SignalLogModel]:
    """Fetch all signal logs for a given user."""
    async with session_factory() as session:
        result = await session.execute(
            select(SignalLogModel)
            .where(SignalLogModel.user_id == user_id)
            .order_by(SignalLogModel.processed_at)
        )
        return list(result.scalars().all())


def _mock_openai_parser(parsed_signal: ParsedSignal):
    """Return a context manager that patches OpenAISignalParser.parse to return
    the given ParsedSignal."""
    mock_parser_instance = MagicMock()
    mock_parser_instance.parse = AsyncMock(return_value=parsed_signal)
    return patch(
        "src.adapters.openai.OpenAISignalParser",
        return_value=mock_parser_instance,
    )


class _MockHttpxPost:
    """Context manager that patches a WebhookDispatcher's HTTP client.

    The ``as`` value supports ``assert_not_called()`` and ``assert_called()``
    by delegating to the underlying ``AsyncMock``.
    """

    def __init__(self, responses, dispatcher=None):
        if responses is None:
            responses = httpx.Response(200, json={"status": "ok"})

        if isinstance(responses, httpx.Response):
            default_response = responses

            async def _side_effect(url, **kwargs):
                return default_response
        else:
            url_map = responses

            async def _side_effect(url, **kwargs):
                url_str = str(url)
                for key, resp in url_map.items():
                    if key in url_str:
                        return resp
                return httpx.Response(200, json={"status": "ok"})

        self._side_effect = _side_effect
        self._mock_post = AsyncMock(side_effect=_side_effect)
        self._dispatcher = dispatcher
        self._original_client = None

    def __enter__(self):
        if self._dispatcher is not None:
            self._original_client = self._dispatcher._client
            self._dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
            self._dispatcher._client.post = self._mock_post
        return self._mock_post

    def __exit__(self, *args):
        if self._dispatcher is not None and self._original_client is not None:
            self._dispatcher._client = self._original_client


def _mock_httpx_post(
    responses: dict[str, httpx.Response] | httpx.Response | None = None,
    dispatcher: WebhookDispatcher | None = None,
):
    """Return a context manager that patches the WebhookDispatcher so its
    internal httpx client returns canned responses.

    The ``as`` value is an ``AsyncMock`` tracking all POST calls, so tests
    can call ``mock_post.assert_not_called()`` etc.

    Parameters
    ----------
    responses:
        - If a dict, maps URL -> httpx.Response.
        - If a single Response, all POSTs return that response.
        - If None, returns a 200 for all URLs.
    dispatcher:
        The WebhookDispatcher instance to patch. When provided, the mock
        replaces its internal HTTP client.
    """
    return _MockHttpxPost(responses, dispatcher=dispatcher)


# ===========================================================================
# Test 1: Single destination dispatch
# ===========================================================================


async def test_single_destination_dispatch(client, session_factory, test_dispatcher):
    """Full pipeline: parse -> route to 1 webhook -> log success."""
    rule_id = await _seed_routing_rule(session_factory, webhook_url=WEBHOOK_URL_1)

    parsed = _make_valid_parsed_signal()

    with _mock_openai_parser(parsed), _mock_httpx_post(dispatcher=test_dispatcher):
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == "success"
    assert results[0]["routing_rule_id"] == str(rule_id)
    assert results[0]["webhook_payload"] is not None

    # Verify signal_log was persisted
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].routing_rule_id == rule_id
    assert logs[0].webhook_payload is not None


# ===========================================================================
# Test 2: Multi-destination dispatch (CRITICAL MVP feature)
# ===========================================================================


async def test_multi_destination_dispatch(client, session_factory, test_dispatcher):
    """Route 1 signal to 3 different webhook destinations."""
    rule_id_1 = await _seed_routing_rule(
        session_factory, webhook_url=WEBHOOK_URL_1
    )
    rule_id_2 = await _seed_routing_rule(
        session_factory, webhook_url=WEBHOOK_URL_2
    )
    rule_id_3 = await _seed_routing_rule(
        session_factory, webhook_url=WEBHOOK_URL_3
    )

    parsed = _make_valid_parsed_signal()

    with _mock_openai_parser(parsed), _mock_httpx_post(dispatcher=test_dispatcher):
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 3

    # All dispatches should succeed
    for result in results:
        assert result["status"] == "success"

    # Verify each result references the correct routing rule
    returned_rule_ids = {r["routing_rule_id"] for r in results}
    assert returned_rule_ids == {str(rule_id_1), str(rule_id_2), str(rule_id_3)}

    # Verify 3 signal_logs created
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 3

    logged_rule_ids = {log.routing_rule_id for log in logs}
    assert logged_rule_ids == {rule_id_1, rule_id_2, rule_id_3}

    for log in logs:
        assert log.status == "success"
        assert log.webhook_payload is not None


# ===========================================================================
# Test 3: Ignored signal flow
# ===========================================================================


async def test_ignored_signal_flow(client, session_factory, test_dispatcher):
    """News/invalid messages should be logged as 'ignored' with no webhook dispatch."""
    await _seed_routing_rule(session_factory)

    parsed = _make_ignored_parsed_signal()

    with _mock_openai_parser(parsed) as mock_parser, \
         _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(
                raw_message="Markets are volatile today, stay safe!"
            ),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == "ignored"
    assert results[0]["routing_rule_id"] is None
    assert results[0]["error_message"] is not None

    # No webhook should have been dispatched
    mock_post.assert_not_called()

    # Signal log should be created with status=ignored
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 1
    assert logs[0].status == "ignored"
    assert logs[0].routing_rule_id is None
    assert logs[0].error_message is not None


# ===========================================================================
# Test 4: Webhook failure handling
# ===========================================================================


async def test_webhook_failure_handling(client, session_factory, test_dispatcher):
    """When webhook returns 500, signal_log should have status='failed'."""
    rule_id = await _seed_routing_rule(session_factory, webhook_url=WEBHOOK_URL_1)

    parsed = _make_valid_parsed_signal()

    error_response = httpx.Response(
        500,
        text="Internal Server Error",
        request=httpx.Request("POST", WEBHOOK_URL_1),
    )

    with _mock_openai_parser(parsed), _mock_httpx_post(error_response, dispatcher=test_dispatcher):
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == "failed"
    assert "500" in results[0]["error_message"]

    # Verify signal_log reflects the failure
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert logs[0].error_message is not None
    assert "500" in logs[0].error_message
    assert logs[0].routing_rule_id == rule_id


# ===========================================================================
# Test 5: Symbol mapping in multi-destination
# ===========================================================================


async def test_symbol_mapping_in_multi_destination(client, session_factory, test_dispatcher):
    """Rule 1 has no mapping (symbol stays GOLD), Rule 2 maps GOLD -> XAUUSD.

    Each webhook should receive the correctly mapped symbol in its payload.
    """
    # Rule 1: no symbol mapping — symbol stays as-is
    rule_id_1 = await _seed_routing_rule(
        session_factory,
        webhook_url=WEBHOOK_URL_1,
        symbol_mappings={},
    )

    # Rule 2: maps GOLD -> XAUUSD
    rule_id_2 = await _seed_routing_rule(
        session_factory,
        webhook_url=WEBHOOK_URL_2,
        symbol_mappings={"GOLD": "XAUUSD"},
    )

    parsed = _make_valid_parsed_signal(symbol="GOLD")

    # Track what payloads were sent to each webhook
    captured_payloads: dict[str, dict] = {}

    async def _capture_post(url, **kwargs):
        url_str = str(url)
        captured_payloads[url_str] = kwargs.get("json", {})
        return httpx.Response(200, json={"status": "ok"})

    # Patch the test dispatcher's client to capture payloads
    original_client = test_dispatcher._client
    test_dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    test_dispatcher._client.post = AsyncMock(side_effect=_capture_post)

    with _mock_openai_parser(parsed):
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(raw_message="GOLD BUY now"),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2

    for result in results:
        assert result["status"] == "success"

    # Verify the payloads sent to each webhook have the right symbol
    assert WEBHOOK_URL_1 in captured_payloads
    assert WEBHOOK_URL_2 in captured_payloads

    # Rule 1 (no mapping): symbol should remain GOLD
    assert captured_payloads[WEBHOOK_URL_1]["symbol"] == "GOLD"

    # Rule 2 (GOLD -> XAUUSD mapping): symbol should be XAUUSD
    assert captured_payloads[WEBHOOK_URL_2]["symbol"] == "XAUUSD"

    # Verify signal logs reflect the correct payloads
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 2

    log_by_rule = {log.routing_rule_id: log for log in logs}

    assert log_by_rule[rule_id_1].webhook_payload["symbol"] == "GOLD"
    assert log_by_rule[rule_id_2].webhook_payload["symbol"] == "XAUUSD"

    # Restore original client
    test_dispatcher._client = original_client


# ===========================================================================
# Test 6: No routing rules configured
# ===========================================================================


async def test_no_routing_rules_returns_empty(client, session_factory, test_dispatcher):
    """When no routing rules match the channel, return empty list and log as ignored."""
    # Don't seed any routing rules
    parsed = _make_valid_parsed_signal()

    with _mock_openai_parser(parsed), _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert results == []

    mock_post.assert_not_called()

    # An "ignored" log should still be created
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 1
    assert logs[0].status == "ignored"
    assert "No routing rules" in logs[0].error_message


# ===========================================================================
# Test 7: enabled_actions filtering
# ===========================================================================


async def test_enabled_actions_filters_disabled_action(client, session_factory, test_dispatcher):
    """When enabled_actions excludes the signal's action, dispatch should be ignored."""
    # Create rule that only allows entry actions (no close_position)
    await _seed_routing_rule(
        session_factory,
        webhook_url=WEBHOOK_URL_1,
        webhook_body_template={
            "type": "",
            "assistId": "test-assist",
            "source": "",
            "symbol": "",
            "date": "",
        },
    )
    # Update the rule to set enabled_actions (excluding close)
    async with session_factory() as session:
        from sqlalchemy import update
        await session.execute(
            update(RoutingRuleModel)
            .where(RoutingRuleModel.user_id == SAMPLE_USER_ID)
            .values(enabled_actions=[
                "start_long_market_deal",
                "start_short_market_deal",
            ])
        )
        await session.commit()

    # Send a close_position signal
    parsed = ParsedSignal(
        action="close_position",
        symbol="EURUSD",
        direction="long",
        order_type="market",
        source_asset_class="forex",
        is_valid_signal=True,
    )

    with _mock_openai_parser(parsed), _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == "ignored"
    assert "disabled" in results[0]["error_message"]

    # No webhook should have been dispatched
    mock_post.assert_not_called()

    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 1
    assert logs[0].status == "ignored"


async def test_enabled_actions_null_allows_all(client, session_factory, test_dispatcher):
    """When enabled_actions is None (default), all actions should dispatch normally."""
    await _seed_routing_rule(
        session_factory,
        webhook_url=WEBHOOK_URL_1,
        # Default template, enabled_actions defaults to None
    )

    parsed = _make_valid_parsed_signal()

    with _mock_openai_parser(parsed), _mock_httpx_post(dispatcher=test_dispatcher):
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == "success"
