"""Resend-based email notification adapter.

Implements :class:`~src.core.notifications.NotificationPort` by sending
dispatch summary emails via the Resend API.
"""

from __future__ import annotations

import asyncio
import logging

import resend
import sentry_sdk

from src.core.models import DispatchResult

logger = logging.getLogger(__name__)


class ResendNotifier:
    """Send dispatch summary emails using Resend.

    If ``api_key`` is empty the notifier silently no-ops so that local
    development works without a real Resend account.
    """

    def __init__(
        self,
        api_key: str,
        from_address: str = "Sage Radar AI <noreply@radar.sagemaster.com>",
    ) -> None:
        self._api_key = api_key
        self._from_address = from_address

    async def send_dispatch_summary(
        self,
        user_email: str,
        signal_symbol: str,
        results: list[DispatchResult],
    ) -> None:
        """Send a summary email for the dispatched signal.

        Silently skips if ``api_key`` is not configured.
        """
        if not self._api_key:
            logger.debug("RESEND_API_KEY not set — skipping notification")
            return

        succeeded = [r for r in results if r.status == "success"]
        failed = [r for r in results if r.status == "failed"]

        subject = (
            f"Signal Routed: {signal_symbol} — "
            f"{len(succeeded)} success, {len(failed)} failed"
        )

        lines = [
            f"<h2>Signal: {signal_symbol}</h2>",
            f"<p><strong>{len(succeeded)}</strong> destination(s) succeeded, "
            f"<strong>{len(failed)}</strong> failed.</p>",
        ]

        if failed:
            lines.append("<h3>Failed Destinations</h3><ul>")
            for r in failed:
                lines.append(f"<li>{r.error_message or 'Unknown error'}</li>")
            lines.append("</ul>")

        html_body = "\n".join(lines)

        try:
            resend.api_key = self._api_key
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": subject,
                "html": html_body,
            })
            logger.info("Dispatch summary email sent to %s", user_email)
        except Exception as exc:
            logger.error("Failed to send notification email: %s", exc)
            sentry_sdk.capture_exception(exc)

    # Reason code → (user-friendly headline, actionable guidance)
    _DISCONNECT_COPY: dict[str, tuple[str, str]] = {
        "session_expired": (
            "Your Telegram session expired",
            "This usually happens when you log out of Telegram on another device "
            "or revoke active sessions in Telegram's privacy settings. "
            "Reconnect your account to resume signal routing.",
        ),
        "flood_wait_exhausted": (
            "Telegram temporarily blocked your account",
            "Telegram rate-limited your account due to too many requests. "
            "This is temporary — wait 30 minutes, then reconnect.",
        ),
        "decrypt_failed": (
            "Session data could not be decrypted",
            "This can happen after a server-side encryption key rotation. "
            "Please reconnect your Telegram account to create a new session.",
        ),
    }

    async def send_disconnect_alert(
        self,
        user_email: str,
        reason: str,
    ) -> None:
        """Send a disconnect notification email with actionable guidance.

        Parameters
        ----------
        user_email:
            Recipient email address.
        reason:
            Disconnect reason code (``session_expired``, ``flood_wait_exhausted``,
            ``decrypt_failed``).
        """
        if not self._api_key:
            return

        headline, guidance = self._DISCONNECT_COPY.get(
            reason,
            ("Your Telegram session was disconnected", "Please reconnect to resume signal routing."),
        )

        subject = "Sage Radar AI — Telegram disconnected"
        html = (
            f"<h2>Telegram Disconnected</h2>"
            f"<p><strong>{headline}.</strong></p>"
            f"<p>{guidance}</p>"
            f"<p>Signal routing has been paused until you reconnect.</p>"
            f"<p><a href='https://app.sageradar.ai/telegram'>Reconnect now →</a></p>"
        )

        try:
            resend.api_key = self._api_key
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": subject,
                "html": html,
            })
            logger.info("Disconnect alert email sent to %s (reason=%s)", user_email, reason)
        except Exception as exc:
            logger.error("Failed to send disconnect alert email: %s", exc)
            sentry_sdk.capture_exception(exc)
