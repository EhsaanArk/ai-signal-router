"""Tests for the notification system — ResendNotifier and preferences."""

from unittest.mock import MagicMock, patch

import pytest

from src.adapters.email.sender import ResendNotifier
from src.core.models import DispatchResult
from src.core.notifications import NotificationPreference


@pytest.mark.asyncio
async def test_sends_on_failure():
    """Should send an email when there are failed dispatches."""
    notifier = ResendNotifier(api_key="test-key")
    results = [
        DispatchResult(status="failed", error_message="HTTP 500: Internal Server Error"),
    ]

    with patch("src.adapters.email.sender.resend") as mock_resend:
        await notifier.send_dispatch_summary("user@example.com", "EURUSD", results)

        mock_resend.Emails.send.assert_called_once()
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["to"] == ["user@example.com"]
        assert "EURUSD" in call_args["subject"]
        assert "1 failed" in call_args["subject"]


@pytest.mark.asyncio
async def test_sends_on_success_when_enabled():
    """Should send email for successful dispatches."""
    notifier = ResendNotifier(api_key="test-key")
    results = [
        DispatchResult(status="success", webhook_payload={"symbol": "EURUSD"}),
    ]

    with patch("src.adapters.email.sender.resend") as mock_resend:
        await notifier.send_dispatch_summary("user@example.com", "EURUSD", results)

        mock_resend.Emails.send.assert_called_once()
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert "1 success" in call_args["subject"]


@pytest.mark.asyncio
async def test_skips_when_no_api_key():
    """Should silently skip if RESEND_API_KEY is empty."""
    notifier = ResendNotifier(api_key="")
    results = [
        DispatchResult(status="failed", error_message="Error"),
    ]

    with patch("src.adapters.email.sender.resend") as mock_resend:
        await notifier.send_dispatch_summary("user@example.com", "EURUSD", results)
        mock_resend.Emails.send.assert_not_called()


@pytest.mark.asyncio
async def test_no_crash_on_resend_error():
    """Should log error but not raise if Resend API fails."""
    notifier = ResendNotifier(api_key="test-key")
    results = [
        DispatchResult(status="failed", error_message="Error"),
    ]

    with patch("src.adapters.email.sender.resend") as mock_resend:
        mock_resend.Emails.send.side_effect = Exception("API error")
        # Should not raise
        await notifier.send_dispatch_summary("user@example.com", "EURUSD", results)


def test_notification_preference_defaults():
    """Default preferences: email on failure, not on success."""
    prefs = NotificationPreference()
    assert prefs.email_on_failure is True
    assert prefs.email_on_success is False


def test_notification_preference_from_dict():
    """Should parse from a dict (as stored in JSONB)."""
    prefs = NotificationPreference(**{"email_on_success": True, "email_on_failure": False})
    assert prefs.email_on_success is True
    assert prefs.email_on_failure is False


def test_notification_preference_empty_dict():
    """Empty dict should use defaults."""
    prefs = NotificationPreference(**{})
    assert prefs.email_on_failure is True
    assert prefs.email_on_success is False
