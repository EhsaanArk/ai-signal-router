"""Resend-based email notification adapter.

Implements :class:`~src.core.notifications.NotificationPort` by sending
dispatch summary emails via the Resend API.
"""

from __future__ import annotations

import asyncio
import logging
import time

import resend
import sentry_sdk

from src.core.models import DispatchResult

logger = logging.getLogger(__name__)

# Track quota errors to avoid spamming Sentry with identical reports.
# Once we detect a quota error, suppress Sentry reports for 1 hour.
_quota_hit_at: float = 0.0
_QUOTA_SUPPRESS_SECONDS = 3600  # 1 hour


def _handle_resend_error(exc: Exception, context: str) -> None:
    """Handle Resend API errors with quota-aware Sentry suppression.

    Quota errors ("daily email sending quota") are logged as warnings and
    reported to Sentry at most once per hour. All other errors are reported
    normally.
    """
    global _quota_hit_at
    is_quota = "quota" in str(exc).lower()

    if is_quota:
        now = time.monotonic()
        if now - _quota_hit_at < _QUOTA_SUPPRESS_SECONDS:
            # Already reported recently — just log, don't spam Sentry
            logger.warning("Resend quota still exceeded — suppressing Sentry (%s)", context)
            return
        _quota_hit_at = now
        logger.warning("Resend daily quota hit — suppressing further Sentry reports for 1h (%s)", context)

    logger.error("Failed to send email (%s): %s", context, exc)
    sentry_sdk.capture_exception(exc)


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
        # Set the module-level API key once, not on every send call.
        if api_key:
            resend.api_key = api_key

    async def send_raw_email(
        self, to: str, subject: str, html: str,
    ) -> None:
        """Send an arbitrary email via Resend.

        Silently skips when the API key is not configured.
        """
        if not self._api_key:
            logger.debug("RESEND_API_KEY not set — skipping email")
            return
        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [to],
                "subject": subject,
                "html": html,
            })
        except Exception as exc:
            _handle_resend_error(exc, f"raw email: {subject}")

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
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": subject,
                "html": html_body,
            })
            logger.info("Dispatch summary email sent to %s", user_email)
        except Exception as exc:
            _handle_resend_error(exc, f"dispatch summary: {signal_symbol}")

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
        "auth_key_duplicated_permanent": (
            "Your Telegram session had a connection conflict",
            "Multiple connections tried to use the same session simultaneously "
            "and recovery attempts were unsuccessful. "
            "Please reconnect your Telegram account to create a fresh session.",
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
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": subject,
                "html": html,
            })
            logger.info("Disconnect alert email sent to %s (reason=%s)", user_email, reason)
        except Exception as exc:
            _handle_resend_error(exc, f"disconnect alert: {reason}")

    # ------------------------------------------------------------------
    # Milestone emails (welcome sequence)
    # ------------------------------------------------------------------

    async def send_welcome(self, user_email: str, frontend_url: str) -> None:
        """Send welcome email after registration with quick-start guide."""
        if not self._api_key:
            return

        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
            'max-width:480px;margin:0 auto;padding:20px">'
            "<h2>Welcome to Sage Radar AI!</h2>"
            "<p>You're in. Here's how to get started in 3 steps:</p>"
            "<ol>"
            "<li><strong>Connect your Telegram</strong> — Link your Telegram account "
            "so we can monitor your signal channels.</li>"
            "<li><strong>Create a routing rule</strong> — Pick a channel, map symbols, "
            "and enter your SageMaster webhook URL.</li>"
            "<li><strong>Go live</strong> — Signals will be parsed and routed automatically.</li>"
            "</ol>"
            f'<p style="text-align:center;margin:24px 0">'
            f'<a href="{frontend_url}/setup" target="_blank" '
            'style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;'
            'border-radius:6px;text-decoration:none;font-weight:600">Get Started →</a></p>'
            '<p style="font-size:13px;color:#666">If you have questions, reply to this email '
            "or reach out at support@sagemaster.com.</p>"
            "</body></html>"
        )

        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": "Welcome to Sage Radar AI — Get started in 3 steps",
                "html": html,
            })
            logger.info("Welcome email sent to %s", user_email)
        except Exception as exc:
            _handle_resend_error(exc, "welcome email")

    async def send_telegram_connected(
        self, user_email: str, frontend_url: str,
    ) -> None:
        """Send milestone email when user connects their Telegram account."""
        if not self._api_key:
            return

        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
            'max-width:480px;margin:0 auto;padding:20px">'
            "<h2>Telegram Connected!</h2>"
            "<p>Your Telegram account is now linked to Sage Radar AI. "
            "We're ready to monitor your signal channels.</p>"
            "<p><strong>Next step:</strong> Create your first routing rule to start "
            "forwarding signals to SageMaster.</p>"
            f'<p style="text-align:center;margin:24px 0">'
            f'<a href="{frontend_url}/routing-rules/new" target="_blank" '
            'style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;'
            'border-radius:6px;text-decoration:none;font-weight:600">Create Routing Rule →</a></p>'
            '<p style="font-size:13px;color:#666">Your Telegram session is encrypted '
            "with AES-256-GCM and stored securely.</p>"
            "</body></html>"
        )

        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": "Telegram connected — Create your first route",
                "html": html,
            })
            logger.info("Telegram connected email sent to %s", user_email)
        except Exception as exc:
            _handle_resend_error(exc, "telegram connected email")

    async def send_first_signal_routed(
        self, user_email: str, symbol: str, frontend_url: str,
    ) -> None:
        """Send celebration email when user's first signal is successfully routed."""
        if not self._api_key:
            return

        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
            'max-width:480px;margin:0 auto;padding:20px">'
            f"<h2>Your first signal was routed!</h2>"
            f"<p>A <strong>{symbol}</strong> signal was just parsed and sent to "
            "SageMaster. Your pipeline is live and working.</p>"
            "<p>From here, you can:</p>"
            "<ul>"
            "<li>Add more routing rules to cover additional channels</li>"
            "<li>Customize symbol mappings and risk settings</li>"
            "<li>Check your signal logs for processing details</li>"
            "</ul>"
            f'<p style="text-align:center;margin:24px 0">'
            f'<a href="{frontend_url}/logs" target="_blank" '
            'style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;'
            'border-radius:6px;text-decoration:none;font-weight:600">View Signal Logs →</a></p>'
            '<p style="font-size:13px;color:#666">Signals are being routed automatically. '
            "You don't need to do anything — just let it run.</p>"
            "</body></html>"
        )

        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": self._from_address,
                "to": [user_email],
                "subject": f"Your first signal was routed — {symbol}",
                "html": html,
            })
            logger.info("First signal routed email sent to %s", user_email)
        except Exception as exc:
            _handle_resend_error(exc, f"first signal routed: {symbol}")
