"""OpenAI adapter implementing the ``SignalParser`` protocol.

Uses GPT-4o-mini with structured JSON output to extract trading parameters
from raw Telegram messages.
"""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from src.core.models import ParsedSignal, RawSignal

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a trading signal parser for a Telegram signal copier service.

Your task is to extract structured trading parameters from raw Telegram messages.
Respond ONLY with a JSON object — no markdown, no commentary.

## Output Schema

{
  "symbol": "<string — normalised trading symbol, e.g. EURUSD, XAUUSD, BTCUSD, US30>",
  "direction": "<'long' | 'short'>",
  "order_type": "<'market' | 'limit' | 'stop'>",
  "entry_price": <number | null>,
  "stop_loss": <number | null>,
  "take_profits": [<number>, ...],
  "source_asset_class": "<'forex' | 'crypto' | 'indices' | 'commodities'>",
  "is_valid_signal": <true | false>,
  "ignore_reason": "<string | null — reason if is_valid_signal is false>"
}

## Classification Rules

1. **Valid signals** contain at least a symbol and a direction (buy/sell/long/short).
2. **Invalid messages** include: greetings, news, commentary, admin messages,
   motivational posts, and anything that is not an actionable trade signal.
   Set `is_valid_signal` to false and provide a concise `ignore_reason`.

## Symbol Normalisation

- "GOLD", "XAUUSD", "Gold" → symbol "XAUUSD", source_asset_class "commodities"
- "SILVER", "XAGUSD" → symbol "XAGUSD", source_asset_class "commodities"
- "BTC", "BTCUSD", "Bitcoin" → symbol "BTCUSD", source_asset_class "crypto"
- "ETH", "ETHUSD", "Ethereum" → symbol "ETHUSD", source_asset_class "crypto"
- Forex pairs (e.g. EURUSD, GBPJPY) → source_asset_class "forex"
- Indices (US30, NAS100, SPX500, DAX, USTEC) → source_asset_class "indices"
- If unclear, default source_asset_class to "forex".

## Direction Mapping

- "BUY", "LONG", "🟢", "🔵", "⬆️" → direction "long"
- "SELL", "SHORT", "🔴", "⬇️" → direction "short"

## Order Type Detection

- If the message says "market", "now", "instant", or gives no explicit entry price
  context, set order_type to "market".
- If the message says "limit", "buy limit", "sell limit", or specifies an entry
  price with the word "limit" or "@", set order_type to "limit".
- If the message says "stop", "buy stop", "sell stop", set order_type to "stop".
- Default to "market" if ambiguous.

## Take Profit / Stop Loss

- Extract ALL TP levels mentioned (TP1, TP2, TP3, etc.) into the take_profits array.
- "SL", "Stop Loss", "❌" → stop_loss
- If only one TP is mentioned, still return it as a single-element array.
- entry_price can be null for market orders where no specific price is given.

## Emoji / Formatting Handling

- Ignore decorative emojis (🔥, 💰, ✅, 📊, 🚀) — they are not signal data.
- Treat 🟢/🔵 as BUY and 🔴 as SELL only when they appear next to a symbol.
- Messages that are ONLY emojis or stickers are not valid signals.
"""


class OpenAISignalParser:
    """Concrete ``SignalParser`` backed by the OpenAI Chat Completions API.

    Parameters
    ----------
    api_key:
        An OpenAI API key with access to the ``gpt-4o-mini`` model.
    model:
        Override the model name (useful for testing with cheaper models).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def parse(self, raw: RawSignal) -> ParsedSignal:
        """Send *raw.raw_message* to GPT and return a ``ParsedSignal``."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": raw.raw_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            return ParsedSignal(
                symbol=data.get("symbol") or "UNKNOWN",
                direction=data.get("direction") or "long",
                order_type=data.get("order_type") or "market",
                entry_price=data.get("entry_price"),
                stop_loss=data.get("stop_loss"),
                take_profits=data.get("take_profits") or [],
                source_asset_class=data.get("source_asset_class") or "forex",
                is_valid_signal=data.get("is_valid_signal", False),
                ignore_reason=data.get("ignore_reason"),
            )

        except json.JSONDecodeError as exc:
            logger.error("Failed to decode OpenAI response as JSON: %s", exc)
            return ParsedSignal(
                symbol="UNKNOWN",
                direction="long",
                order_type="market",
                source_asset_class="forex",
                is_valid_signal=False,
                ignore_reason=f"JSON decode error from AI response: {exc}",
            )
        except Exception as exc:
            logger.exception("OpenAI API call failed")
            return ParsedSignal(
                symbol="UNKNOWN",
                direction="long",
                order_type="market",
                source_asset_class="forex",
                is_valid_signal=False,
                ignore_reason=f"AI parser error: {exc}",
            )
