"""Notification ports and preference models for the signal copier.

Defines the :class:`NotificationPreference` model for per-user settings and
the :class:`NotificationPort` protocol that notification adapters must
implement.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from src.core.models import DispatchResult


class NotificationPreference(BaseModel):
    """Per-user notification preferences stored as JSONB on the user row."""

    email_on_success: bool = False
    email_on_failure: bool = True
    telegram_on_success: bool = False
    telegram_on_failure: bool = False
    telegram_bot_chat_id: int | None = None


class NotificationPort(Protocol):
    """Interface for sending dispatch summary notifications."""

    async def send_dispatch_summary(
        self,
        user_email: str,
        signal_symbol: str,
        results: list[DispatchResult],
    ) -> None: ...
