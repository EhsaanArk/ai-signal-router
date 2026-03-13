# Internal API Endpoints

## 1. Overview

This document defines the REST API endpoints used by the frontend dashboard to communicate with the backend. All endpoints require a valid JWT bearer token in the `Authorization` header, except for the initial user login/registration.

Base URL: `/api/v1`

## 2. Authentication (Dashboard)

### `POST /auth/login`
Authenticates a user into the dashboard.
*   **Request Body**: `{"email": "user@example.com", "password": "password123"}`
*   **Response (200)**: `{"access_token": "jwt_string", "token_type": "bearer"}`

## 3. Telegram Connection

### `POST /telegram/send-code`
Initiates the Telegram login flow by requesting a verification code.
*   **Request Body**: `{"phone_number": "+1234567890"}`
*   **Response (200)**: `{"phone_code_hash": "hash_string"}`

### `POST /telegram/verify-code`
Completes the Telegram login flow.
*   **Request Body**: `{"phone_number": "+1234567890", "phone_code_hash": "hash_string", "code": "12345", "password": "optional_2fa_password"}`
*   **Response (200)**: `{"status": "success", "message": "Telegram account connected"}`

### `GET /telegram/status`
Checks if the user has an active Telegram session.
*   **Response (200)**: `{"is_connected": true, "phone_number": "+1234567890"}`

## 4. Routing Rules (Multi-Destination)

### `GET /channels`
Retrieves a list of all Telegram channels the user is subscribed to (from the MTProto session).
*   **Response (200)**:
    ```json
    [
      {
        "channel_id": "-100123456789",
        "channel_name": "Forex VIP Signals"
      }
    ]
    ```

### `GET /routing-rules`
Retrieves all active routing rules for the user.
*   **Response (200)**:
    ```json
    [
      {
        "id": "uuid",
        "source_channel_id": "-100123456789",
        "source_channel_name": "Forex VIP Signals",
        "destination_webhook_url": "https://api.sagemaster.io/deals_idea/uuid1",
        "payload_version": "V2",
        "is_active": true
      }
    ]
    ```

### `POST /routing-rules`
Creates a new routing rule (maps 1 channel to 1 webhook destination).
*   **Request Body**:
    ```json
    {
      "source_channel_id": "-100123456789",
      "source_channel_name": "Forex VIP Signals",
      "destination_webhook_url": "https://api.sagemaster.io/deals_idea/uuid1",
      "payload_version": "V2",
      "symbol_mappings": {"GOLD": "XAUUSD"},
      "risk_overrides": {"lots": 0.5}
    }
    ```
*   **Response (201)**: `{"status": "success", "id": "uuid"}`
*   **Error (403)**: `{"error": "Tier limit reached. Upgrade to add more destinations."}`

## 5. Upstash Workflow (Internal)

These endpoints are called by Upstash QStash and must not be exposed to the frontend. They must validate the QStash signature header.

### `POST /api/workflow/process-signal`
The durable workflow endpoint triggered by QStash when a new signal arrives from the Telegram Listener.
*   **Authentication**: Validated via `Upstash-Signature` header (not JWT).
*   **Request Body** (from QStash):
    ```json
    {
      "user_id": "uuid",
      "channel_id": "-100123456789",
      "raw_message": "BUY EURUSD @ 1.1000 SL 1.0950 TP 1.1050",
      "message_id": 12345,
      "timestamp": "2026-03-12T10:00:00Z"
    }
    ```
*   **Workflow Steps**: Parse -> Map -> Dispatch -> Log
*   **Response (200)**: `{"workflowRunId": "wfr_xxxxxx"}`

## 6. Local Development (Mock Injector)

These endpoints are ONLY available when `LOCAL_MODE=true`.

### `POST /api/dev/inject-signal`
Bypasses the Telegram Listener and injects a raw text signal directly into the processing pipeline. Used for local testing without a real Telegram account.
*   **Request Body**:
    ```json
    {
      "text": "BUY GOLD @ 2000 SL 1990 TP 2020",
      "channel_id": "-100123456789"
    }
    ```
*   **Response (200)**: `{"status": "success", "message": "Signal injected into pipeline"}`

## 7. Logs

### `GET /logs`
Retrieves the recent signal processing logs for the user.
*   **Query Parameters**: `limit` (default 50), `offset` (default 0)
*   **Response (200)**:
    ```json
    [
      {
        "id": "uuid",
        "channel_name": "Forex VIP Signals",
        "raw_message": "BUY EURUSD @ 1.1000 SL 1.0950 TP 1.1050",
        "status": "success",
        "processed_at": "2026-03-12T10:00:00Z"
      }
    ]
    ```
