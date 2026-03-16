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
        from_address: str = "SageMaster Copier <noreply@sagemaster.io>",
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
