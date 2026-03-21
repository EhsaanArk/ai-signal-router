# SageMaster Crypto Webhook — Parity Report

**Date:** 2026-03-21
**Author:** Engineering (automated investigation)
**Purpose:** Document gaps between Sage Radar AI's crypto pipeline and SageMaster's actual crypto webhook API.
**For review by:** QA Team, Product Management

---

## Executive Summary

Live testing on 2026-03-21 revealed that **Sage Radar AI uses incorrect webhook action type strings for SageMaster Crypto (DCA)** management actions. SageMaster Crypto uses different action type names than SageMaster Forex — our pipeline was sending forex action types to the crypto webhook, which SageMaster silently ignores.

**Impact:** Close-all, stop assist, and start assist commands sent via Sage Radar AI to crypto DCA assists are silently rejected by SageMaster.

---

## Evidence: SageMaster Crypto Action Types (from live UI)

The following action types were captured directly from the SageMaster DCA Assist UI at:
`https://app.sagemaster.io/ai-assist/dca/dcf5a01f-31dc-4424-9dfd-496d8d24a32e`
(AI Signal Router v1, Paper Trading Bitget)

### Correct Crypto Action Types (from SageMaster UI)

| UI Action | Crypto `type` String | Notes |
|-----------|---------------------|-------|
| Alert to start trade | `start_deal` | Entry signal |
| Alert to Close order at market price | `close_order_at_market_price` | Close single position |
| Alert to close all trades at Market Price | `close_all_deals_at_market_price` | Close ALL positions |
| Alert to close all + stop AI Assist | `close_all_deals_at_market_price_and_stop_ai_assist` | Close all + stop |
| Alert to cancel the trade | `cancel_the_deal` | Cancel without selling |
| Alert to cancel all + stop AI Assist | *(not yet captured)* | Cancel all + stop |
| Alert to cancel all active trades | *(not yet captured)* | Cancel all active |
| Alert to stop AI Assist | `stop_ai_assist` | Pause the assist |
| Alert to start AI Assist and trade | `start_ai_assist_and_deal` | Resume + open trade |

### What Sage Radar AI Currently Sends (INCORRECT for Crypto)

| Action | What We Send (Forex type) | What SageMaster Crypto Expects | Match? |
|--------|--------------------------|-------------------------------|--------|
| Start trade | `start_deal` | `start_deal` | YES |
| Close single | `close_order_at_market_price` | `close_order_at_market_price` | YES |
| Close ALL | `close_all_orders_at_market_price` | `close_all_deals_at_market_price` | **NO** |
| Close ALL + stop | `close_all_orders_at_market_price_and_stop_assist` | `close_all_deals_at_market_price_and_stop_ai_assist` | **NO** |
| Stop assist | `stop_assist` | `stop_ai_assist` | **NO** |
| Start assist | `start_assist` | `start_ai_assist_and_deal` | **NO** |
| Partial close | `partially_closed_by_percentage` | `partially_closed_by_percentage` | YES |
| SL adjustment | `moved_sl_adjustment` | `moved_sl_adjustment` | YES |
| Extra order | `open_extra_order` | `open_extra_order` | YES |

### Key Naming Pattern

- **Forex** uses "orders" and "assist": `close_all_orders_at_market_price`, `stop_assist`
- **Crypto** uses "deals" and "ai_assist": `close_all_deals_at_market_price`, `stop_ai_assist`

---

## Bug #1: close_all Sends Wrong Type (CRITICAL)

**Signal:** "Close all btc trades from this assist"
**What we sent:**
```json
{
  "type": "close_all_orders_at_market_price",
  "aiAssistId": "dcf5a01f-31dc-4424-9dfd-496d8d24a32e",
  "exchange": "pptbitget",
  "date": "2026-03-21T21:40:57Z"
}
```

**What SageMaster expects:**
```json
{
  "type": "close_all_deals_at_market_price",
  "aiAssistId": "dcf5a01f-31dc-4424-9dfd-496d8d24a32e",
  "exchange": "pptbitget",
  "tradeSymbol": "LUMIA/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}"
}
```

**Result:** SageMaster returned HTTP 200 (accepted) but did NOT close any trades. The trades remain open.

**SageMaster behavior:** SageMaster silently ignores unrecognized action types — it returns 200 OK but takes no action. This makes debugging very difficult.

---

## Bug #2: Entry Signals Missing TP/SL (FIXED in PR #105)

**Signal:** "Buy limit btc usdt 71k Sl 70k Tp 72k"
**Parser output:** Correctly extracted `entry_price=71000, stop_loss=70000, take_profits=[72000]`

**What we sent (before fix):**
```json
{
  "type": "start_deal",
  "price": "71000.0",
  "aiAssistId": "dcf5a01f-...",
  "exchange": "pptbitget",
  "eventSymbol": "BTC/USDT",
  "tradeSymbol": "BTC/USDT"
}
```
TP and SL were silently dropped because the webhook template didn't include those keys.

**What SageMaster expects:**
```json
{
  "type": "start_deal",
  "price": "71000.0",
  "aiAssistId": "dcf5a01f-...",
  "exchange": "pptbitget",
  "eventSymbol": "BTC/USDT",
  "tradeSymbol": "BTC/USDT",
  "take_profits": [72000.0],
  "stopLoss": 70000.0,
  "position_type": "long"
}
```

**Status:** FIXED in PR #105 (deployed 2026-03-21). Entry signals now inject TP/SL from the parsed signal even when the template lacks those keys.

**Evidence from SageMaster UI:** Active trades show "TP 7256" but "Stop Loss Condition: -" — confirming SL was not applied on earlier signals before the fix.

---

## Bug #3: modify_sl Sends Absolute Price as Relative Offset (FIXED in PR #105)

**Signal:** "Set SL to 70000"
**What we sent:**
```json
{
  "type": "moved_sl_adjustment",
  "sl_adjustment": 70000,
  "position_type": "long"
}
```

`sl_adjustment` is a **relative pip/percentage offset from entry**, not an absolute price. Sending 70000 as an offset is nonsensical.

**Status:** FIXED in PR #105. Now returns an error for absolute SL modification on crypto (unsupported by SageMaster's webhook API).

---

## Bug #4: modify_tp Not Supported by SageMaster (PLATFORM LIMITATION)

**Signal:** "Set TP to 72k"
**Result:** `Action 'modify_tp' is not supported by SageMaster`

SageMaster's webhook API has NO action type for modifying TP on an existing position. TP can only be set during the initial `start_deal` entry signal.

**Status:** Platform limitation — cannot be fixed without SageMaster adding a new action type. TP must be included in the entry signal.

---

## Additional Crypto Actions Not Yet Supported by Sage Radar AI

SageMaster Crypto supports these actions that Sage Radar AI does not yet handle:

| SageMaster Action | Type String | Sage Radar Status |
|-------------------|-------------|-------------------|
| Cancel single trade | `cancel_the_deal` | Not implemented |
| Cancel all + stop | *(type TBD)* | Not implemented |
| Cancel all active | *(type TBD)* | Not implemented |
| Start assist + trade | `start_ai_assist_and_deal` | Not implemented (we send `start_assist`) |

"Cancel" differs from "Close" — cancel keeps the bought currency (or released funds for short), while close sells at market price.

---

## Recommended Fix: Update CRYPTO_ACTION_TYPE Mapping

File: `src/core/models.py`

Current (INCORRECT):
```python
CRYPTO_ACTION_TYPE = {
    "start_deal": "start_deal",
    "close_position": "close_order_at_market_price",
    "partial_close_lot": "partially_closed_by_percentage",
    "partial_close_pct": "partially_closed_by_percentage",
    "breakeven": "moved_sl_adjustment",
    "extra_order": "open_extra_order",
}
```

Should be:
```python
CRYPTO_ACTION_TYPE = {
    "start_deal": "start_deal",
    "close_position": "close_order_at_market_price",
    "close_all": "close_all_deals_at_market_price",
    "close_all_stop": "close_all_deals_at_market_price_and_stop_ai_assist",
    "start_assist": "start_ai_assist_and_deal",
    "stop_assist": "stop_ai_assist",
    "partial_close_lot": "partially_closed_by_percentage",
    "partial_close_pct": "partially_closed_by_percentage",
    "breakeven": "moved_sl_adjustment",
    "extra_order": "open_extra_order",
}
```

**Effort:** Small (~15 min code change + tests)

---

## Questions for SageMaster Product Team

1. **Silent 200 OK on unrecognized actions:** Can SageMaster return a 4xx error when an unrecognized `type` string is sent? Currently it returns 200 OK but takes no action, making debugging extremely difficult.

2. **Modify TP/SL on existing trades:** Is there a webhook action to modify TP or SL on an existing open trade? If not, is this on the roadmap?

3. **Cancel action type strings:** What are the exact `type` strings for "Cancel all AI Assist trades and stop" and "Cancel all active trades"?

4. **Crypto SL as absolute price:** `moved_sl_adjustment` uses a relative offset. Is there a way to set SL to an absolute price (e.g. "set SL to $70,000") via webhook?

---

## Appendix: Full Signal Flow Evidence

### Signal: "Close all btc trades from this assist" (msg 179)
- **Timestamp:** 2026-03-21 21:40:54 UTC
- **Parser:** action=close_all, symbol=ALL, direction=long (CORRECT)
- **Mapper:** type=close_all_orders_at_market_price (WRONG — should be close_all_deals_at_market_price)
- **Dispatch:** HTTP 200 from SageMaster (accepted but NOT executed)
- **Result:** Trades remain open

### Signal: "Buy limit btc usdt 71k Sl 70k Tp 72k" (msg 177)
- **Timestamp:** 2026-03-21 21:05:17 UTC
- **Parser:** action=entry, symbol=BTC/USDT, entry=71000, sl=70000, tp=[72000] (CORRECT)
- **Mapper:** type=start_deal, price=71000.0 (CORRECT but SL/TP stripped — FIXED in PR #105)
- **Dispatch:** HTTP 200 from SageMaster (trade opened, no SL applied)
- **Result:** Trade shows TP 7256 but Stop Loss Condition: -
