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
*   **V1 (Static Strategy):** Uses fixed SL/TP and money management defined in the SageMaster strategy. The webhook only triggers the action.
*   **V2 (Dynamic Signal):** The webhook payload overrides the strategy's SL/TP and money management settings.
*   **Note:** Both V1 and V2 support the same trade management actions (close, partial close, breakeven). The difference is only in the entry payload fields.

### 2.3 Forex Entry Actions
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

**V2 Entry (Long/Short):**
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
  "stopLoss": {{slPrice}}
}
```

### 2.4 Forex Trade Management Actions (V1 & V2)

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
  "percentage": 50
}
```

**Move SL to Breakeven:**
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

The dispatcher must log all non-200 responses in the `signal_logs` table for troubleshooting.
