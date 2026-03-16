"""Telegram Bot notification adapter.

Sends dispatch summary messages via the Telegram Bot API using httpx.
No additional dependency required — httpx is already in the stack.
"""

from __future__ import annotations

import logging

import httpx
import sentry_sdk

from src.core.models import DispatchResult

logger = logging.getLogger(__name__)

_BOT_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramNotifier:
    """Send dispatch summary messages via a shared Telegram bot.

    If ``bot_token`` is empty the notifier silently no-ops so that local
    development works without a real bot token.
    """

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token

    async def send_dispatch_summary(
        self,
        chat_id: int,
        signal_symbol: str,
        results: list[DispatchResult],
    ) -> None:
        """Send a Markdown-formatted summary to the user's Telegram chat."""
        if not self._bot_token:
            logger.debug("TELEGRAM_BOT_TOKEN not set — skipping Telegram notification")
            return

        succeeded = [r for r in results if r.status == "success"]
        failed = [r for r in results if r.status == "failed"]

        lines = [
            f"*Signal Routed: {_escape_md(signal_symbol)}*",
            f"✅ {len(succeeded)} succeeded, ❌ {len(failed)} failed",
        ]

        if failed:
            lines.append("")
            lines.append("*Failed:*")
            for r in failed:
                lines.append(f"• {_escape_md(r.error_message or 'Unknown error')}")

        text = "\n".join(lines)

        url = f"{_BOT_API_BASE.format(token=self._bot_token)}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.error(
                        "Telegram Bot API error %s: %s",
                        resp.status_code,
                        resp.text,
                    )
                else:
                    logger.info("Telegram notification sent to chat_id=%s", chat_id)
        except Exception as exc:
            logger.error("Failed to send Telegram notification: %s", exc)
            sentry_sdk.capture_exception(exc)


def _escape_md(text: str) -> str:
    """Escape Markdown special characters for Telegram."""
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, f"\\{ch}")
    return text
