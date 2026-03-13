# SageMaster Webhook Integration Schemas

## 1. Overview

The core function of the Telegram Signal Copier is to translate unstructured Telegram messages into structured JSON payloads that the SageMaster API can process. SageMaster performs **order routing** based on these payloads.

The webhook URL format is:
`https://api.sagemaster.io/deals_idea/{strategy_uuid}`

The `{strategy_uuid}` is unique to each user's strategy and is provided by the user during configuration.

## 2. V1 Payload (Static Strategy)

Use the V1 payload when the user wants their SageMaster strategy to manage the Stop Loss (SL) and Take Profit (TP) values. The Telegram signal merely acts as a trigger to open the trade.

### 2.1 Example: Start Long Market Deal

```json
{
  "type": "start_long_market_deal",
  "assetId": "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307",
  "source": "forex",
  "symbol": "EURUSD",
  "date": "{{time}}"
}
```

### 2.2 Example: Start Short Market Deal

```json
{
  "type": "start_short_market_deal",
  "assetId": "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307",
  "source": "forex",
  "symbol": "GBPUSD",
  "date": "{{time}}"
}
```

### 2.3 Field Descriptions (V1)

*   `type` (string, required): The action to perform. Must be `start_long_market_deal` or `start_short_market_deal`.
*   `assetId` (string, required): The unique identifier for the asset, provided by the user's SageMaster configuration.
*   `source` (string, required): The asset class. Typically `forex` or `crypto`.
*   `symbol` (string, required): The trading symbol (e.g., `EURUSD`). Must match the broker's symbol exactly.
*   `date` (string, required): The timestamp of the signal. Can use the TradingView `{{time}}` variable or an ISO 8601 timestamp.

## 3. V2 Payload (Dynamic Signal)

Use the V2 payload when the Telegram signal provides specific SL/TP levels that should override the default strategy settings.

### 3.1 Example: Start Long Market Deal with SL/TP

```json
{
  "type": "start_long_market_deal",
  "assetId": "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307",
  "source": "forex",
  "symbol": "EURUSD",
  "price": "1.1000",
  "takeProfits": [
    1.1050,
    1.1100
  ],
  "stopLoss": 1.0950
}
```

### 3.2 Example: Partially Close Position (V2 Provider Command)

```json
{
  "type": "partially_close_by_lot",
  "assetId": "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307",
  "lots": "0.5"
}
```

### 3.3 Example: Move to Breakeven (V2 Provider Command)

```json
{
  "type": "breakeven",
  "assetId": "eec79d52-1ab9-4d3b-a7ca-125b2f5e0307"
}
```

### 3.4 Field Descriptions (V2)

*   `type` (string, required): The action to perform.
*   `assetId` (string, required): The unique identifier for the asset.
*   `source` (string, required): The asset class.
*   `symbol` (string, required): The trading symbol.
*   `price` (string, optional): The entry price specified in the signal.
*   `takeProfits` (array of numbers, optional): An array of Take Profit price levels.
*   `stopLoss` (number, optional): The Stop Loss price level.
*   `lots` (string/number, optional): The position size to close (for partial close actions).

## 4. Error Handling

The SageMaster API will return standard HTTP status codes.

*   `200 OK`: The payload was successfully received and processed.
*   `400 Bad Request`: The JSON payload is malformed or missing required fields.
*   `401 Unauthorized`: The `{strategy_uuid}` in the URL is invalid or inactive.
*   `404 Not Found`: The specified `assetId` or `symbol` could not be found.
*   `500 Internal Server Error`: An error occurred on the SageMaster platform.

The dispatcher must log all non-200 responses in the `signal_logs` table for troubleshooting.
