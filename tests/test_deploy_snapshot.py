"""Tests for the deploy snapshot module (pre/post-deploy session verification)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.adapters.telegram.deploy_snapshot import (
    SNAPSHOT_KEY,
    build_snapshot,
    compare_snapshots,
    read_pre_deploy_snapshot,
    run_post_startup_check,
    save_pre_shutdown_snapshot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_listener(connected: bool = True) -> MagicMock:
    listener = MagicMock()
    listener.is_connected = connected
    return listener


def _make_listeners(n_connected: int, n_disconnected: int = 0):
    listeners = {}
    channels = {}
    for i in range(n_connected):
        uid = uuid4()
        listeners[uid] = _make_listener(connected=True)
        channels[uid] = {f"ch_{i}_a", f"ch_{i}_b"}
    for i in range(n_disconnected):
        uid = uuid4()
        listeners[uid] = _make_listener(connected=False)
        channels[uid] = {f"ch_disc_{i}"}
    return listeners, channels


class FakeCache:
    """In-memory cache for testing."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# build_snapshot
# ---------------------------------------------------------------------------


class TestBuildSnapshot:
    def test_basic_snapshot(self):
        listeners, channels = _make_listeners(3)
        snapshot = build_snapshot(listeners, channels)

        assert snapshot["active_sessions"] == 3
        assert snapshot["connected_listeners"] == 3
        assert snapshot["channels_monitored"] == 6  # 3 users × 2 channels each
        assert len(snapshot["user_ids"]) == 3
        assert "timestamp" in snapshot

    def test_mixed_connected_disconnected(self):
        listeners, channels = _make_listeners(2, n_disconnected=1)
        snapshot = build_snapshot(listeners, channels)

        assert snapshot["active_sessions"] == 3
        assert snapshot["connected_listeners"] == 2
        assert snapshot["channels_monitored"] == 5  # 2×2 + 1×1

    def test_empty_listeners(self):
        snapshot = build_snapshot({}, {})

        assert snapshot["active_sessions"] == 0
        assert snapshot["connected_listeners"] == 0
        assert snapshot["channels_monitored"] == 0
        assert snapshot["user_ids"] == []


# ---------------------------------------------------------------------------
# compare_snapshots
# ---------------------------------------------------------------------------


class TestCompareSnapshots:
    def test_healthy_same_counts(self):
        pre = {"active_sessions": 6, "connected_listeners": 6,
               "channels_monitored": 13, "user_ids": ["a", "b", "c"],
               "timestamp": "2026-03-19T02:00:00Z"}
        post = {"active_sessions": 6, "connected_listeners": 6,
                "channels_monitored": 13, "user_ids": ["a", "b", "c"]}

        result = compare_snapshots(pre, post)
        assert result["verdict"] == "HEALTHY"
        assert result["sessions_delta"] == 0
        assert result["lost_user_ids"] == []

    def test_sessions_lost(self):
        pre = {"active_sessions": 6, "connected_listeners": 6,
               "channels_monitored": 13, "user_ids": ["a", "b", "c", "d", "e", "f"],
               "timestamp": "2026-03-19T02:00:00Z"}
        post = {"active_sessions": 4, "connected_listeners": 4,
                "channels_monitored": 10, "user_ids": ["a", "b", "c", "d"]}

        result = compare_snapshots(pre, post)
        assert result["verdict"] == "SESSIONS_LOST"
        assert result["sessions_delta"] == -2
        assert set(result["lost_user_ids"]) == {"e", "f"}

    def test_connections_degraded(self):
        pre = {"active_sessions": 6, "connected_listeners": 6,
               "channels_monitored": 13, "user_ids": ["a", "b", "c"],
               "timestamp": "2026-03-19T02:00:00Z"}
        post = {"active_sessions": 6, "connected_listeners": 4,
                "channels_monitored": 13, "user_ids": ["a", "b", "c"]}

        result = compare_snapshots(pre, post)
        assert result["verdict"] == "CONNECTIONS_DEGRADED"

    def test_new_users_added(self):
        pre = {"active_sessions": 3, "connected_listeners": 3,
               "channels_monitored": 6, "user_ids": ["a", "b", "c"],
               "timestamp": "2026-03-19T02:00:00Z"}
        post = {"active_sessions": 4, "connected_listeners": 4,
                "channels_monitored": 8, "user_ids": ["a", "b", "c", "d"]}

        result = compare_snapshots(pre, post)
        assert result["verdict"] == "HEALTHY"
        assert result["sessions_delta"] == 1
        assert result["new_user_ids"] == ["d"]


# ---------------------------------------------------------------------------
# save_pre_shutdown_snapshot
# ---------------------------------------------------------------------------


class TestSavePreShutdownSnapshot:
    @pytest.mark.asyncio
    async def test_success(self):
        listeners, channels = _make_listeners(3)
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            result = await save_pre_shutdown_snapshot(
                "redis://localhost:6379", listeners, channels,
            )

        assert result is True
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == SNAPSHOT_KEY
        data = json.loads(call_args[0][1])
        assert data["active_sessions"] == 3

    @pytest.mark.asyncio
    async def test_redis_down_returns_false(self):
        listeners, channels = _make_listeners(3)

        with patch("redis.asyncio.from_url", side_effect=ConnectionError("refused")):
            result = await save_pre_shutdown_snapshot(
                "redis://localhost:6379", listeners, channels,
            )

        assert result is False


# ---------------------------------------------------------------------------
# read_pre_deploy_snapshot
# ---------------------------------------------------------------------------


class TestReadPreDeploySnapshot:
    @pytest.mark.asyncio
    async def test_valid_snapshot(self):
        cache = FakeCache()
        snapshot = {"active_sessions": 6, "timestamp": "2026-03-19T02:00:00Z"}
        cache._store[SNAPSHOT_KEY] = json.dumps(snapshot)

        result = await read_pre_deploy_snapshot(cache)
        assert result == snapshot

    @pytest.mark.asyncio
    async def test_no_snapshot(self):
        cache = FakeCache()
        result = await read_pre_deploy_snapshot(cache)
        assert result is None

    @pytest.mark.asyncio
    async def test_corrupt_json(self):
        cache = FakeCache()
        cache._store[SNAPSHOT_KEY] = "not valid json{{"

        result = await read_pre_deploy_snapshot(cache)
        assert result is None


# ---------------------------------------------------------------------------
# run_post_startup_check
# ---------------------------------------------------------------------------


class TestRunPostStartupCheck:
    @pytest.mark.asyncio
    async def test_healthy_comparison(self):
        cache = FakeCache()
        pre = {"active_sessions": 3, "connected_listeners": 3,
               "channels_monitored": 6, "user_ids": [],
               "timestamp": "2026-03-19T02:00:00Z"}
        cache._store[SNAPSHOT_KEY] = json.dumps(pre)

        listeners, channels = _make_listeners(3)
        result = await run_post_startup_check(cache, listeners, channels)

        assert result is not None
        assert result["verdict"] == "HEALTHY"

    @pytest.mark.asyncio
    async def test_sessions_lost_logs_warning(self):
        cache = FakeCache()
        pre = {"active_sessions": 6, "connected_listeners": 6,
               "channels_monitored": 13, "user_ids": ["a", "b", "c", "d", "e", "f"],
               "timestamp": "2026-03-19T02:00:00Z"}
        cache._store[SNAPSHOT_KEY] = json.dumps(pre)

        listeners, channels = _make_listeners(4)
        result = await run_post_startup_check(cache, listeners, channels)

        assert result is not None
        assert result["verdict"] == "SESSIONS_LOST"
        assert result["sessions_delta"] == -2

    @pytest.mark.asyncio
    async def test_no_snapshot_returns_none(self):
        cache = FakeCache()
        listeners, channels = _make_listeners(3)

        result = await run_post_startup_check(cache, listeners, channels)
        assert result is None
