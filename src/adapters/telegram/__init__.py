from __future__ import annotations

from urllib.parse import urlparse

from src.adapters.telegram.auth import TelegramAuth
from src.adapters.telegram.channels import get_user_channels


def parse_proxy_url(url: str | None) -> dict | None:
    """Parse a ``TELEGRAM_PROXY_URL`` into a Telethon-compatible proxy dict.

    Accepts URLs in the form ``socks5://user:pass@host:port`` or
    ``socks5://host:port``.  Returns ``None`` when *url* is falsy so that
    callers can pass the result directly to ``TelegramClient(proxy=...)``.
    """
    if not url:
        return None
    parsed = urlparse(url)
    proxy: dict = {
        "proxy_type": parsed.scheme,
        "addr": parsed.hostname,
        "port": parsed.port or 1080,
        "rdns": True,
    }
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


__all__ = ["TelegramAuth", "get_user_channels", "parse_proxy_url"]
