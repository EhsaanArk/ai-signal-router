"""Shared fixtures for E2E / post-deploy tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest


def _require_env(key: str, default: str | None = None) -> str:
    """Return an env var or skip the test if not set and no default."""
    value = os.environ.get(key, default)
    if value is None:
        pytest.skip(f"{key} not set — skipping E2E test")
    return value


# ---------------------------------------------------------------------------
# URL fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def staging_api_url() -> str:
    """Base URL for the staging API (no trailing slash)."""
    return _require_env(
        "STAGING_API_URL",
        "https://ai-signal-router-staging.up.railway.app",
    )


@pytest.fixture(scope="session")
def staging_frontend_url() -> str:
    """Base URL for the staging frontend (no trailing slash)."""
    return _require_env(
        "STAGING_FRONTEND_URL",
        "https://profound-communication-staging.up.railway.app",
    )


# ---------------------------------------------------------------------------
# Credential fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_user_email() -> str:
    """Email of the persistent test account on staging."""
    return _require_env("TEST_USER_EMAIL")


@pytest.fixture(scope="session")
def test_user_password() -> str:
    """Password of the persistent test account on staging."""
    return _require_env("TEST_USER_PASSWORD")


# ---------------------------------------------------------------------------
# Session-scoped auth token (avoids 5/min login rate limit)
# ---------------------------------------------------------------------------

_cached_token: str | None = None


@pytest.fixture(scope="session")
def auth_token(
    staging_api_url: str,
    test_user_email: str,
    test_user_password: str,
) -> str:
    """Login once per session and return a JWT. Shared across all tests."""
    global _cached_token
    if _cached_token:
        return _cached_token
    resp = httpx.post(
        f"{staging_api_url}/api/v1/auth/login-json",
        json={"email": test_user_email, "password": test_user_password},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Cannot login test user: {resp.status_code} {resp.text}")
    _cached_token = resp.json()["access_token"]
    return _cached_token


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> dict[str, str]:
    """Authorization headers for authenticated API requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Screenshot-on-failure hook (Playwright tests)
# ---------------------------------------------------------------------------


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when a Playwright test fails."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")
        if page:
            screenshot_dir = Path("test-screenshots")
            screenshot_dir.mkdir(exist_ok=True)
            try:
                page.screenshot(
                    path=str(screenshot_dir / f"{item.name}.png"),
                    full_page=True,
                )
            except Exception:
                pass  # Page may already be closed
