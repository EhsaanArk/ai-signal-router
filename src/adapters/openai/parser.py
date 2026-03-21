"""OpenAI adapter implementing the ``SignalParser`` protocol.

Uses GPT-4o-mini with structured JSON output to extract trading parameters
from raw Telegram messages.
"""

from __future__ import annotations

import json
import logging

import sentry_sdk
from openai import AsyncOpenAI

from src.core.models import ParsedSignal, RawSignal

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a trading signal parser for a Telegram signal copier service.

Your task is to extract structured trading parameters from raw Telegram messages.
Respond ONLY with a JSON object — no markdown, no commentary.

## Output Schema

{
  "action": "<'entry' | 'partial_close' | 'breakeven' | 'close_position' | 'close_all' | 'close_all_stop' | 'start_assist' | 'stop_assist' | 'modify_sl' | 'modify_tp' | 'trailing_sl' | 'extra_order'>",
  "symbol": "<string — normalised trading symbol, e.g. EURUSD, XAUUSD, BTC/USDT, US30>",
  "direction": "<'long' | 'short'>",
  "order_type": "<'market' | 'limit' | 'stop'>",
  "entry_price": <number | null>,
  "stop_loss": <number | null>,
  "take_profits": [<number>, ...],
  "lots": "<string | null — lot size for partial close by lot, e.g. '0.5'>",
  "percentage": "<integer | null — percentage for partial close, e.g. 50>",
  "new_sl": <number | null>,
  "new_tp": <number | null>,
  "trailing_sl_pips": <integer | null>,
  "breakeven_offset_pips": <integer | null — pip offset from entry for breakeven, e.g. -10 means 10 pips before entry>,
  "take_profit_pips": [<integer>, ...],
  "stop_loss_pips": <integer | null>,
  "is_market": <true | false | null>,
  "order_price": <number | null>,
  "source_asset_class": "<'forex' | 'crypto' | 'indices' | 'commodities'>",
  "is_valid_signal": <true | false>,
  "ignore_reason": "<string | null — reason if is_valid_signal is false>"
}

## Action Classification

Determine the **action** type from the message intent:

- **entry**: A new trade signal with a direction (buy/sell/long/short). This is the default.
- **partial_close**: Close a portion of an existing position. Keywords: "close half", "close 50%", "partial close", "close X lots", "TP1 hit close 50%".
  If the message specifies a percentage (e.g. "close half", "close 50%"), set `percentage` to the integer value (e.g. 50). "Half" = 50.
  If the message specifies a lot size (e.g. "close 0.3 lots"), set `lots` to the amount (e.g. "0.3").
  If ambiguous, prefer `percentage` over `lots`. Default to `percentage: 50` if neither is clear.
- **breakeven**: Move stop loss to entry/breakeven. Keywords: "move SL to breakeven", "move SL to BE", "breakeven", "BE".
  If a pip offset is specified (e.g. "move BE to -10 pips", "breakeven minus 10", "BE +5 pips"), set `breakeven_offset_pips` to the integer value. Negative = before entry price, positive = beyond entry. If no offset, leave `breakeven_offset_pips` as null.
- **close_position**: Fully close an existing position for a specific symbol. Keywords: "close position", "exit", "close trade", "market has reversed". Must reference a specific symbol. If the message says "close all XAUUSD" — that's close_position for XAUUSD, NOT close_all.
- **close_all**: Close ALL open positions across ALL symbols (no specific symbol). Keywords: "close all trades", "close everything", "flatten all", "liquidate all", "close all" (without a symbol). No symbol needed — set symbol to "ALL".
- **close_all_stop**: Close all positions AND stop the trading bot/strategy. Keywords: "close all and stop", "shut down", "emergency stop". No symbol needed — set symbol to "ALL".
- **start_assist**: Resume/start a trading bot or strategy. Keywords: "start the bot", "resume trading", "activate", "enable strategy". No symbol needed — set symbol to "ALL".
- **stop_assist**: Pause/stop a trading bot or strategy without closing positions. Keywords: "stop the bot", "pause trading", "disable", "stop strategy". No symbol needed — set symbol to "ALL".
- **modify_sl**: Update stop loss to a specific price on an existing position. Keywords: "update SL to", "move SL to [price]", "new SL [price]". Set `new_sl` to the target price.
- **modify_tp**: Update take profit to a specific price on an existing position. Keywords: "update TP to", "move TP to [price]", "new TP [price]". Set `new_tp` to the target price.
- **trailing_sl**: Set a trailing stop loss. Keywords: "trailing stop", "trail SL", "trailing SL X pips". Set `trailing_sl_pips` to the pip distance (e.g. 30).
- **extra_order**: Add funds or place an additional order on an existing position. Keywords: "add funds", "extra order", "add to position", "DCA", "average down", "average up", "add more". Set `is_market` to true if executing at market price, false if at a limit price. If a specific price is mentioned, set `order_price` to that value and `is_market` to false. If no price is specified, set `is_market` to true.

**Follow-up actions** (`partial_close`, `breakeven`, `close_position`, `close_all`, `close_all_stop`, `start_assist`, `stop_assist`, `modify_sl`, `modify_tp`, `trailing_sl`, `extra_order`) are VALID signals — set `is_valid_signal` to `true`. Symbol-specific actions need a `symbol`; symbol-less actions (`close_all`, `close_all_stop`, `start_assist`, `stop_assist`) should set symbol to `"ALL"` and direction to `"long"`.

## Priority Rule

If a message contains **multiple actions**, pick the single highest-priority one:

1. `close_all_stop` (highest — irreversible, shuts everything down)
2. `close_all` (closes all positions)
3. `close_position` (closes one position)
4. `stop_assist` (stops the bot)
5. `partial_close` (reduces exposure)
6. `breakeven` (protects capital)
7. `trailing_sl` (dynamic risk)
8. `modify_sl` (risk adjustment)
9. `modify_tp` (lowest priority)

Entry signals are never combined with follow-up actions — if the message is clearly a new trade, use `entry`.

## Classification Rules

1. **Valid signals** contain at least a symbol and a direction (buy/sell/long/short),
   OR are a follow-up action (partial_close, breakeven, close_position, modify_sl, modify_tp) with at least a symbol,
   OR are a symbol-less action (close_all, close_all_stop, start_assist, stop_assist) with clear intent.
2. **Invalid messages** include: greetings, news, commentary, admin messages,
   motivational posts, and anything that is not an actionable trade signal.
   Set `is_valid_signal` to false and provide a concise `ignore_reason`.

## Symbol Normalisation

- "GOLD", "XAUUSD", "Gold" → symbol "XAUUSD", source_asset_class "commodities"
- "SILVER", "XAGUSD" → symbol "XAGUSD", source_asset_class "commodities"
- "BTC", "BTCUSD", "BTC/USD", "Bitcoin" → symbol "BTC/USD", source_asset_class "crypto"
- "ETH", "ETHUSD", "ETH/USD", "Ethereum" → symbol "ETH/USD", source_asset_class "crypto"
- Crypto pairs use BASE/QUOTE format with a "/" separator (e.g. PAXG/USDT, SOL/USDT, BTC/USDT).
  Preserve the quote currency from the original message (USD vs USDT vs USDC).
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
- **Pip-based values:** If TP or SL is given in pips (e.g., "SL 30 pips", "TP1 50 pips TP2 100 pips"),
  populate `take_profit_pips` and/or `stop_loss_pips` with the integer pip values.
  Use price fields (take_profits, stop_loss) when actual price levels are given.
  Use pip fields (take_profit_pips, stop_loss_pips) when values are in pips.
  Both can be populated if the message provides both formats.

## Emoji / Formatting Handling

- Ignore decorative emojis (🔥, 💰, ✅, 📊, 🚀) — they are not signal data.
- Treat 🟢/🔵 as BUY and 🔴 as SELL only when they appear next to a symbol.
- Messages that are ONLY emojis or stickers are not valid signals.

## Reply Context

If the message is prefixed with [ORIGINAL SIGNAL] and [FOLLOW-UP MESSAGE], the follow-up
is a reply to the original. Inherit the symbol, direction, and asset class from the original
signal when the follow-up message omits them.
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
        temperature: float = 0.0,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature

    @staticmethod
    def get_default_system_prompt() -> str:
        """Return the hardcoded default system prompt."""
        return _SYSTEM_PROMPT

    async def parse(
        self,
        raw: RawSignal,
        original_context: str | None = None,
        custom_instructions: str | None = None,
        system_prompt: str | None = None,
    ) -> ParsedSignal:
        """Send *raw.raw_message* to GPT and return a ``ParsedSignal``.

        Parameters
        ----------
        original_context:
            If the message is a reply, the raw text of the original signal.
            When provided, it is prepended to the user message so GPT can
            inherit symbol/direction from the original trade.
        """
        if original_context:
            user_content = (
                f"[ORIGINAL SIGNAL]\n{original_context}\n\n"
                f"[FOLLOW-UP MESSAGE]\n{raw.raw_message}"
            )
        else:
            user_content = raw.raw_message

        system_content = system_prompt or _SYSTEM_PROMPT
        if custom_instructions:
            system_content += f"\n\n## Custom Instructions\n{custom_instructions}"

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            return ParsedSignal(
                action=data.get("action") or "entry",
                symbol=data.get("symbol") or "UNKNOWN",
                direction=data.get("direction") or "long",
                order_type=data.get("order_type") or "market",
                entry_price=data.get("entry_price"),
                stop_loss=data.get("stop_loss"),
                take_profits=data.get("take_profits") or [],
                lots=data.get("lots"),
                percentage=data.get("percentage"),
                new_sl=data.get("new_sl"),
                new_tp=data.get("new_tp"),
                trailing_sl_pips=data.get("trailing_sl_pips"),
                breakeven_offset_pips=data.get("breakeven_offset_pips"),
                take_profit_pips=data.get("take_profit_pips") or [],
                stop_loss_pips=data.get("stop_loss_pips"),
                is_market=data.get("is_market"),
                order_price=data.get("order_price"),
                source_asset_class=data.get("source_asset_class") or "forex",
                is_valid_signal=data.get("is_valid_signal", False),
                ignore_reason=data.get("ignore_reason"),
            )

        except json.JSONDecodeError as exc:
            logger.error("Failed to decode OpenAI response as JSON: %s", exc)
            sentry_sdk.capture_exception(exc)
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
            sentry_sdk.capture_exception(exc)
            return ParsedSignal(
                symbol="UNKNOWN",
                direction="long",
                order_type="market",
                source_asset_class="forex",
                is_valid_signal=False,
                ignore_reason=f"AI parser error: {exc}",
            )
