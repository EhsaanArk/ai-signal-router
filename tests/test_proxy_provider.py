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
            session_duration=60,
            country=None,
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
        assert proxy["password"] == "testpass"
        assert proxy["rdns"] is True
        assert "testaccount" in proxy["username"]

    def test_username_contains_session_id(self):
        """Username should embed the user ID as a session identifier."""
        provider = self._make_provider()
        proxy = provider.get_proxy_for_user(USER_A)

        user_id_hex = str(USER_A).replace("-", "")
        assert f"-session-{user_id_hex}" in proxy["username"]

    def test_username_contains_session_duration(self):
        """Username should include the sticky session duration."""
        provider = self._make_provider(session_duration=30)
        proxy = provider.get_proxy_for_user(USER_A)

        assert "-sessionTime-30" in proxy["username"]

    def test_username_includes_country_when_set(self):
        """Country code should be appended to username when configured."""
        provider = self._make_provider(country="us")
        proxy = provider.get_proxy_for_user(USER_A)

        assert "-country-us" in proxy["username"]

    def test_username_excludes_country_when_none(self):
        """No country suffix when country is not configured."""
        provider = self._make_provider(country=None)
        proxy = provider.get_proxy_for_user(USER_A)

        assert "-country-" not in proxy["username"]

    def test_different_users_get_different_sessions(self):
        """Each user should get a unique session ID → unique IP."""
        provider = self._make_provider()
        proxy_a = provider.get_proxy_for_user(USER_A)
        proxy_b = provider.get_proxy_for_user(USER_B)

        assert proxy_a["username"] != proxy_b["username"]
        # Same gateway, same password, same port
        assert proxy_a["addr"] == proxy_b["addr"]
        assert proxy_a["port"] == proxy_b["port"]
        assert proxy_a["password"] == proxy_b["password"]

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
            "PROXY_GATEWAY_HOST": "geo.iproyal.com",
            "PROXY_GATEWAY_PORT": "12321",
            "PROXY_USERNAME": "testaccount",
            "PROXY_PASSWORD": "testpass",
            "PROXY_SESSION_DURATION": "30",
            "PROXY_COUNTRY": "us",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, IPRoyalProxyProvider)

            # Verify it generates correct proxies
            proxy = provider.get_proxy_for_user(USER_A)
            assert proxy["addr"] == "geo.iproyal.com"
            assert proxy["port"] == 12321
            assert "-sessionTime-30" in proxy["username"]
            assert "-country-us" in proxy["username"]

    def test_iproyal_missing_host_falls_back(self):
        """PROXY_PROVIDER=iproyal without required vars → NoOp with warning."""
        env = {
            "PROXY_PROVIDER": "iproyal",
            "PROXY_USERNAME": "testaccount",
            "PROXY_PASSWORD": "testpass",
            # Missing PROXY_GATEWAY_HOST
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)

    def test_iproyal_missing_password_falls_back(self):
        """PROXY_PROVIDER=iproyal without password → NoOp."""
        env = {
            "PROXY_PROVIDER": "iproyal",
            "PROXY_GATEWAY_HOST": "geo.iproyal.com",
            "PROXY_USERNAME": "testaccount",
            # Missing PROXY_PASSWORD
        }
        with patch.dict(os.environ, env, clear=True):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)

    def test_unknown_provider_falls_back(self):
        """PROXY_PROVIDER=unknown → NoOp with warning."""
        with patch.dict(os.environ, {"PROXY_PROVIDER": "brightdata"}):
            provider = get_proxy_provider()
            assert isinstance(provider, NoOpProxyProvider)
