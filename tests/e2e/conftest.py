"""Shared fixtures for E2E / post-deploy tests."""

from __future__ import annotations

import os

import pytest


def _require_env(key: str, default: str | None = None) -> str:
    """Return an env var or skip the test if not set and no default."""
    value = os.environ.get(key, default)
    if value is None:
        pytest.skip(f"{key} not set — skipping E2E test")
    return value


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


@pytest.fixture(scope="session")
def test_user_email() -> str:
    """Email of the persistent test account on staging."""
    return _require_env("TEST_USER_EMAIL")


@pytest.fixture(scope="session")
def test_user_password() -> str:
    """Password of the persistent test account on staging."""
    return _require_env("TEST_USER_PASSWORD")
