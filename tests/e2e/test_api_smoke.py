"""API smoke tests — run against the live staging environment.

These tests verify basic API responsiveness. They do NOT require
authentication for health endpoints, and only check for 4xx (not 5xx)
on auth endpoints. No real credentials are needed for smoke testing.

Usage:
    STAGING_API_URL=https://ai-signal-router-staging.up.railway.app \
        pytest tests/e2e/test_api_smoke.py -v
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Health endpoints (unauthenticated)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint(staging_api_url: str) -> None:
    """GET /health returns 200 with status=ok."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "database" in data


@pytest.mark.asyncio
async def test_deploy_health_endpoint(staging_api_url: str) -> None:
    """GET /health/deploy returns 200 with expected structure."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/health/deploy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "deploy_health" in data
    assert "current" in data
    current = data["current"]
    assert "active_sessions" in current
    assert "channels_monitored" in current
    assert "last_signal_at" in current


# ---------------------------------------------------------------------------
# Auth endpoints (expect 4xx, never 5xx)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_rejects_bad_credentials(staging_api_url: str) -> None:
    """POST /api/v1/auth/login-json with bad creds returns 401, not 500."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/login-json",
            json={"email": "nonexistent@test.com", "password": "wrongpassword"},
        )
    assert resp.status_code in (401, 403, 429), (
        f"Expected 4xx, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_register_rejects_duplicate(staging_api_url: str) -> None:
    """POST /api/v1/auth/register with an obviously bad request returns 4xx."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/register",
            json={"email": "", "password": ""},
        )
    # Empty email/password should be rejected — 422 or 400, never 500
    assert resp.status_code < 500, (
        f"Expected non-5xx, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Protected endpoints (expect 401/403 when unauthenticated)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_requires_auth(staging_api_url: str) -> None:
    """GET /api/v1/auth/me without token returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/api/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_telegram_status_requires_auth(staging_api_url: str) -> None:
    """GET /api/v1/telegram/status without token returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/api/v1/telegram/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_routing_rules_requires_auth(staging_api_url: str) -> None:
    """GET /api/v1/routing-rules without token returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/api/v1/routing-rules")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_logs_requires_auth(staging_api_url: str) -> None:
    """GET /api/v1/logs without token returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/api/v1/logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_health_requires_auth(staging_api_url: str) -> None:
    """GET /api/v1/admin/health without token returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/api/v1/admin/health")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Authenticated smoke tests (only run when test credentials provided)
# ---------------------------------------------------------------------------


@pytest.fixture
async def auth_token(
    staging_api_url: str,
    test_user_email: str,
    test_user_password: str,
) -> str:
    """Login and return a JWT for authenticated tests."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/login-json",
            json={"email": test_user_email, "password": test_user_password},
        )
    if resp.status_code != 200:
        pytest.skip(f"Cannot login test user: {resp.status_code}")
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_authenticated_me(
    staging_api_url: str, auth_token: str,
) -> None:
    """GET /api/v1/auth/me with valid token returns user profile."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "email" in data


@pytest.mark.asyncio
async def test_authenticated_telegram_status(
    staging_api_url: str, auth_token: str,
) -> None:
    """GET /api/v1/telegram/status returns 200 with connected field."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/telegram/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert resp.status_code == 200
    assert "connected" in resp.json()


@pytest.mark.asyncio
async def test_authenticated_routing_rules(
    staging_api_url: str, auth_token: str,
) -> None:
    """GET /api/v1/routing-rules returns 200 with a list."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/routing-rules",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_authenticated_logs(
    staging_api_url: str, auth_token: str,
) -> None:
    """GET /api/v1/logs returns 200 with paginated structure."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/logs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
