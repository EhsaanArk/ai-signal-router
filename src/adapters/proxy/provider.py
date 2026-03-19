"""Per-user proxy providers for Telegram MTProto connections.

Generates Telethon-compatible proxy dicts with per-user IP isolation.
Each user gets a unique residential IP via the proxy provider's gateway,
preventing Telegram from flagging multiple accounts on the same IP.

Controlled by environment variables:

    PROXY_PROVIDER              – "iproyal" or "none" (default: "none")
    PROXY_GATEWAY_HOST          – provider gateway hostname
    PROXY_GATEWAY_PORT          – provider gateway port (default: 12321)
    PROXY_USERNAME              – provider account username
    PROXY_PASSWORD              – provider account password
    PROXY_SESSION_DURATION      – sticky IP duration in minutes (default: 60)
    PROXY_COUNTRY               – target country code, e.g. "us" (optional)

When ``PROXY_PROVIDER=none``, the :class:`NoOpProxyProvider` is returned
and all users fall back to the global ``TELEGRAM_PROXY_URL`` or connect
directly.
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

logger = logging.getLogger(__name__)


class IPRoyalProxyProvider:
    """Generate per-user SOCKS5 proxy configs via IPRoyal's gateway.

    IPRoyal uses a single gateway endpoint.  The session ID embedded in
    the username determines which residential IP is assigned.  Same
    session ID = same IP (sticky for ``session_duration`` minutes).

    ::

        socks5://acct-session-{uid}-sessionTime-60:pass@geo.iproyal.com:12321

        User A → session-aaa... → IP 203.0.113.1  (sticky 60 min)
        User B → session-bbb... → IP 198.51.100.7 (sticky 60 min)
    """

    def __init__(
        self,
        gateway_host: str,
        gateway_port: int,
        username: str,
        password: str,
        session_duration: int = 60,
        country: str | None = None,
    ) -> None:
        self._gateway_host = gateway_host
        self._gateway_port = gateway_port
        self._base_username = username
        self._password = password
        self._duration = session_duration
        self._country = country

    def get_proxy_for_user(self, user_id: UUID) -> dict:
        """Return a SOCKS5 proxy dict with a unique session for this user."""
        session_id = str(user_id).replace("-", "")
        username = (
            f"{self._base_username}"
            f"-session-{session_id}"
            f"-sessionTime-{self._duration}"
        )
        if self._country:
            username += f"-country-{self._country}"

        return {
            "proxy_type": "socks5",
            "addr": self._gateway_host,
            "port": self._gateway_port,
            "username": username,
            "password": self._password,
            "rdns": True,
        }


class NoOpProxyProvider:
    """Returns ``None`` for all users — proxy disabled.

    Used when ``PROXY_PROVIDER=none`` (default).  The caller should
    fall back to the global ``TELEGRAM_PROXY_URL`` or connect directly.
    """

    def get_proxy_for_user(self, user_id: UUID) -> dict | None:
        return None


def get_proxy_provider() -> IPRoyalProxyProvider | NoOpProxyProvider:
    """Factory: create a proxy provider based on environment config.

    Returns :class:`IPRoyalProxyProvider` when ``PROXY_PROVIDER=iproyal``
    and all required env vars are set.  Otherwise returns
    :class:`NoOpProxyProvider`.
    """
    provider = os.environ.get("PROXY_PROVIDER", "none").lower()

    if provider == "iproyal":
        host = os.environ.get("PROXY_GATEWAY_HOST", "")
        port_str = os.environ.get("PROXY_GATEWAY_PORT", "12321")
        username = os.environ.get("PROXY_USERNAME", "")
        password = os.environ.get("PROXY_PASSWORD", "")
        duration_str = os.environ.get("PROXY_SESSION_DURATION", "60")
        country = os.environ.get("PROXY_COUNTRY") or None

        if not host or not username or not password:
            logger.warning(
                "PROXY_PROVIDER=iproyal but missing required env vars "
                "(PROXY_GATEWAY_HOST, PROXY_USERNAME, PROXY_PASSWORD). "
                "Falling back to no proxy."
            )
            return NoOpProxyProvider()

        proxy_provider = IPRoyalProxyProvider(
            gateway_host=host,
            gateway_port=int(port_str),
            username=username,
            password=password,
            session_duration=int(duration_str),
            country=country,
        )
        logger.info(
            "Proxy provider: IPRoyal (gateway=%s:%s, duration=%smin, country=%s)",
            host, port_str, duration_str, country or "any",
        )
        return proxy_provider

    if provider != "none":
        logger.warning(
            "Unknown PROXY_PROVIDER=%s — falling back to no proxy. "
            "Supported: 'iproyal', 'none'.",
            provider,
        )

    logger.info("Proxy provider: none (using global TELEGRAM_PROXY_URL if set)")
    return NoOpProxyProvider()
