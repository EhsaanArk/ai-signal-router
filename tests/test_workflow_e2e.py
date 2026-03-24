"""End-to-end tests for the signal processing workflow pipeline.

Tests the full flow: POST raw signal -> parse (mocked OpenAI) -> route ->
dispatch (mocked webhook) -> persist signal_log.

Uses SQLite + aiosqlite with the same PostgreSQL type compilation overrides
as test_routes.py.
"""

from __future__ import annotations

import asyncio
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
    MarketplaceProviderModel,
    MarketplaceSubscriptionModel,
    RoutingRuleModel,
    SignalLogModel,
    UserModel,
)
from src.adapters.webhook.dispatcher import WebhookDispatcher
from src.api.deps import Settings, get_current_user, get_db, get_dispatcher, get_settings
from src.api.qstash_auth import verify_qstash_signature
from src.core.models import DispatchJob, ParsedSignal, RawSignalMeta, SubscriptionTier, User
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
    destination_type: str = "sagemaster_forex",
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
                destination_type=destination_type,
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


async def test_concurrent_duplicate_inflight_only_one_dispatches(
    client, session_factory, test_dispatcher,
):
    """Concurrent identical messages should process once when lock rejects in-flight duplicate."""
    await _seed_routing_rule(session_factory, webhook_url=WEBHOOK_URL_1)
    parsed = _make_valid_parsed_signal()

    lock_mock = AsyncMock(side_effect=[True, False])
    payload = _raw_signal_payload()

    with (
        patch("src.api.workflow._acquire_message_lock", lock_mock),
        _mock_openai_parser(parsed),
        _mock_httpx_post(dispatcher=test_dispatcher) as mock_post,
    ):
        resp1, resp2 = await asyncio.gather(
            client.post("/api/workflow/process-signal", json=payload),
            client.post("/api/workflow/process-signal", json=payload),
        )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    bodies = [resp1.json(), resp2.json()]
    assert any(body == [] for body in bodies)
    assert any(body and body[0]["status"] == "success" for body in bodies)

    # Only one dispatch attempt should reach outbound webhook layer.
    assert mock_post.call_count == 1


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
    """When no routing rules match the channel, return empty list without calling OpenAI."""
    # Don't seed any routing rules
    parsed = _make_valid_parsed_signal()

    with _mock_openai_parser(parsed) as mock_parser_cls, \
         _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert results == []

    mock_post.assert_not_called()
    # OpenAI parser should NOT even be instantiated when no routing rules exist
    mock_parser_cls.assert_not_called()

    # No log entry should be created (skip silently to save resources)
    logs = await _get_signal_logs(session_factory)
    assert len(logs) == 0


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


# ---------------------------------------------------------------------------
# Asset class mismatch filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asset_class_mismatch_ignores_signal(
    client, session_factory, test_dispatcher,
):
    """A commodities signal (XAUUSD) sent to a crypto destination should be
    filtered out as 'ignored' with an asset class mismatch reason."""
    crypto_template = {
        "type": "start_deal",
        "aiAssistId": "test-crypto-assist",
        "exchange": "binance",
        "tradeSymbol": "{{ticker}}",
        "eventSymbol": "{{ticker}}",
        "price": "{{close}}",
        "date": "{{time}}",
    }
    await _seed_routing_rule(
        session_factory,
        webhook_body_template=crypto_template,
        destination_type="sagemaster_crypto",
    )

    # AI parses "Buy gold" as XAUUSD / commodities
    parsed = ParsedSignal(
        symbol="XAUUSD",
        direction="long",
        order_type="market",
        entry_price=2350.0,
        source_asset_class="commodities",
        is_valid_signal=True,
    )

    with _mock_openai_parser(parsed), _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(raw_message="Buy gold"),
        )

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == "ignored"
    assert "commodities" in results[0]["error_message"]
    assert "sagemaster_crypto" in results[0]["error_message"]
    # Webhook should NOT have been called
    mock_post.assert_not_called()


# ===========================================================================
# Test: Two-stage dispatch — Stage 2 (dispatch-signal endpoint)
# ===========================================================================


SUBSCRIBER_USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.mark.asyncio
async def test_dispatch_signal_stage2_endpoint(
    client, session_factory, test_dispatcher,
):
    """Two-stage dispatch Stage 2: POST a DispatchJob to /api/workflow/dispatch-signal
    and verify webhook dispatch + signal_log creation."""
    rule_id = await _seed_routing_rule(session_factory, webhook_url=WEBHOOK_URL_1)

    parsed = _make_valid_parsed_signal()
    meta = RawSignalMeta(
        user_id=SAMPLE_USER_ID,
        channel_id=CHANNEL_ID,
        message_id=999,
        raw_message="EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050",
    )
    job = DispatchJob(
        parsed_signal=parsed,
        routing_rule_id=rule_id,
        raw_signal_meta=meta,
    )

    with _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp = await client.post(
            "/api/workflow/dispatch-signal",
            json=job.model_dump(mode="json"),
        )

    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "success"
    assert result["routing_rule_id"] == str(rule_id)

    # Verify signal_log was created
    logs = await _get_signal_logs(session_factory)
    assert len(logs) >= 1
    stage2_log = next((l for l in logs if l.routing_rule_id == rule_id), None)
    assert stage2_log is not None
    assert stage2_log.status == "success"
    assert stage2_log.source_type == "telegram"

    # Verify webhook was called
    mock_post.assert_called()


@pytest.mark.asyncio
async def test_dispatch_signal_stage2_dedup(
    client, session_factory, test_dispatcher,
):
    """Stage 2 dedup: if a signal_log already exists for this rule+message,
    return 'ignored' without dispatching."""
    rule_id = await _seed_routing_rule(session_factory, webhook_url=WEBHOOK_URL_1)

    # First dispatch — should succeed
    parsed = _make_valid_parsed_signal()
    meta = RawSignalMeta(
        user_id=SAMPLE_USER_ID,
        channel_id=CHANNEL_ID,
        message_id=888,
        raw_message="EURUSD BUY",
    )
    job = DispatchJob(parsed_signal=parsed, routing_rule_id=rule_id, raw_signal_meta=meta)

    with _mock_httpx_post(dispatcher=test_dispatcher):
        resp1 = await client.post(
            "/api/workflow/dispatch-signal",
            json=job.model_dump(mode="json"),
        )
    assert resp1.json()["status"] == "success"

    # Second dispatch with same message_id — should be deduped
    with _mock_httpx_post(dispatcher=test_dispatcher) as mock_post:
        resp2 = await client.post(
            "/api/workflow/dispatch-signal",
            json=job.model_dump(mode="json"),
        )
    assert resp2.json()["status"] == "ignored"
    assert "Already processed" in resp2.json()["error_message"]
    mock_post.assert_not_called()


# ===========================================================================
# Test: Marketplace fan-out integration
# ===========================================================================


@pytest.mark.asyncio
async def test_marketplace_fanout_integration(
    client, session_factory, test_dispatcher,
):
    """When a signal arrives from a marketplace provider's channel via an admin
    listener, the workflow should fan out to all marketplace subscribers."""
    # Promote the test user to admin (fan-out only triggers for admin listeners)
    async with session_factory() as session:
        from sqlalchemy import update as sa_update
        await session.execute(sa_update(UserModel).where(UserModel.id == SAMPLE_USER_ID).values(is_admin=True))
        await session.commit()

    # Seed the original user's routing rule (their own channel subscription)
    rule_id = await _seed_routing_rule(session_factory, webhook_url=WEBHOOK_URL_1)

    # Seed a second user (marketplace subscriber)
    sub_user_id = SUBSCRIBER_USER_ID
    async with session_factory() as session:
        session.add(UserModel(
            id=sub_user_id,
            email="subscriber@example.com",
            password_hash="$2b$12$fakehashedpassword",
            subscription_tier="pro",
        ))
        await session.commit()

    # Seed marketplace provider for the channel
    provider_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(MarketplaceProviderModel(
            id=provider_id,
            name="Test Signals",
            asset_class="forex",
            telegram_channel_id=CHANNEL_ID,
            is_active=True,
        ))
        await session.commit()

    # Seed a routing rule for the marketplace subscriber
    sub_rule_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(RoutingRuleModel(
            id=sub_rule_id,
            user_id=sub_user_id,
            source_channel_id=CHANNEL_ID,
            destination_webhook_url=WEBHOOK_URL_2,
            payload_version="V1",
            symbol_mappings={},
            risk_overrides={},
            webhook_body_template=DEFAULT_TEMPLATE.copy(),
            destination_type="sagemaster_forex",
            is_active=True,
        ))
        await session.commit()

    # Seed marketplace subscription linking subscriber to provider
    async with session_factory() as session:
        session.add(MarketplaceSubscriptionModel(
            user_id=sub_user_id,
            provider_id=provider_id,
            routing_rule_id=sub_rule_id,
            is_active=True,
        ))
        await session.commit()

    parsed = _make_valid_parsed_signal()

    with (
        _mock_openai_parser(parsed),
        _mock_httpx_post(dispatcher=test_dispatcher) as mock_post,
        patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"}),
    ):
        resp = await client.post(
            "/api/workflow/process-signal",
            json=_raw_signal_payload(),
        )

    assert resp.status_code == 200
    results = resp.json()
    # Original user's dispatch should succeed
    assert any(r["status"] == "success" for r in results)

    # Verify marketplace fan-out created signal_logs for the subscriber
    async with session_factory() as session:
        result = await session.execute(
            select(SignalLogModel).where(
                SignalLogModel.user_id == sub_user_id,
                SignalLogModel.source_type == "marketplace",
            )
        )
        marketplace_logs = result.scalars().all()

    assert len(marketplace_logs) >= 1
    assert marketplace_logs[0].status == "success"

    # Webhook should have been called at least twice (original + marketplace)
    assert mock_post.call_count >= 2
