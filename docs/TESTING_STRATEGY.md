# Testing Strategy & Verification Criteria

## 1. Overview

This document defines the testing strategy for the SageMaster Telegram Signal Copier. Because this project relies heavily on AI parsing, deterministic testing of the LLM output is critical. All code must be verified against the criteria defined here before being considered complete.

## 2. Test Framework

-   **Framework**: `pytest`
-   **Async Support**: `pytest-asyncio`
-   **Mocking**: `unittest.mock` and `pytest-mock`
-   **HTTP Mocking**: `responses` or `httpx_mock` (for mocking SageMaster webhook endpoints)

## 3. Module Verification Criteria

### 3.1 AI Parsing Engine (`src/parser/`)

The AI Parsing Engine is the most critical component. It must be tested deterministically using the provided fixtures.

*   **Fixture Location**: `tests/fixtures/raw_signals.txt` (input) and `tests/fixtures/expected_payloads.json` (expected output).
*   **Success Criteria**:
    1.  The parser must process every signal in `raw_signals.txt`.
    2.  The output for each signal must exactly match the corresponding JSON object in `expected_payloads.json`.
    3.  The parser must correctly identify non-signal messages (e.g., "Good morning traders!") and return a status of `ignored`.
    4.  The parser must handle missing optional fields (e.g., a signal with no Take Profit) without throwing an exception.

### 3.2 Webhook Dispatcher (`src/adapters/webhook/`)

The dispatcher must correctly format payloads and handle HTTP responses for multiple destinations.

*   **Success Criteria**:
    1.  Given a `ParsedSignal` object and a V1 configuration, it must generate a valid V1 JSON payload.
    2.  Given a `ParsedSignal` object and a V2 configuration, it must generate a valid V2 JSON payload.
    3.  It must correctly apply destination-specific symbol mappings (e.g., converting "GOLD" to "XAUUSD" for Destination A, and "GOLD" to "XAUUSD.pro" for Destination B).
    4.  It must correctly apply destination-specific risk overrides (e.g., overriding the signal's lot size).
    5.  It must handle HTTP 200 responses by logging a `success` status per destination.
    6.  It must handle HTTP 4xx and 5xx responses by logging a `failed` status per destination and capturing the error message.
    7.  It must rely on Upstash Workflow's built-in retry mechanism for HTTP 5xx errors (no custom retry loop needed in the code).

### 3.3 Telegram Authentication (`src/telegram/auth.py`)

Authentication must be tested using mock Telethon clients to avoid triggering real Telegram API rate limits during CI/CD.

*   **Success Criteria**:
    1.  The `send_code_request` function must successfully call the Telethon API and return a phone code hash.
    2.  The `sign_in` function must successfully authenticate and return an encrypted session string.
    3.  The `sign_in` function must correctly handle `SessionPasswordNeededError` (2FA required) and prompt for a password.

## 4. Local Pipeline Testing (Mock Injector)

Before deploying, the entire pipeline must be tested locally using the Mock Injector.

*   **Requirement**: When `LOCAL_MODE=true`, sending a POST request to `/api/dev/inject-signal` with a raw signal must result in a successful parse, map, and dispatch (verified via local logs), without requiring a real Telegram message or Upstash QStash.

## 5. Load Testing

The system must be capable of handling bursts of signals.

*   **Requirement**: The Webhook Dispatcher must be able to process and dispatch 100 concurrent signals within 5 seconds.
*   **Tool**: `locust` or `k6` (to be implemented in a later phase).

## 6. Agentic Workflow Instructions

When implementing a module, the AI agent must:
1.  Read the relevant section of this document.
2.  Write the tests *before* or *alongside* the implementation code.
3.  Run `pytest -v tests/test_<module>.py`.
4.  Do not consider the task complete until all tests pass.
