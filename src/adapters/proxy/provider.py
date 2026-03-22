"""Per-user proxy providers for Telegram MTProto connections.

Generates Telethon-compatible proxy dicts with per-user IP isolation.
Each user gets a unique residential IP via the proxy provider's gateway,
preventing Telegram from flagging multiple accounts on the same IP.

Controlled by environment variables:

    PROXY_PROVIDER              – "iproyal" or "none" (default: "none")
    PROXY_GATEWAY_HOST          – provider gateway hostname (default: "geo.iproyal.com")
    PROXY_GATEWAY_PORT          – provider gateway port (default: 12321)
    PROXY_USERNAME              – provider account username
    PROXY_PASSWORD              – provider account password (base, without session params)
    PROXY_SESSION_LIFETIME      – sticky IP duration, e.g. "30m", "7d" (default: "7d")
    PROXY_COUNTRY               – target country code, e.g. "de" (optional)
    PROXY_IP_POOL_SIZE          – number of IP slots in the pool (default: 50)

When ``PROXY_PROVIDER=none``, the :class:`NoOpProxyProvider` is returned
and all users fall back to the global ``TELEGRAM_PROXY_URL`` or connect
directly.
"""

from __future__ import annotations

import hashlib
import logging
import os
from uuid import UUID

logger = logging.getLogger(__name__)


class IPRoyalProxyProvider:
    """Generate per-user SOCKS5 proxy configs via IPRoyal's residential gateway.

    IPRoyal embeds session parameters in the password field.  Same
    session ID = same sticky residential IP for ``lifetime`` duration.
    SOCKS5 is required for Telethon (raw TCP to Telegram servers).

    ::

        socks5://user:pass_country-de_session-{sid}_lifetime-7d_streaming-1
               @geo.iproyal.com:12321

        User A → session-slot0001 → IP 92.208.104.15  (sticky 7 days)
        User B → session-slot0002 → IP 84.59.143.74   (sticky 7 days)

    IP sharing: users are distributed across ``ip_pool_size`` IP slots
    via consistent hashing.  With pool_size=50 and 150 users, each IP
    serves ~3 users.  Cost = pool_size * per-IP price/month.
    """

    def __init__(
        self,
        gateway_host: str,
        gateway_port: int,
        username: str,
        password: str,
        session_lifetime: str = "7d",
        country: str | None = None,
        ip_pool_size: int = 50,
    ) -> None:
        self._gateway_host = gateway_host
        self._gateway_port = gateway_port
        self._username = username
        self._base_password = password
        self._lifetime = session_lifetime
        self._country = country
        self._ip_pool_size = max(1, ip_pool_size)

    def _session_id_for_user(self, user_id: UUID) -> str:
        """Derive a session ID for this user.

        Users are distributed across ``ip_pool_size`` slots via
        consistent hashing.  Same user always maps to the same slot.
        """
        uid_hex = str(user_id).replace("-", "")
        uid_hash = int(hashlib.sha256(uid_hex.encode()).hexdigest(), 16)
        slot = uid_hash % self._ip_pool_size
        return f"slot{slot:04d}"

    def get_proxy_for_user(self, user_id: UUID) -> dict:
        """Return a SOCKS5 proxy dict with a sticky session for this user."""
        session_id = self._session_id_for_user(user_id)
        parts = [self._base_password]
        if self._country:
            parts.append(f"country-{self._country}")
        parts.append(f"session-{session_id}")
        parts.append(f"lifetime-{self._lifetime}")
        parts.append("streaming-1")
        password = "_".join(parts)

        return {
            "proxy_type": "socks5",
            "addr": self._gateway_host,
            "port": self._gateway_port,
            "username": self._username,
            "password": password,
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
        host = os.environ.get("PROXY_GATEWAY_HOST", "geo.iproyal.com")
        port_str = os.environ.get("PROXY_GATEWAY_PORT", "12321")
        username = os.environ.get("PROXY_USERNAME", "")
        password = os.environ.get("PROXY_PASSWORD", "")
        lifetime = os.environ.get("PROXY_SESSION_LIFETIME", "7d")
        country = os.environ.get("PROXY_COUNTRY") or None
        pool_size = int(os.environ.get("PROXY_IP_POOL_SIZE", "50"))

        if not username or not password:
            logger.warning(
                "PROXY_PROVIDER=iproyal but missing required env vars "
                "(PROXY_USERNAME, PROXY_PASSWORD). "
                "Falling back to no proxy."
            )
            return NoOpProxyProvider()

        proxy_provider = IPRoyalProxyProvider(
            gateway_host=host,
            gateway_port=int(port_str),
            username=username,
            password=password,
            session_lifetime=lifetime,
            country=country,
            ip_pool_size=pool_size,
        )
        logger.info(
            "Proxy provider: IPRoyal (gateway=%s:%s, lifetime=%s, "
            "country=%s, pool_size=%d)",
            host, port_str, lifetime, country or "any", pool_size,
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
