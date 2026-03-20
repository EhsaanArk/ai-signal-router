"""E2E Playwright tests — verify key UI flows on staging.

These tests launch a headless Chromium browser and navigate through
the Sage Radar AI frontend to verify pages load without errors.

Usage:
    STAGING_FRONTEND_URL=https://profound-communication-staging.up.railway.app \
    TEST_USER_EMAIL=test@example.com \
    TEST_USER_PASSWORD=secret \
        pytest tests/e2e/test_ui_flows.py -v

Requires: pip install -r requirements-e2e.txt && playwright install chromium
"""

from __future__ import annotations

import os
import re

import pytest

# Skip entire module if playwright is not installed
pytest.importorskip("playwright")

from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.playwright]

_FRONTEND_URL = os.environ.get(
    "STAGING_FRONTEND_URL",
    "https://profound-communication-staging.up.railway.app",
)
_TEST_EMAIL = os.environ.get("TEST_USER_EMAIL", "")
_TEST_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "")


# ---------------------------------------------------------------------------
# Unauthenticated pages
# ---------------------------------------------------------------------------


def test_login_page_loads(page: Page) -> None:
    """Login page renders without errors."""
    page.goto(f"{_FRONTEND_URL}/login", wait_until="networkidle")
    # Should have some form of login UI
    expect(page.locator("body")).to_contain_text(
        re.compile(r"sign\s*in|log\s*in|email", re.IGNORECASE),
    )


def test_register_page_loads(page: Page) -> None:
    """Register page renders without errors."""
    page.goto(f"{_FRONTEND_URL}/register", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text(
        re.compile(r"sign\s*up|register|create.*account", re.IGNORECASE),
    )


def test_forgot_password_page_loads(page: Page) -> None:
    """Forgot password page renders without errors."""
    page.goto(f"{_FRONTEND_URL}/forgot-password", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text(
        re.compile(r"reset|forgot|password", re.IGNORECASE),
    )


# ---------------------------------------------------------------------------
# Authenticated pages — require TEST_USER_EMAIL + TEST_USER_PASSWORD
# ---------------------------------------------------------------------------


def _skip_if_no_credentials() -> None:
    if not _TEST_EMAIL or not _TEST_PASSWORD:
        pytest.skip("TEST_USER_EMAIL / TEST_USER_PASSWORD not set")


def _login(page: Page) -> None:
    """Perform login via the frontend UI."""
    page.goto(f"{_FRONTEND_URL}/login", wait_until="networkidle")

    # Fill email field
    email_input = page.locator('input[type="email"], input[name="email"]').first
    email_input.fill(_TEST_EMAIL)

    # Fill password field
    password_input = page.locator('input[type="password"]').first
    password_input.fill(_TEST_PASSWORD)

    # Click submit
    submit_btn = page.locator('button[type="submit"]').first
    submit_btn.click()

    # Wait for navigation away from login page
    page.wait_for_url(re.compile(r"(?!.*login)"), timeout=15_000)


def test_dashboard_loads(page: Page) -> None:
    """Dashboard loads after login."""
    _skip_if_no_credentials()
    _login(page)
    # Dashboard should be at / or /dashboard
    page.goto(f"{_FRONTEND_URL}/", wait_until="networkidle")
    # Should not show a login form anymore
    assert "login" not in page.url.lower() or page.locator("nav").count() > 0


def test_telegram_page_loads(page: Page) -> None:
    """Telegram connection page loads."""
    _skip_if_no_credentials()
    _login(page)
    page.goto(f"{_FRONTEND_URL}/telegram", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text(
        re.compile(r"telegram|connect|phone", re.IGNORECASE),
    )


def test_routing_rules_page_loads(page: Page) -> None:
    """Routing rules page loads."""
    _skip_if_no_credentials()
    _login(page)
    page.goto(f"{_FRONTEND_URL}/routing-rules", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text(
        re.compile(r"rout|rule|destination|channel", re.IGNORECASE),
    )


def test_signal_logs_page_loads(page: Page) -> None:
    """Signal logs page loads."""
    _skip_if_no_credentials()
    _login(page)
    page.goto(f"{_FRONTEND_URL}/logs", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text(
        re.compile(r"log|signal|history", re.IGNORECASE),
    )


def test_settings_page_loads(page: Page) -> None:
    """Settings page loads."""
    _skip_if_no_credentials()
    _login(page)
    page.goto(f"{_FRONTEND_URL}/settings", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text(
        re.compile(r"setting|notification|account|preference", re.IGNORECASE),
    )


# ---------------------------------------------------------------------------
# Console error check
# ---------------------------------------------------------------------------


def test_no_console_errors_on_login(page: Page) -> None:
    """Login page should not produce JavaScript console errors."""
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto(f"{_FRONTEND_URL}/login", wait_until="networkidle")
    # Filter out known benign errors (e.g., favicon 404)
    real_errors = [e for e in errors if "favicon" not in e.lower()]
    assert len(real_errors) == 0, f"Console errors: {real_errors}"
