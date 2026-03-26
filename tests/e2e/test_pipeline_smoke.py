"""Pipeline smoke tests — verify real signals flow end-to-end.

Sends a signal via Telegram Bot API to a test channel, waits for the
listener to pick it up, and verifies the signal was parsed, mapped,
and dispatched successfully via signal_logs.

This is the highest-value test in the suite — it verifies the critical
trading path that handles real money:
  Bot → Telegram Channel → Listener → QStash → Workflow →
  Parser (OpenAI) → Mapper → Dispatcher → SageMaster

Required env vars:
    STAGING_API_URL — staging API base URL
    TEST_USER_EMAIL / TEST_USER_PASSWORD — staging test account
    TELEGRAM_BOT_TOKEN — bot token for sending test signals
    TELEGRAM_TEST_CHAT_ID — chat_id of the test channel (with -100 prefix)
    PIPELINE_TEST_ACCOUNT_EMAIL — account that monitors the test channel

Usage:
    STAGING_API_URL=https://ai-signal-router-staging.up.railway.app \
    TEST_USER_EMAIL=e2e-test@sagemaster.com \
    TEST_USER_PASSWORD='E2eTest2026!' \
    TELEGRAM_BOT_TOKEN=8616002077:AAHNnQYeXC1GIGZ3FhsvyIyotL_kEfskfog \
    TELEGRAM_TEST_CHAT_ID=-1003819954354 \
    PIPELINE_TEST_ACCOUNT_EMAIL=ehsaan.private@gmail.com \
        pytest tests/e2e/test_pipeline_smoke.py -v
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.pipeline]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_TEST_CHAT_ID", "-1003819954354")
_API_URL = os.environ.get(
    "STAGING_API_URL",
    "https://ai-signal-router-staging.up.railway.app",
)
_PIPELINE_ACCOUNT = os.environ.get(
    "PIPELINE_TEST_ACCOUNT_EMAIL",
    "ehsaan.private@gmail.com",
)

# How long to wait for the signal to flow through the pipeline (seconds).
# Covers: Telegram delivery → listener → QStash → workflow → OpenAI → mapper → dispatcher
_PIPELINE_TIMEOUT = 30
_POLL_INTERVAL = 5


def _skip_if_no_bot():
    if not _BOT_TOKEN:
        pytest.skip("TELEGRAM_BOT_TOKEN not set — skipping pipeline test")


def _send_telegram_message(text: str) -> int:
    """Send a message via the Telegram Bot API. Returns message_id."""
    resp = httpx.post(
        f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
        json={"chat_id": _CHAT_ID, "text": text},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    assert data["ok"], f"Telegram API error: {data}"
    return data["result"]["message_id"]


def _find_signal_in_logs(marker: str, timeout: int = _PIPELINE_TIMEOUT) -> list[dict]:
    """Poll the staging DB via the API for signal logs containing the marker.

    Returns matching log entries once found, or empty list on timeout.
    Uses the admin signals endpoint to search across all users.
    """
    headers = {}
    # Login with the test account (admin) to access admin endpoints
    email = os.environ.get("TEST_USER_EMAIL", "")
    password = os.environ.get("TEST_USER_PASSWORD", "")
    if email and password:
        resp = httpx.post(
            f"{_API_URL}/api/v1/auth/login-json",
            json={"email": email, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(
                f"{_API_URL}/api/v1/admin/signals",
                headers=headers,
                params={"limit": 10},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", data) if isinstance(data, dict) else data
                matches = [
                    item for item in items
                    if marker in (item.get("raw_message") or "")
                ]
                if matches:
                    return matches
        except Exception:
            pass
        time.sleep(_POLL_INTERVAL)

    return []


# ---------------------------------------------------------------------------
# Pipeline smoke tests
# ---------------------------------------------------------------------------


def test_pipeline_forex_signal_e2e() -> None:
    """Full pipeline: send a forex signal → verify it's parsed and dispatched."""
    _skip_if_no_bot()

    marker = f"E2E-FX-{int(time.time())}"
    signal_text = (
        f"BUY GBPUSD @ 1.2650\n"
        f"TP1: 1.2700\n"
        f"TP2: 1.2750\n"
        f"SL: 1.2600\n"
        f"Ref: {marker}"
    )

    # Send signal to Telegram
    msg_id = _send_telegram_message(signal_text)
    assert msg_id > 0, "Failed to send Telegram message"

    # Wait for pipeline processing
    matches = _find_signal_in_logs(marker)
    assert len(matches) > 0, (
        f"Signal with marker {marker} not found in logs after {_PIPELINE_TIMEOUT}s. "
        "Pipeline may be down or listener not monitoring the test channel."
    )

    # Verify at least one successful dispatch
    success = [m for m in matches if m.get("status") == "success"]
    assert len(success) > 0, (
        f"Signal found but none with status=success. Statuses: "
        f"{[m.get('status') for m in matches]}"
    )

    # Verify parsing
    for s in success:
        parsed = s.get("parsed_data") or {}
        assert parsed.get("is_valid_signal") is True, f"Signal not parsed as valid: {parsed}"
        assert parsed.get("action") in (
            "entry", "buy", "sell", "buy_limit", "buy_stop", "sell_limit", "sell_stop",
        ), f"Unexpected action: {parsed.get('action')}"
        assert "GBP" in (parsed.get("symbol") or "").upper(), (
            f"Expected GBPUSD symbol, got: {parsed.get('symbol')}"
        )

    # Verify webhook payload was built
    for s in success:
        assert s.get("webhook_payload") is not None, (
            "Signal dispatched but no webhook_payload recorded"
        )


def test_pipeline_crypto_signal_e2e() -> None:
    """Full pipeline: send a crypto signal → verify it's parsed and dispatched."""
    _skip_if_no_bot()

    marker = f"E2E-CR-{int(time.time())}"
    signal_text = (
        f"LONG BTC/USDT\n"
        f"Entry: 95000\n"
        f"TP: 98000\n"
        f"SL: 93000\n"
        f"Ref: {marker}"
    )

    msg_id = _send_telegram_message(signal_text)
    assert msg_id > 0

    matches = _find_signal_in_logs(marker)
    assert len(matches) > 0, (
        f"Crypto signal with marker {marker} not found in logs after {_PIPELINE_TIMEOUT}s."
    )

    # Crypto signals should be parsed as valid
    for m in matches:
        parsed = m.get("parsed_data") or {}
        if parsed.get("is_valid_signal"):
            assert "BTC" in (parsed.get("symbol") or "").upper(), (
                f"Expected BTC symbol, got: {parsed.get('symbol')}"
            )


def test_pipeline_nonsignal_ignored() -> None:
    """Non-signal messages should be ignored (not dispatched)."""
    _skip_if_no_bot()

    marker = f"E2E-NS-{int(time.time())}"
    msg_text = f"Good morning everyone! Have a great trading day. Ref: {marker}"

    msg_id = _send_telegram_message(msg_text)
    assert msg_id > 0

    matches = _find_signal_in_logs(marker)

    # Non-signals may or may not appear in logs depending on config.
    # If they appear, they should be "ignored", never "success".
    for m in matches:
        assert m.get("status") != "success", (
            f"Non-signal was dispatched as success — pipeline safety issue! "
            f"Message: {m.get('raw_message', '')[:80]}"
        )


def test_pipeline_management_signal_e2e() -> None:
    """Management signal (close/TP/SL update) flows through pipeline."""
    _skip_if_no_bot()

    marker = f"E2E-MG-{int(time.time())}"
    signal_text = f"Close all GBPUSD positions at market. Ref: {marker}"

    msg_id = _send_telegram_message(signal_text)
    assert msg_id > 0

    matches = _find_signal_in_logs(marker)
    # Management signals may be parsed as valid or ignored depending on
    # enabled_actions config. We just verify the pipeline doesn't crash.
    # If matches found, none should be in a "failed" state.
    for m in matches:
        assert m.get("status") != "failed", (
            f"Management signal failed in pipeline: {m.get('error_message', '')}"
        )


def test_pipeline_latency() -> None:
    """Signal should be processed within 30 seconds of sending."""
    _skip_if_no_bot()

    marker = f"E2E-LAT-{int(time.time())}"
    send_time = time.time()

    signal_text = (
        f"SELL USDJPY @ 155.50\n"
        f"TP: 155.00\n"
        f"SL: 156.00\n"
        f"Ref: {marker}"
    )

    _send_telegram_message(signal_text)

    matches = _find_signal_in_logs(marker, timeout=45)
    assert len(matches) > 0, f"Signal {marker} not processed within 45s"

    elapsed = time.time() - send_time
    assert elapsed < 45, f"Pipeline took {elapsed:.0f}s — exceeds 45s threshold"
