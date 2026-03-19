# SageMaster Webhook Integration Schemas

## 1. Overview

The core function of the Telegram Signal Copier is to translate unstructured Telegram messages into structured JSON payloads that the SageMaster API can process. SageMaster performs **order routing** based on these payloads.

The webhook URL format is:
`https://api.sagemaster.io/deals_idea/{strategy_uuid}` (Crypto)
`https://sfx.sagemaster.io/deals_idea/{strategy_uuid}` (Forex)

The `{strategy_uuid}` is unique to each user's strategy and is provided by the user during configuration.

**CRITICAL DIFFERENCE:** The Forex and Crypto platforms use different field names and action types. The mapper must construct the correct payload based on the user's selected platform.

## 2. Forex Webhook Schemas (SFX)

### 2.1 Forex Field Mapping
*   **ID Field:** `assistId` (NOT `assetId`)
*   **Symbol Field:** `symbol`
*   **Source:** `forex`
*   **Date:** `{{time}}`

### 2.2 Forex V1 vs V2

*   **V1 (Static Strategy / "Custom TradingView Alert"):** Uses fixed SL/TP and money management defined in the SageMaster strategy. The webhook only triggers the action.
*   **V2 (Dynamic Signal / "Custom TradingView Alert V2"):** The webhook payload overrides the strategy's SL/TP and money management settings.
*   **Note:** Both V1 and V2 support the same trade management actions (close, partial close, breakeven). The difference is only in the entry payload fields.
*   **CRITICAL:** The V1/V2 choice must match the **Trigger Condition** configured on the SageMaster Assist ("Custom TradingView Alert" for V1, "Custom TradingView Alert V2" for V2).

### 2.3 Forex V2 Field Requirements

**Money Management Mode Dependency:**
*   `balance`: Only used when Assist money management is set to "Indicator provider x percent w ratio check mode". Otherwise the strategy ignores it — leave default or omit.
*   `lots`: Only used when Assist money management is set to "Indicator provider x percent w ratio check mode" or "Indicator provider x percent w/o ratio check mode". Otherwise the strategy ignores it.

**TP/SL Options (need at least one from each pair):**
*   `takeProfits`: Array of price values, e.g., `[1.1050, 1.1100]`. Supports TradingView variables.
*   `takeProfitsPips`: Array of pip values, e.g., `[15, 30, 45]`. Multiple values enable laddered TP with partial closes when Assist SL/TP mode is set to "Set indicator TP laddered and SL".
*   `stopLoss`: Price value or TradingView variable.
*   `stopLossPips`: Pip value, e.g., `30`.
*   The webhook only needs **either** `takeProfits` OR `takeProfitsPips` (not both). Same for `stopLoss` OR `stopLossPips`.

**Price Field:**
*   `price`: Recommended to use `{{close}}`. Can be changed to `{{open}}`, `{{high}}`, or `{{low}}`.

**CRITICAL:** If a V2 entry payload is sent with empty TP/SL fields (e.g., `takeProfits: []`, `stopLoss: null`), SageMaster's Assist will reject it with "Invalid S/L or T/P". Empty optional fields must be **stripped** from the payload entirely.

### 2.4 Forex Entry Actions

**V1 Entry (Long/Short):**
```json
{
  "type": "start_long_market_deal",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD"
}
```
*(Use `start_short_market_deal` for short positions)*

**V2 Entry (Long/Short — Market):**
```json
{
  "type": "start_long_market_deal",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD",
  "price": "{{close}}",
  "balance": 1000,
  "lots": 1,
  "takeProfits": [ {{tpPrice}} ],
  "takeProfitsPips": [30],
  "stopLoss": {{slPrice}},
  "stopLossPips": 30
}
```

**V2 Entry (Long/Short — Limit):**
```json
{
  "type": "start_long_limit_deal",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD",
  "price": "{{close}}",
  "balance": 1000,
  "lots": 1,
  "takeProfits": [ {{tpPrice}} ],
  "takeProfitsPips": [30],
  "stopLoss": {{slPrice}},
  "stopLossPips": 30
}
```
*(Use `start_short_limit_deal` for short limit positions)*

### 2.5 Forex Trade Management Actions (V1 & V2)

**Close Position:**
```json
{
  "type": "close_order_at_market_price",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD"
}
```

**Close All Positions:**
```json
{
  "type": "close_all_orders_at_market_price",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}"
}
```

**Close All Positions & Stop Assist:**
```json
{
  "type": "close_all_orders_at_market_price_and_stop_assist",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}"
}
```

**Partial Close (by Lot):**
```json
{
  "type": "partially_close_by_lot",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD",
  "lotSize": 0.1
}
```

**Partial Close (by Percentage):**
```json
{
  "type": "partially_close_by_percentage",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD",
  "percentage": 10
}
```

**Move SL to Breakeven:**
Adjusts the SL to the entry price (breakeven) with optional pip adjustment. Negative values move SL before entry for buy / after entry for sell. 0 = move to exact entry price.
```json
{
  "type": "move_sl_to_breakeven",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD",
  "slAdjustment": 0
}
```

**Start Assist:**
```json
{
  "type": "start_assist",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}"
}
```

**Stop Assist:**
```json
{
  "type": "stop_assist",
  "assistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "source": "forex",
  "date": "{{time}}"
}
```

## 3. Crypto Webhook Schemas

### 3.1 Crypto Field Mapping
*   **ID Field:** `aiAssistId`
*   **Symbol Field:** `tradeSymbol`
*   **Exchange:** `exchange` (Required, e.g., "binance")
*   **Event Symbol:** `eventSymbol` (e.g., `{{ticker}}`)
*   **Date:** `{{time}}`

### 3.2 Crypto Entry Action
Crypto does not distinguish between long and short in the action type. It uses a single `start_deal` type.

```json
{
  "type": "start_deal",
  "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}"
}
```

### 3.3 Crypto Trade Management Actions

**Close Position:**
```json
{
  "type": "close_order_at_market_price",
  "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}"
}
```

**Partial Close (by Percentage ONLY):**
Note: Crypto does not support partial close by lot, only by percentage.
```json
{
  "type": "partially_closed_by_percentage",
  "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}",
  "position_type": "long",
  "percentage": 50
}
```

**Move SL to Breakeven:**
```json
{
  "type": "moved_sl_adjustment",
  "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}",
  "position_type": "long",
  "sl_adjustment": 0
}
```

**Add Funds / Extra Order:**
```json
{
  "type": "open_extra_order",
  "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}",
  "position_type": "long",
  "is_market": false,
  "order_price": 30000
}
```

**Start Deal with TP/SL (percentage-based):**
Note: Crypto TP/SL values are **percentages**, not prices (e.g., `[1,2,5]` = 1%, 2%, 5%).
```json
{
  "type": "start_deal",
  "aiAssistId": "eec79a52-1ab9-4d9b-a7ca-126a2f5e0307",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "position_type": "long",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}",
  "take_profits": [1, 2, 5],
  "stopLoss": 10
}
```

## 4. Error Handling

The SageMaster API will return standard HTTP status codes.

*   `200 OK`: The payload was successfully received and processed.
*   `400 Bad Request`: The JSON payload is malformed or missing required fields.
*   `401 Unauthorized`: The `{strategy_uuid}` in the URL is invalid or inactive.
*   `404 Not Found`: The specified ID or symbol could not be found.
*   `500 Internal Server Error`: An error occurred on the SageMaster platform.

**Known Assist-level errors (HTTP 200 but trade rejected):**
*   "Invalid S/L or T/P" — Empty TP/SL arrays or null values in V2 payload. Solution: strip empty optional fields.

The dispatcher must log all non-200 responses in the `signal_logs` table for troubleshooting.

## 5. Unsupported Actions

The following signal actions have **no SageMaster equivalent** and must be filtered by the pipeline:
*   `modify_tp` — SageMaster does not support modifying TP after trade is open
*   `modify_sl` — SageMaster does not support modifying SL after trade is open (only breakeven via `move_sl_to_breakeven`)
*   `add_to_position` — Not supported for Forex (Crypto uses `open_extra_order`)
