"""Tests for src.core.marketplace — fan-out, stats computation, subscribe/unsubscribe."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.marketplace import (
    compute_provider_stats,
    marketplace_fanout,
    subscribe_to_provider,
    unsubscribe_from_provider,
)
from src.core.models import DispatchResult, ParsedSignal


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes for SQLAlchemy ORM rows
# ---------------------------------------------------------------------------


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _make_provider(
    *,
    id: uuid.UUID | None = None,
    channel_id: str = "-1001234567890",
    name: str = "VIP Forex Signals",
    is_active: bool = True,
    win_rate: float | None = None,
    total_pnl_pips: float | None = None,
    max_drawdown_pips: float | None = None,
    signal_count: int = 0,
    subscriber_count: int = 0,
    track_record_days: int = 0,
    stats_last_computed_at: datetime | None = None,
) -> MagicMock:
    provider = MagicMock()
    provider.id = id or _uuid()
    provider.telegram_channel_id = channel_id
    provider.name = name
    provider.is_active = is_active
    provider.win_rate = win_rate
    provider.total_pnl_pips = total_pnl_pips
    provider.max_drawdown_pips = max_drawdown_pips
    provider.signal_count = signal_count
    provider.subscriber_count = subscriber_count
    provider.track_record_days = track_record_days
    provider.stats_last_computed_at = stats_last_computed_at
    return provider


def _make_subscription(
    *,
    id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    provider_id: uuid.UUID | None = None,
    routing_rule_id: uuid.UUID | None = None,
    is_active: bool = True,
) -> MagicMock:
    sub = MagicMock()
    sub.id = id or _uuid()
    sub.user_id = user_id or _uuid()
    sub.provider_id = provider_id or _uuid()
    sub.routing_rule_id = routing_rule_id or _uuid()
    sub.is_active = is_active
    return sub


def _make_routing_rule_row(
    *,
    id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    source_channel_id: str = "-1001234567890",
    source_channel_name: str | None = "VIP Signals",
    destination_webhook_url: str = "https://api.sagemaster.io/deals_idea/test-id",
    payload_version: str = "V2",
    symbol_mappings: dict | None = None,
    risk_overrides: dict | None = None,
    webhook_body_template: dict | None = None,
    rule_name: str | None = "Test Rule",
    destination_label: str | None = "My Account",
    destination_type: str = "sagemaster_forex",
    custom_ai_instructions: str | None = None,
    is_active: bool = True,
    enabled_actions: list | None = None,
    keyword_blacklist: list | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = id or _uuid()
    row.user_id = user_id or _uuid()
    row.source_channel_id = source_channel_id
    row.source_channel_name = source_channel_name
    row.destination_webhook_url = destination_webhook_url
    row.payload_version = payload_version
    row.symbol_mappings = symbol_mappings or {}
    row.risk_overrides = risk_overrides or {}
    row.webhook_body_template = webhook_body_template
    row.rule_name = rule_name
    row.destination_label = destination_label
    row.destination_type = destination_type
    row.custom_ai_instructions = custom_ai_instructions
    row.is_active = is_active
    row.enabled_actions = enabled_actions
    row.keyword_blacklist = keyword_blacklist or []
    return row


def _sample_parsed_signal() -> ParsedSignal:
    return ParsedSignal(
        symbol="EURUSD",
        direction="long",
        entry_price=1.1,
        stop_loss=1.095,
        take_profits=[1.105, 1.11],
    )


class _FakeScalarsResult:
    """Wraps a list so .scalars().all() works."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    """Mimics SQLAlchemy execute() result with scalar_one_or_none / scalars / one."""

    def __init__(self, value=None, *, items=None, row=None):
        self._value = value
        self._items = items
        self._row = row

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def scalars(self):
        return _FakeScalarsResult(self._items or [])

    def one(self):
        return self._row or (self._value,)

    def all(self):
        return self._items or []


def _build_db_session(execute_side_effects: list) -> AsyncMock:
    """Build a mock AsyncSession whose .execute() returns results in order."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_side_effects)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ===========================================================================
# marketplace_fanout tests
# ===========================================================================


class TestMarketplaceFanout:
    """Tests for marketplace_fanout()."""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "false"})
    async def test_disabled_returns_empty(self):
        """MARKETPLACE_ENABLED=false skips fan-out entirely."""
        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id="-1001234567890",
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=AsyncMock(),
            db_session=AsyncMock(),
        )
        assert result == []

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"})
    async def test_channel_not_in_providers_returns_empty(self):
        """Channel not in marketplace_providers returns empty."""
        db = _build_db_session([
            _FakeResult(value=None),  # provider lookup → not found
        ])
        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id="-999",
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=AsyncMock(),
            db_session=db,
        )
        assert result == []

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"})
    async def test_zero_active_subscribers_returns_empty(self):
        """Channel with 0 active subscribers returns empty."""
        provider = _make_provider()
        db = _build_db_session([
            _FakeResult(value=provider),  # provider found
            _FakeResult(items=[]),         # 0 subscriptions
        ])
        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id=provider.telegram_channel_id,
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=AsyncMock(),
            db_session=db,
        )
        assert result == []

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"})
    async def test_one_subscriber_dispatches_successfully(self):
        """Channel with 1 subscriber dispatches successfully."""
        provider = _make_provider()
        rule_id = _uuid()
        user_id = _uuid()
        sub = _make_subscription(
            user_id=user_id,
            provider_id=provider.id,
            routing_rule_id=rule_id,
        )
        rule_row = _make_routing_rule_row(id=rule_id, user_id=user_id)

        dispatch_result = DispatchResult(
            routing_rule_id=rule_id,
            status="success",
            error_message=None,
            webhook_payload={"type": "start_long_market_deal"},
        )
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(return_value=dispatch_result)

        db = _build_db_session([
            _FakeResult(value=provider),       # provider found
            _FakeResult(items=[sub]),           # 1 subscription
            _FakeResult(items=[rule_row]),      # routing rule
        ])

        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id=provider.telegram_channel_id,
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=dispatcher,
            db_session=db,
        )
        assert len(result) == 1
        assert result[0]["status"] == "success"
        assert result[0]["user_id"] == str(user_id)
        dispatcher.dispatch.assert_awaited_once()
        # Signal log should be added
        db.add.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"})
    async def test_n_subscribers_dispatches_to_all(self):
        """Channel with N subscribers dispatches to all."""
        provider = _make_provider()
        subs = []
        rule_rows = []
        for _ in range(3):
            rid = _uuid()
            uid = _uuid()
            subs.append(_make_subscription(
                user_id=uid, provider_id=provider.id, routing_rule_id=rid,
            ))
            rule_rows.append(_make_routing_rule_row(id=rid, user_id=uid))

        dispatch_result = DispatchResult(
            status="success",
            webhook_payload={"type": "start_long_market_deal"},
        )
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(return_value=dispatch_result)

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(items=subs),
            _FakeResult(items=rule_rows),
        ])

        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id=provider.telegram_channel_id,
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=dispatcher,
            db_session=db,
        )
        assert len(result) == 3
        assert all(r["status"] == "success" for r in result)
        assert dispatcher.dispatch.await_count == 3

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"})
    async def test_one_failure_does_not_block_others(self):
        """One subscriber's dispatch failure doesn't block others."""
        provider = _make_provider()
        subs = []
        rule_rows = []
        for _ in range(3):
            rid = _uuid()
            uid = _uuid()
            subs.append(_make_subscription(
                user_id=uid, provider_id=provider.id, routing_rule_id=rid,
            ))
            rule_rows.append(_make_routing_rule_row(id=rid, user_id=uid))

        # Second dispatch raises an exception
        success = DispatchResult(
            status="success",
            webhook_payload={"type": "start_long_market_deal"},
        )
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(
            side_effect=[success, RuntimeError("Connection timeout"), success]
        )

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(items=subs),
            _FakeResult(items=rule_rows),
        ])

        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id=provider.telegram_channel_id,
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=dispatcher,
            db_session=db,
        )
        assert len(result) == 3
        assert result[0]["status"] == "success"
        assert result[1]["status"] == "failed"
        assert "Connection timeout" in result[1]["error"]
        assert result[2]["status"] == "success"
        # All 3 signal logs added (success + failure + success)
        assert db.add.call_count == 3

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MARKETPLACE_ENABLED": "true"})
    async def test_subscriber_with_deleted_routing_rule_skipped(self):
        """Subscriber with deleted routing_rule is skipped gracefully."""
        provider = _make_provider()
        valid_rid = _uuid()
        deleted_rid = _uuid()  # This rule won't appear in the rules query
        uid1 = _uuid()
        uid2 = _uuid()

        sub1 = _make_subscription(
            user_id=uid1, provider_id=provider.id, routing_rule_id=valid_rid,
        )
        sub2 = _make_subscription(
            user_id=uid2, provider_id=provider.id, routing_rule_id=deleted_rid,
        )

        rule_row = _make_routing_rule_row(id=valid_rid, user_id=uid1)
        # Only return one rule row — the other is "deleted"

        dispatch_result = DispatchResult(
            status="success",
            webhook_payload={"type": "start_long_market_deal"},
        )
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(return_value=dispatch_result)

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(items=[sub1, sub2]),
            _FakeResult(items=[rule_row]),  # only valid_rid returned
        ])

        result = await marketplace_fanout(
            parsed_signal=_sample_parsed_signal(),
            channel_id=provider.telegram_channel_id,
            raw_message="Buy EURUSD",
            message_id=123,
            reply_to_msg_id=None,
            dispatcher=dispatcher,
            db_session=db,
        )
        # Only sub1 should dispatch; sub2 skipped because rule not found
        assert len(result) == 1
        assert result[0]["user_id"] == str(uid1)
        dispatcher.dispatch.assert_awaited_once()


# ===========================================================================
# compute_provider_stats tests
# ===========================================================================


class TestComputeProviderStats:
    """Tests for compute_provider_stats()."""

    @pytest.mark.asyncio
    async def test_provider_with_zero_signals_returns_defaults(self):
        """Provider with 0 signals returns default stats."""
        provider_id = _uuid()
        provider = _make_provider(id=provider_id)

        db = _build_db_session([
            _FakeResult(value=provider),          # provider lookup
            _FakeResult(value=0),                  # total signal count
            _FakeResult(value=0),                  # success count
            _FakeResult(row=(None, None)),          # date range (no signals)
            _FakeResult(value=0),                  # subscriber count
            _FakeResult(value=None),               # update (returns nothing)
        ])

        stats = await compute_provider_stats(provider_id, db)
        assert stats["signal_count"] == 0
        assert stats["win_rate"] is None  # no signals → None
        assert stats["track_record_days"] == 0
        assert stats["subscriber_count"] == 0

    @pytest.mark.asyncio
    async def test_provider_with_signals_computes_win_rate(self):
        """Provider with signals computes correct win_rate."""
        provider_id = _uuid()
        provider = _make_provider(id=provider_id)

        now = datetime.now(timezone.utc)
        first = now - timedelta(days=30)

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(value=10),                 # 10 total signals
            _FakeResult(value=7),                  # 7 successful
            _FakeResult(row=(first, now)),          # 30-day track record
            _FakeResult(value=5),                  # 5 subscribers
            _FakeResult(value=None),               # update
        ])

        stats = await compute_provider_stats(provider_id, db)
        assert stats["signal_count"] == 10
        assert stats["win_rate"] == pytest.approx(70.0)
        assert stats["track_record_days"] == 30
        assert stats["subscriber_count"] == 5

    @pytest.mark.asyncio
    async def test_division_by_zero_handled(self):
        """Division by zero handled when 0 closed signals (same as 0 signals)."""
        provider_id = _uuid()
        provider = _make_provider(id=provider_id)

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(value=0),                  # 0 total
            _FakeResult(value=0),                  # 0 success
            _FakeResult(row=(None, None)),
            _FakeResult(value=0),
            _FakeResult(value=None),
        ])

        stats = await compute_provider_stats(provider_id, db)
        # Should not raise — win_rate is None when signal_count == 0
        assert stats["win_rate"] is None

    @pytest.mark.asyncio
    async def test_stats_cache_updated_on_provider(self):
        """Stats cache is updated on provider model via UPDATE statement."""
        provider_id = _uuid()
        provider = _make_provider(id=provider_id)

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(value=5),
            _FakeResult(value=3),
            _FakeResult(row=(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 3, 1, tzinfo=timezone.utc),
            )),
            _FakeResult(value=2),
            _FakeResult(value=None),  # the UPDATE call
        ])

        stats = await compute_provider_stats(provider_id, db)
        # The 6th execute call is the UPDATE — verify it was called
        assert db.execute.await_count == 6
        assert stats["stats_last_computed_at"] is not None

    @pytest.mark.asyncio
    async def test_provider_not_found_raises(self):
        """Non-existent provider raises ValueError."""
        db = _build_db_session([
            _FakeResult(value=None),  # provider not found
        ])

        with pytest.raises(ValueError, match="not found"):
            await compute_provider_stats(_uuid(), db)


# ===========================================================================
# subscribe_to_provider tests
# ===========================================================================


class TestSubscribeToProvider:
    """Tests for subscribe_to_provider()."""

    @pytest.mark.asyncio
    async def test_successful_subscribe(self):
        """Successful subscribe creates subscription + routing_rule + consent_log."""
        user_id = _uuid()
        provider_id = _uuid()
        dest_rule_id = _uuid()
        provider = _make_provider(id=provider_id, is_active=True)
        dest_rule = _make_routing_rule_row(
            id=dest_rule_id,
            user_id=user_id,
            destination_webhook_url="https://api.sagemaster.io/deals_idea/abc",
        )

        db = _build_db_session([
            _FakeResult(value=provider),       # 1. provider exists
            _FakeResult(value=None),           # 2. not already subscribed
            _FakeResult(value="pro"),          # 3. user tier lookup
            _FakeResult(value=1),             # 4. active rule count (under limit)
            _FakeResult(value=dest_rule),      # 5. destination rule found
            _FakeResult(value=None),           # 6. UPDATE subscriber_count
        ])
        # flush is called twice (after rule add, after subscription+consent)
        db.flush = AsyncMock()

        result = await subscribe_to_provider(
            user_id=user_id,
            provider_id=provider_id,
            webhook_destination_id=dest_rule_id,
            db_session=db,
        )

        assert result["provider_id"] == str(provider_id)
        assert result["provider_name"] == provider.name
        assert result["is_active"] is True
        # Should add: routing_rule, subscription, consent_log = 3 calls
        assert db.add.call_count == 3
        # Should update subscriber_count
        assert db.execute.await_count == 6  # 5 selects + 1 update

    @pytest.mark.asyncio
    async def test_already_subscribed_raises(self):
        """Already subscribed raises ValueError (409 in API layer)."""
        user_id = _uuid()
        provider_id = _uuid()
        provider = _make_provider(id=provider_id, is_active=True)
        existing_sub = _make_subscription(user_id=user_id, provider_id=provider_id)

        db = _build_db_session([
            _FakeResult(value=provider),
            _FakeResult(value=existing_sub),   # already subscribed
        ])

        with pytest.raises(ValueError, match="Already subscribed"):
            await subscribe_to_provider(
                user_id=user_id,
                provider_id=provider_id,
                webhook_destination_id=_uuid(),
                db_session=db,
            )

    @pytest.mark.asyncio
    async def test_inactive_provider_raises(self):
        """Inactive provider returns ValueError (400 in API layer)."""
        provider = _make_provider(is_active=False)

        db = _build_db_session([
            _FakeResult(value=provider),
        ])

        with pytest.raises(ValueError, match="not active"):
            await subscribe_to_provider(
                user_id=_uuid(),
                provider_id=provider.id,
                webhook_destination_id=_uuid(),
                db_session=db,
            )

    @pytest.mark.asyncio
    async def test_no_webhook_destination_raises(self):
        """User with no webhook destination returns ValueError (400 in API layer)."""
        provider = _make_provider(is_active=True)

        db = _build_db_session([
            _FakeResult(value=provider),       # provider exists
            _FakeResult(value=None),           # not already subscribed
            _FakeResult(value="pro"),          # user tier lookup
            _FakeResult(value=1),             # active rule count (under limit)
            _FakeResult(value=None),           # destination rule NOT found
        ])

        with pytest.raises(ValueError, match="Webhook destination not found"):
            await subscribe_to_provider(
                user_id=_uuid(),
                provider_id=provider.id,
                webhook_destination_id=_uuid(),
                db_session=db,
            )

    @pytest.mark.asyncio
    async def test_provider_not_found_raises(self):
        """Provider not found raises ValueError (404 in API layer)."""
        db = _build_db_session([
            _FakeResult(value=None),  # provider not found
        ])

        with pytest.raises(ValueError, match="Provider not found"):
            await subscribe_to_provider(
                user_id=_uuid(),
                provider_id=_uuid(),
                webhook_destination_id=_uuid(),
                db_session=db,
            )


# ===========================================================================
# unsubscribe_from_provider tests
# ===========================================================================


class TestUnsubscribeFromProvider:
    """Tests for unsubscribe_from_provider()."""

    @pytest.mark.asyncio
    async def test_successful_unsubscribe(self):
        """Successful unsubscribe deactivates subscription + routing_rule."""
        user_id = _uuid()
        provider_id = _uuid()
        routing_rule_id = _uuid()
        sub = _make_subscription(
            user_id=user_id,
            provider_id=provider_id,
            routing_rule_id=routing_rule_id,
            is_active=True,
        )

        db = _build_db_session([
            _FakeResult(value=sub),            # subscription found
            _FakeResult(value=None),           # UPDATE routing rule
            _FakeResult(value=None),           # UPDATE subscriber count
        ])

        await unsubscribe_from_provider(
            user_id=user_id,
            provider_id=provider_id,
            db_session=db,
        )

        # Subscription should be deactivated
        assert sub.is_active is False
        # Two UPDATE executes: routing_rule deactivation + subscriber_count decrement
        assert db.execute.await_count == 3  # 1 select + 2 updates

    @pytest.mark.asyncio
    async def test_nonexistent_subscription_raises(self):
        """Unsubscribe from non-existent subscription raises ValueError (404 in API layer)."""
        db = _build_db_session([
            _FakeResult(value=None),  # subscription not found
        ])

        with pytest.raises(ValueError, match="No active subscription"):
            await unsubscribe_from_provider(
                user_id=_uuid(),
                provider_id=_uuid(),
                db_session=db,
            )

    @pytest.mark.asyncio
    async def test_resubscribe_after_unsubscribe(self):
        """Re-subscribe after unsubscribe creates a new subscription (fresh consent)."""
        user_id = _uuid()
        provider_id = _uuid()
        dest_rule_id = _uuid()
        provider = _make_provider(id=provider_id, is_active=True)
        dest_rule = _make_routing_rule_row(
            id=dest_rule_id,
            user_id=user_id,
        )

        # Step 1: Unsubscribe
        old_sub = _make_subscription(
            user_id=user_id,
            provider_id=provider_id,
            routing_rule_id=_uuid(),
            is_active=True,
        )
        unsub_db = _build_db_session([
            _FakeResult(value=old_sub),
            _FakeResult(value=None),
            _FakeResult(value=None),
        ])
        await unsubscribe_from_provider(user_id, provider_id, unsub_db)
        assert old_sub.is_active is False

        # Step 2: Re-subscribe (no active subscription exists)
        resub_db = _build_db_session([
            _FakeResult(value=provider),       # provider exists
            _FakeResult(value=None),           # no active subscription
            _FakeResult(value="pro"),          # user tier lookup
            _FakeResult(value=1),             # active rule count (under limit)
            _FakeResult(value=dest_rule),      # destination rule found
            _FakeResult(value=None),           # UPDATE subscriber_count
        ])
        resub_db.flush = AsyncMock()

        result = await subscribe_to_provider(
            user_id=user_id,
            provider_id=provider_id,
            webhook_destination_id=dest_rule_id,
            db_session=resub_db,
        )

        assert result["is_active"] is True
        assert result["provider_id"] == str(provider_id)
        # 3 adds: routing_rule + subscription + consent_log (fresh consent)
        assert resub_db.add.call_count == 3
