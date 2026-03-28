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
        self._base_url = _BOT_API_BASE.format(token=bot_token) if bot_token else ""

    @property
    def _enabled(self) -> bool:
        return bool(self._bot_token)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
    ) -> None:
        """Send a message via the Bot API with optional inline keyboard."""
        if not self._enabled:
            return
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self._post("sendMessage", payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> None:
        """Acknowledge an inline keyboard callback query."""
        if not self._enabled:
            return
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self._post("answerCallbackQuery", payload)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "Markdown",
    ) -> None:
        """Edit the text of an existing message."""
        if not self._enabled:
            return
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        await self._post("editMessageText", payload)

    async def _post(self, method: str, payload: dict) -> None:
        """POST to the Telegram Bot API, logging errors and capturing to Sentry."""
        url = f"{self._base_url}/{method}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.error("Telegram Bot API %s error %s: %s", method, resp.status_code, resp.text)
        except Exception as exc:
            logger.error("Telegram Bot API %s failed: %s", method, exc)
            sentry_sdk.capture_exception(exc)

    async def send_dispatch_summary(
        self,
        chat_id: int,
        signal_symbol: str,
        results: list[DispatchResult],
    ) -> None:
        """Send a Markdown-formatted summary to the user's Telegram chat."""
        if not self._enabled:
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
        await self.send_message(chat_id, text)


def _escape_md(text: str) -> str:
    """Escape Markdown special characters for Telegram."""
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, f"\\{ch}")
    return text
