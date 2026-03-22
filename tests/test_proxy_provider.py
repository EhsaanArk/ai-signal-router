"""Tests for per-user proxy provider (IPRoyal + NoOp)."""

from __future__ import annotations

import os
from unittest.mock import patch
from uuid import UUID

import pytest

from src.adapters.proxy.provider import (
    IPRoyalProxyProvider,
    NoOpProxyProvider,
    get_proxy_provider,
)

USER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# =========================================================================
# IPRoyalProxyProvider
# =========================================================================


class TestIPRoyalProxyProvider:
    """Tests for IPRoyal per-user proxy generation."""

    def _make_provider(self, **overrides) -> IPRoyalProxyProvider:
        defaults = dict(
            gateway_host="geo.iproyal.com",
            gateway_port=12321,
            username="testaccount",
            password="testpass",
            session_lifetime="7d",
            country=None,
            ip_pool_size=50,
        )
        defaults.update(overrides)
        return IPRoyalProxyProvider(**defaults)

    def test_generates_correct_proxy_dict(self):
        """Proxy dict should have all Telethon-required fields."""
        provider = self._make_provider()
        proxy = provider.get_proxy_for_user(USER_A)

        assert proxy["proxy_type"] == "socks5"
        assert proxy["addr"] == "geo.iproyal.com"
        assert proxy["port"] == 12321
        assert proxy["username"] == "testaccount"
        assert proxy["rdns"] is True
        # Password contains session params
        assert "testpass" in proxy["password"]
        assert "session-slot" in proxy["password"]

    def test_password_contains_session_id(self):
        """Password should embed a slot-based session identifier."""
        provider = self._make_provider()
        proxy = provider.get_proxy_for_user(USER_A)

        assert "_session-slot" in proxy["password"]

    def test_password_contains_lifetime(self):
        """Password should include the sticky session lifetime."""
        provider = self._make_provider(session_lifetime="1h")
        proxy = provider.get_proxy_for_user(USER_A)

        assert "_lifetime-1h_" in proxy["password"]

    def test_password_includes_country_when_set(self):
        """Country code should be in password when configured."""
        provider = self._make_provider(country="us")
        proxy = provider.get_proxy_for_user(USER_A)

        assert "_country-us_" in proxy["password"]

    def test_password_excludes_country_when_none(self):
        """No country param when country is not configured."""
        provider = self._make_provider(country=None)
        proxy = provider.get_proxy_for_user(USER_A)

        assert "country-" not in proxy["password"]

    def test_password_includes_streaming(self):
        """Password should include streaming=1 for persistent connections."""
        provider = self._make_provider()
        proxy = provider.get_proxy_for_user(USER_A)

        assert proxy["password"].endswith("_streaming-1")

    def test_different_users_get_different_sessions_with_large_pool(self):
        """With a large pool, different users should get different slots."""
        provider = self._make_provider(ip_pool_size=1000)
        proxy_a = provider.get_proxy_for_user(USER_A)
        proxy_b = provider.get_proxy_for_user(USER_B)

        # Different passwords (different session slots)
        assert proxy_a["password"] != proxy_b["password"]
        # Same gateway and username
        assert proxy_a["addr"] == proxy_b["addr"]
        assert proxy_a["port"] == proxy_b["port"]
        assert proxy_a["username"] == proxy_b["username"]

    def test_same_user_gets_same_session(self):
        """Same user should always get the same proxy config (deterministic)."""
        provider = self._make_provider()
        proxy_1 = provider.get_proxy_for_user(USER_A)
        proxy_2 = provider.get_proxy_for_user(USER_A)

        assert proxy_1 == proxy_2

    def test_custom_port(self):
        """Non-default port should be respected."""
        provider = self._make_provider(gateway_port=9999)
        proxy = provider.get_proxy_for_user(USER_A)

        assert proxy["port"] == 9999

    def test_pool_size_1_all_users_share_one_slot(self):
        """With pool_size=1, all users should share the same slot."""
        provider = self._make_provider(ip_pool_size=1)
        proxy_a = provider.get_proxy_for_user(USER_A)
        proxy_b = provider.get_proxy_for_user(USER_B)

        assert proxy_a["password"] == proxy_b["password"]

    def test_pool_grouping_is_consistent(self):
        """Users should always land in the same slot across calls."""
        provider = self._make_provider(ip_pool_size=5)
        users = [UUID(f"{i:08x}-0000-0000-0000-000000000000") for i in range(20)]

        for u in users:
            p1 = provider.get_proxy_for_user(u)
            p2 = provider.get_proxy_for_user(u)
            assert p1 == p2, f"User {u} got different proxies on repeated calls"


# =========================================================================
# NoOpProxyProvider
# =========================================================================


class TestNoOpProxyProvider:
    """Tests for the disabled proxy provider."""

    def test_returns_none(self):
        """NoOp should always return None."""
        provider = NoOpProxyProvider()
        assert provider.get_proxy_for_user(USER_A) is None

    def test_returns_none_for_any_user(self):
        """NoOp should return None regardless of user."""
        provider = NoOpProxyProvider()
        assert provider.get_proxy_for_user(USER_A) is None
        assert provider.get_proxy_for_user(USER_B) is None


# =========================================================================
# Factory: get_proxy_provider()
# =========================================================================


class TestGetProxyProvider:
    """Tests for the provider factory function."""

    def test_default_returns_noop(self):
        """No PROXY_PROVIDER env var → NoOp."""
        with patch.dict(os.environ, {}, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)

    def test_none_returns_noop(self):
        """PROXY_PROVIDER=none → NoOp."""
        with patch.dict(os.environ, {"PROXY_PROVIDER": "none"}):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)

    def test_iproyal_returns_provider(self):
        """PROXY_PROVIDER=iproyal with all required vars → IPRoyal."""
        env = {
            "PROXY_PROVIDER": "iproyal",
            "PROXY_USERNAME": "testaccount",
            "PROXY_PASSWORD": "testpass",
            "PROXY_SESSION_LIFETIME": "1h",
            "PROXY_COUNTRY": "us",
            "PROXY_IP_POOL_SIZE": "10",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, IPRoyalProxyProvider)

            # Verify it generates correct proxies
            proxy = provider.get_proxy_for_user(USER_A)
            assert proxy["addr"] == "geo.iproyal.com"
            assert proxy["port"] == 12321
            assert proxy["proxy_type"] == "socks5"
            assert "_lifetime-1h_" in proxy["password"]
            assert "_country-us_" in proxy["password"]

    def test_iproyal_missing_username_falls_back(self):
        """PROXY_PROVIDER=iproyal without username → NoOp with warning."""
        env = {
            "PROXY_PROVIDER": "iproyal",
            "PROXY_PASSWORD": "testpass",
            # Missing PROXY_USERNAME
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)

    def test_iproyal_missing_password_falls_back(self):
        """PROXY_PROVIDER=iproyal without password → NoOp."""
        env = {
            "PROXY_PROVIDER": "iproyal",
            "PROXY_USERNAME": "testaccount",
            # Missing PROXY_PASSWORD
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)

    def test_iproyal_defaults_host_and_port(self):
        """Host and port should default when not set."""
        env = {
            "PROXY_PROVIDER": "iproyal",
            "PROXY_USERNAME": "testaccount",
            "PROXY_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, IPRoyalProxyProvider)
            proxy = provider.get_proxy_for_user(USER_A)
            assert proxy["addr"] == "geo.iproyal.com"
            assert proxy["port"] == 12321

    def test_unknown_provider_falls_back(self):
        """PROXY_PROVIDER=unknown → NoOp with warning."""
        with patch.dict(os.environ, {"PROXY_PROVIDER": "brightdata"}):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)
