"""Unit tests for SQLAlchemy repository implementations.

Uses SQLite + aiosqlite with PostgreSQL type compilation overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import JSON, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.adapters.db.models import Base, UserModel
from src.adapters.db.repositories import (
    SqlAlchemyRoutingRuleRepository,
    SqlAlchemySignalLogRepository,
    SqlAlchemyUserRepository,
)
from src.core.models import RoutingRule, User

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

USER_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

SAMPLE_WEBHOOK_URL = (
    "https://api.sagemaster.io/deals_idea/eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    """Yield an in-memory SQLite-backed AsyncSession, then tear down."""
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

    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def user_repo(db_session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(db_session)


@pytest_asyncio.fixture
async def rule_repo(db_session: AsyncSession) -> SqlAlchemyRoutingRuleRepository:
    return SqlAlchemyRoutingRuleRepository(db_session)


@pytest_asyncio.fixture
async def log_repo(db_session: AsyncSession) -> SqlAlchemySignalLogRepository:
    return SqlAlchemySignalLogRepository(db_session)


async def _seed_user(session: AsyncSession, user_id: uuid.UUID, email: str) -> None:
    """Insert a user row directly so repository tests have FK targets."""
    session.add(
        UserModel(
            id=user_id,
            email=email,
            password_hash="$2b$12$fakehash",
        )
    )
    await session.flush()


# ===========================================================================
# UserRepository
# ===========================================================================


class TestUserRepository:
    """Tests for SqlAlchemyUserRepository."""

    async def test_create_user(self, user_repo: SqlAlchemyUserRepository):
        user = await user_repo.create(
            email="alice@example.com",
            password_hash="$2b$12$hashedpassword",
        )

        assert isinstance(user, User)
        assert user.email == "alice@example.com"
        assert user.password_hash == "$2b$12$hashedpassword"
        assert user.subscription_tier.value == "free"
        assert user.id is not None

    async def test_get_by_email_existing(self, user_repo: SqlAlchemyUserRepository):
        await user_repo.create(
            email="bob@example.com", password_hash="$2b$12$hash"
        )

        found = await user_repo.get_by_email("bob@example.com")
        assert found is not None
        assert found.email == "bob@example.com"

    async def test_get_by_email_nonexistent(self, user_repo: SqlAlchemyUserRepository):
        result = await user_repo.get_by_email("nobody@example.com")
        assert result is None

    async def test_get_by_id_existing(self, user_repo: SqlAlchemyUserRepository):
        created = await user_repo.create(
            email="carol@example.com", password_hash="$2b$12$hash"
        )

        found = await user_repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.email == "carol@example.com"

    async def test_get_by_id_nonexistent(self, user_repo: SqlAlchemyUserRepository):
        fake_id = uuid.uuid4()
        result = await user_repo.get_by_id(fake_id)
        assert result is None


# ===========================================================================
# RoutingRuleRepository
# ===========================================================================


class TestRoutingRuleRepository:
    """Tests for SqlAlchemyRoutingRuleRepository."""

    async def test_create(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        rule = RoutingRule(
            user_id=USER_A_ID,
            source_channel_id="-1001234567890",
            source_channel_name="VIP Signals",
            destination_webhook_url=SAMPLE_WEBHOOK_URL,
            payload_version="V1",
            symbol_mappings={"GOLD": "XAUUSD"},
            risk_overrides={"lotSize": 0.1},
            is_active=True,
        )

        created = await rule_repo.create(rule)

        assert isinstance(created, RoutingRule)
        assert created.id == rule.id
        assert created.user_id == USER_A_ID
        assert created.source_channel_id == "-1001234567890"
        assert created.source_channel_name == "VIP Signals"
        assert created.destination_webhook_url == SAMPLE_WEBHOOK_URL
        assert created.payload_version == "V1"
        assert created.symbol_mappings == {"GOLD": "XAUUSD"}
        assert created.risk_overrides == {"lotSize": 0.1}
        assert created.is_active is True

    async def test_list_by_user(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")
        await _seed_user(db_session, USER_B_ID, "user_b@example.com")

        # Create two rules for user A and one for user B
        for i in range(2):
            await rule_repo.create(
                RoutingRule(
                    user_id=USER_A_ID,
                    source_channel_id=f"-100{i}",
                    destination_webhook_url=SAMPLE_WEBHOOK_URL,
                    payload_version="V1",
                )
            )
        await rule_repo.create(
            RoutingRule(
                user_id=USER_B_ID,
                source_channel_id="-100999",
                destination_webhook_url=SAMPLE_WEBHOOK_URL,
                payload_version="V1",
            )
        )

        user_a_rules = await rule_repo.get_by_user(USER_A_ID)
        user_b_rules = await rule_repo.get_by_user(USER_B_ID)

        assert len(user_a_rules) == 2
        assert len(user_b_rules) == 1
        assert all(r.user_id == USER_A_ID for r in user_a_rules)
        assert user_b_rules[0].user_id == USER_B_ID

    async def test_get_by_id(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")
        await _seed_user(db_session, USER_B_ID, "user_b@example.com")

        rule = RoutingRule(
            user_id=USER_A_ID,
            source_channel_id="-100111",
            destination_webhook_url=SAMPLE_WEBHOOK_URL,
            payload_version="V1",
        )
        created = await rule_repo.create(rule)

        # Correct user finds the rule
        found = await rule_repo.get_by_id(created.id, USER_A_ID)
        assert found is not None
        assert found.id == created.id

        # Wrong user gets None
        not_found = await rule_repo.get_by_id(created.id, USER_B_ID)
        assert not_found is None

    async def test_update(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        rule = RoutingRule(
            user_id=USER_A_ID,
            source_channel_id="-100222",
            source_channel_name="Old Name",
            destination_webhook_url=SAMPLE_WEBHOOK_URL,
            payload_version="V1",
            is_active=True,
        )
        created = await rule_repo.create(rule)

        updated = await rule_repo.update(
            created.id,
            USER_A_ID,
            source_channel_name="New Name",
            is_active=False,
        )

        assert updated is not None
        assert updated.source_channel_name == "New Name"
        assert updated.is_active is False
        # Unchanged fields remain intact
        assert updated.source_channel_id == "-100222"

    async def test_update_nonexistent_returns_none(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        result = await rule_repo.update(
            uuid.uuid4(), USER_A_ID, source_channel_name="X"
        )
        assert result is None

    async def test_delete(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        rule = RoutingRule(
            user_id=USER_A_ID,
            source_channel_id="-100333",
            destination_webhook_url=SAMPLE_WEBHOOK_URL,
            payload_version="V1",
        )
        created = await rule_repo.create(rule)

        deleted = await rule_repo.delete(created.id, USER_A_ID)
        assert deleted is True

        # Verify it is gone
        found = await rule_repo.get_by_id(created.id, USER_A_ID)
        assert found is None

    async def test_delete_nonexistent_returns_false(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        result = await rule_repo.delete(uuid.uuid4(), USER_A_ID)
        assert result is False

    async def test_get_by_channel(
        self,
        db_session: AsyncSession,
        rule_repo: SqlAlchemyRoutingRuleRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        channel_id = "-100444"

        # Active rule on target channel
        await rule_repo.create(
            RoutingRule(
                user_id=USER_A_ID,
                source_channel_id=channel_id,
                destination_webhook_url=SAMPLE_WEBHOOK_URL,
                payload_version="V1",
                is_active=True,
            )
        )
        # Inactive rule on same channel — should be excluded
        inactive_rule = RoutingRule(
            user_id=USER_A_ID,
            source_channel_id=channel_id,
            destination_webhook_url=SAMPLE_WEBHOOK_URL,
            payload_version="V2",
            is_active=False,
        )
        await rule_repo.create(inactive_rule)

        # Active rule on a different channel — should be excluded
        await rule_repo.create(
            RoutingRule(
                user_id=USER_A_ID,
                source_channel_id="-100555",
                destination_webhook_url=SAMPLE_WEBHOOK_URL,
                payload_version="V1",
                is_active=True,
            )
        )

        results = await rule_repo.get_rules_for_channel(USER_A_ID, channel_id)

        assert len(results) == 1
        assert results[0].source_channel_id == channel_id
        assert results[0].is_active is True


# ===========================================================================
# SignalLogRepository
# ===========================================================================


class TestSignalLogRepository:
    """Tests for SqlAlchemySignalLogRepository."""

    async def test_create_log(
        self,
        db_session: AsyncSession,
        log_repo: SqlAlchemySignalLogRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        await log_repo.log(
            user_id=USER_A_ID,
            routing_rule_id=None,
            raw_message="EURUSD BUY @ 1.1000",
            parsed_data={"symbol": "EURUSD", "direction": "long"},
            webhook_payload={"type": "start_long_market_deal"},
            status="success",
        )

        logs = await log_repo.get_by_user(USER_A_ID)
        assert len(logs) == 1
        assert logs[0]["raw_message"] == "EURUSD BUY @ 1.1000"
        assert logs[0]["status"] == "success"
        assert logs[0]["parsed_data"] == {"symbol": "EURUSD", "direction": "long"}
        assert logs[0]["webhook_payload"] == {"type": "start_long_market_deal"}
        assert logs[0]["user_id"] == str(USER_A_ID)
        assert logs[0]["routing_rule_id"] is None
        assert logs[0]["error_message"] is None

    async def test_create_log_with_error(
        self,
        db_session: AsyncSession,
        log_repo: SqlAlchemySignalLogRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        await log_repo.log(
            user_id=USER_A_ID,
            routing_rule_id=None,
            raw_message="invalid signal text",
            parsed_data=None,
            webhook_payload=None,
            status="failed",
            error_message="Could not parse signal",
        )

        logs = await log_repo.get_by_user(USER_A_ID)
        assert len(logs) == 1
        assert logs[0]["status"] == "failed"
        assert logs[0]["error_message"] == "Could not parse signal"

    async def test_list_by_user_pagination(
        self,
        db_session: AsyncSession,
        log_repo: SqlAlchemySignalLogRepository,
    ):
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        # Insert 5 logs
        for i in range(5):
            await log_repo.log(
                user_id=USER_A_ID,
                routing_rule_id=None,
                raw_message=f"signal {i}",
                parsed_data=None,
                webhook_payload=None,
                status="success",
            )

        # Limit to 3
        page1 = await log_repo.get_by_user(USER_A_ID, limit=3, offset=0)
        assert len(page1) == 3

        # Offset by 3, get remaining 2
        page2 = await log_repo.get_by_user(USER_A_ID, limit=3, offset=3)
        assert len(page2) == 2

        # No overlap in IDs
        ids_page1 = {log["id"] for log in page1}
        ids_page2 = {log["id"] for log in page2}
        assert ids_page1.isdisjoint(ids_page2)

    async def test_list_by_user_ordering(
        self,
        db_session: AsyncSession,
        log_repo: SqlAlchemySignalLogRepository,
    ):
        """Logs are returned ordered by processed_at DESC (newest first)."""
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")

        for i in range(3):
            await log_repo.log(
                user_id=USER_A_ID,
                routing_rule_id=None,
                raw_message=f"signal {i}",
                parsed_data=None,
                webhook_payload=None,
                status="success",
            )

        logs = await log_repo.get_by_user(USER_A_ID)
        assert len(logs) == 3

        # Verify descending order by processed_at
        timestamps = [log["processed_at"] for log in logs]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_list_by_user_isolation(
        self,
        db_session: AsyncSession,
        log_repo: SqlAlchemySignalLogRepository,
    ):
        """Logs from one user do not appear in another user's results."""
        await _seed_user(db_session, USER_A_ID, "user_a@example.com")
        await _seed_user(db_session, USER_B_ID, "user_b@example.com")

        await log_repo.log(
            user_id=USER_A_ID,
            routing_rule_id=None,
            raw_message="signal for A",
            parsed_data=None,
            webhook_payload=None,
            status="success",
        )
        await log_repo.log(
            user_id=USER_B_ID,
            routing_rule_id=None,
            raw_message="signal for B",
            parsed_data=None,
            webhook_payload=None,
            status="success",
        )

        logs_a = await log_repo.get_by_user(USER_A_ID)
        logs_b = await log_repo.get_by_user(USER_B_ID)

        assert len(logs_a) == 1
        assert len(logs_b) == 1
        assert logs_a[0]["raw_message"] == "signal for A"
        assert logs_b[0]["raw_message"] == "signal for B"
