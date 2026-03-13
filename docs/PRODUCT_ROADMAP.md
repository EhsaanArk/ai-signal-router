# Product Roadmap: V1 to V3

This document outlines the definitive feature breakdown for the SageMaster Telegram Signal Copier across its first three major releases.

## V1 — MVP: Core Routing (Weeks 1-6)
The goal is to prove the core value: reliably parse Telegram signals and route them to SageMaster.

| Feature | Description |
|---------|-------------|
| **AI Signal Parsing** | GPT-4o-mini parses standard Buy/Sell signals (Entry, SL, TP) from any text format or language. |
| **Multi-Destination Routing** | Route 1 Telegram channel to multiple SageMaster webhook URLs (Channel X → Bot 1, Bot 2, Bot 3). |
| **Symbol Mapping** | Per-destination dictionary (e.g., GOLD → XAUUSD, NAS100 → USTEC). |
| **Order Types** | Market, Limit, and Stop orders based on parsed signal. |
| **Single TP Handling** | Routes TP1 only. If signal has multiple TPs, only the first is sent (keeps V1 simple). |
| **Configurable Notifications** | Email or Telegram alerts when a signal is successfully routed. |
| **Standalone Dashboard** | Separate branded web app (React/Next.js) — connect Telegram, configure routing rules, view logs. |
| **Tier Enforcement** | Enforce active destination limits based on subscription tier (Free, Starter, Pro, Elite). |

## V2 — Advanced Trade Management (Weeks 7-12)
The goal is to match the advanced features of top competitors (TelegramFxCopier, Copygram) using SageMaster's V2 webhook capabilities.

| Feature | Description |
|---------|-------------|
| **Multiple TPs** | Parse TP1, TP2, TP3 and send them as an array in the V2 webhook payload. |
| **Provider Commands** | Parse "Close Half", "Close All", "Move SL to Entry" messages and send V2 `partially_close_by_lot` or `breakeven` webhooks. |
| **Trailing SL** | Parse trailing stop instructions and pass them to SageMaster. |
| **Risk Overrides** | Allow users to override the signal's lot size or risk % on a per-destination basis. |
| **Keyword Filter** | Ignore signals containing specific words (e.g., "Scalp", "High Risk"). |
| **MT5 EA Source** | Add a new `SignalSource` adapter to receive signals from an MT5 Expert Advisor, expanding beyond Telegram. |

## V3 — Analytics & Protection (Future)
The goal is to become the premium, undisputed leader in the space.

| Feature | Description |
|---------|-------------|
| **Equity Guardian** | Global daily loss limits across all copiers. |
| **News Filter** | Pause copying 30 mins before/after high-impact news events (Forex Factory API). |
| **Analytics Dashboard** | Win rate, drawdown, and profitability metrics per Telegram channel. |
| **Backtesting** | "Test before you trust" — run a channel's historical signals through a simulator before connecting a live webhook. |
| **Discord Source** | Add a new `SignalSource` adapter to read signals from Discord servers. |

## Feature Matrix by Tier

| Feature | Free | Starter ($29) | Pro ($59) | Elite ($99) |
|---------|------|---------------|-----------|-------------|
| AI Signal Parsing | Yes | Yes | Yes | Yes |
| Active Destinations | 1 | 2 | 5 | 15 |
| Telegram Channels | Unlimited | Unlimited | Unlimited | Unlimited |
| Symbol Mapping | Yes | Yes | Yes | Yes |
| Single TP | Yes | Yes | Yes | Yes |
| Signal Logs | Yes | Yes | Yes | Yes |
| Notifications | No | Yes | Yes | Yes |
| Multiple TPs (V2) | — | — | Yes | Yes |
| Trailing SL (V2) | — | — | Yes | Yes |
| Auto-Breakeven (V2) | — | — | Yes | Yes |
| Provider Commands (V2) | — | — | — | Yes |
| Risk Overrides (V2) | — | — | Yes | Yes |
| Keyword Filter (V2) | — | — | Yes | Yes |
| MT5 EA Source (V2) | — | — | Yes | Yes |
| Equity Guardian (V3) | — | — | — | Yes |
| News Filter (V3) | — | — | — | Yes |
| Analytics Dashboard (V3) | — | — | — | Yes |
| Backtesting (V3) | — | — | — | Yes |
