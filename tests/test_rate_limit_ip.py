"""Tests for proxy-aware client IP extraction used by the rate limiter."""

from __future__ import annotations

from starlette.requests import Request

from src.api.deps import _get_real_ip, _trusted_proxy_networks


def _make_request(client_ip: str, headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in headers.items()
        ],
        "client": (client_ip, 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_x_forwarded_for_ignored_without_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    _trusted_proxy_networks.cache_clear()
    request = _make_request(
        "127.0.0.1",
        {"X-Forwarded-For": "203.0.113.10"},
    )
    assert _get_real_ip(request) == "127.0.0.1"


def test_x_forwarded_for_used_with_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
    _trusted_proxy_networks.cache_clear()
    request = _make_request(
        "127.0.0.1",
        {"X-Forwarded-For": "203.0.113.10, 127.0.0.1"},
    )
    assert _get_real_ip(request) == "203.0.113.10"
