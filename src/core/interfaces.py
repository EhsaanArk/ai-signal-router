"""Port interfaces (Protocol classes) for the SGM Telegram Signal Copier.

Every adapter in ``src/adapters/`` must satisfy one of these protocols.  The
core domain logic depends ONLY on these abstractions — never on concrete
infrastructure.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.core.models import (
    DispatchJob,
    DispatchResult,
    ParsedSignal,
    RawSignal,
    RoutingRule,
    User,
)


# ---------------------------------------------------------------------------
# Signal source (Telegram, MT5 EA, Discord, etc.)
# ---------------------------------------------------------------------------

class SignalSource(Protocol):
    """Lifecycle interface for a signal input (e.g. Telegram listener).

    Implementations push ``RawSignal`` objects to a ``QueuePort`` internally;
    this protocol only governs start/stop lifecycle.
    """

    async def start(self) -> None:
        """Begin listening for signals."""
        ...

    async def stop(self) -> None:
        """Gracefully stop listening."""
        ...


# ---------------------------------------------------------------------------
# Signal parsing
# ---------------------------------------------------------------------------

class SignalParser(Protocol):
    """Parses a raw Telegram message into a structured signal."""

    async def parse(self, raw: RawSignal) -> ParsedSignal:
        """Parse *raw* into a ``ParsedSignal``.

        Implementations may call an LLM, apply regex heuristics, or combine
        both strategies.
        """
        ...


# ---------------------------------------------------------------------------
# Signal dispatching
# ---------------------------------------------------------------------------

class SignalDispatcher(Protocol):
    """Sends a parsed signal to a SageMaster webhook endpoint."""

    async def dispatch(
        self, signal: ParsedSignal, rule: RoutingRule
    ) -> DispatchResult:
        """Dispatch *signal* according to *rule* and return the outcome."""
        ...


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

class QueuePort(Protocol):
    """Abstraction over the signal processing queue (QStash or local)."""

    async def enqueue(self, signal: RawSignal) -> None:
        """Place *signal* onto the processing queue."""
        ...


class DispatchQueuePort(Protocol):
    """Abstraction over the Stage 2 dispatch queue (QStash or local)."""

    async def enqueue_dispatch_job(self, job: DispatchJob) -> None:
        """Place a per-rule dispatch *job* onto the dispatch queue."""
        ...


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class CachePort(Protocol):
    """General-purpose cache (rate limiting, dedup, etc.)."""

    async def get(self, key: str) -> str | None:
        """Return the cached value, or ``None`` if absent/expired."""
        ...

    async def set(
        self, key: str, value: str, ttl_seconds: int | None = None
    ) -> None:
        """Store *value* under *key*, optionally expiring after *ttl_seconds*."""
        ...

    async def delete(self, key: str) -> None:
        """Remove *key* from the cache."""
        ...

    async def getdel(self, key: str) -> str | None:
        """Atomically return and delete the cached value (Redis 6.2+ GETDEL)."""
        ...


# ---------------------------------------------------------------------------
# Session storage (encrypted Telegram session strings)
# ---------------------------------------------------------------------------

class SessionStore(Protocol):
    """Stores and retrieves encrypted Telegram session strings."""

    async def save_session(self, user_id: UUID, session_string: str) -> None:
        """Persist *session_string* for *user_id*."""
        ...

    async def get_session(self, user_id: UUID) -> str | None:
        """Return the stored session string, or ``None`` if absent."""
        ...

    async def delete_session(self, user_id: UUID) -> None:
        """Remove the stored session for *user_id*."""
        ...


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

class RoutingRuleRepository(Protocol):
    """CRUD operations for routing rules."""

    async def get_rules_for_channel(
        self, user_id: UUID, channel_id: str
    ) -> list[RoutingRule]:
        """Return all active rules matching *user_id* and *channel_id*."""
        ...

    async def create(self, rule: RoutingRule) -> RoutingRule:
        """Persist a new routing rule and return it."""
        ...

    async def get_by_user(self, user_id: UUID) -> list[RoutingRule]:
        """Return every routing rule belonging to *user_id*."""
        ...

    async def count_by_user(self, user_id: UUID) -> int:
        """Return the number of routing rules owned by *user_id*."""
        ...


class SignalLogRepository(Protocol):
    """Append-only log of signal processing events."""

    async def log(
        self,
        user_id: UUID,
        routing_rule_id: UUID | None,
        raw_message: str,
        parsed_data: dict | None,
        webhook_payload: dict | None,
        status: str,
        error_message: str | None,
    ) -> None:
        """Record a signal processing event."""
        ...

    async def get_by_user(
        self, user_id: UUID, limit: int, offset: int
    ) -> list[dict]:
        """Return paginated log entries for *user_id*."""
        ...


class UserRepository(Protocol):
    """CRUD operations for users."""

    async def get_by_email(self, email: str) -> User | None:
        """Look up a user by email address."""
        ...

    async def create(self, email: str, password_hash: str) -> User:
        """Create and return a new user."""
        ...

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Look up a user by primary key."""
        ...


# ---------------------------------------------------------------------------
# Proxy provider (per-user residential proxy for Telegram connections)
# ---------------------------------------------------------------------------

class ProxyProvider(Protocol):
    """Provides per-user proxy configuration for Telegram clients.

    Implementations generate a Telethon-compatible proxy dict for each
    user, enabling per-user IP isolation at scale.  When the provider
    returns ``None``, the caller should fall back to the global proxy
    (``TELEGRAM_PROXY_URL``) or connect directly.
    """

    def get_proxy_for_user(self, user_id: UUID) -> dict | None:
        """Return a Telethon-compatible proxy dict, or ``None``."""
        ...
