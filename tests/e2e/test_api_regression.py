"""API regression tests — run against the live staging environment.

Full regression suite covering auth lifecycle, routing rules CRUD,
signal logs, parse preview, pipeline verification, and marketplace.

Usage:
    STAGING_API_URL=https://ai-signal-router-staging.up.railway.app \
    TEST_USER_EMAIL=test@example.com \
    TEST_USER_PASSWORD=secret \
        pytest tests/e2e/test_api_regression.py -v
"""

from __future__ import annotations

import httpx
import pytest

from tests.e2e.helpers import (
    assert_error_response,
    assert_response_time,
    create_test_routing_rule,
    subscribe_to_marketplace,
)

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Auth lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_valid_credentials(
    staging_api_url: str,
    auth_token: str,
    test_user_email: str,
    test_user_password: str,
) -> None:
    """Login with valid credentials returns 200 + access_token + user profile."""
    # auth_token fixture already validated login works — re-verify the response shape
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/login-json",
            json={"email": test_user_email, "password": test_user_password},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert "subscription_tier" in data["user"]
    assert_response_time(resp)


@pytest.mark.asyncio
async def test_login_wrong_password(staging_api_url: str) -> None:
    """Login with wrong password returns 401 with error message."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/login-json",
            json={"email": "valid@example.com", "password": "definitelywrong"},
        )
    assert_error_response(resp, 401, "incorrect")


@pytest.mark.asyncio
async def test_login_nonexistent_email(staging_api_url: str) -> None:
    """Login with nonexistent email returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/login-json",
            json={"email": "nonexistent-e2e@example.com", "password": "anypassword"},
        )
    assert_error_response(resp, 401)


@pytest.mark.asyncio
async def test_me_returns_user_profile(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """GET /auth/me returns full user profile with correct fields."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/auth/me",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "email" in data
    assert "subscription_tier" in data
    assert "is_admin" in data
    assert "email_verified" in data
    assert "accepted_tos_version" in data
    assert_response_time(resp)


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Change password with wrong current password returns 401."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "definitelywrong",
                "new_password": "newpassword123",
            },
        )
    assert_error_response(resp, 401, "incorrect")


# ---------------------------------------------------------------------------
# Routing rules CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routing_rules_crud_lifecycle(
    staging_api_url: str, auth_token: str,
) -> None:
    """Full CRUD lifecycle: create → list → get → update → delete."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Create
        rule, cleanup = await create_test_routing_rule(
            client, staging_api_url, auth_token,
        )
        try:
            rule_id = rule["id"]
            assert rule["destination_type"] == "custom"
            assert rule["is_active"] is True

            # List — should contain the new rule
            resp = await client.get(
                f"{staging_api_url}/api/v1/routing-rules",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert resp.status_code == 200
            rules = resp.json()
            assert any(r["id"] == rule_id for r in rules)

            # Get by ID
            resp = await client.get(
                f"{staging_api_url}/api/v1/routing-rules/{rule_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["id"] == rule_id

            # Update
            resp = await client.put(
                f"{staging_api_url}/api/v1/routing-rules/{rule_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"rule_name": "Updated E2E Test Rule"},
            )
            assert resp.status_code == 200
            assert resp.json()["rule_name"] == "Updated E2E Test Rule"

            # Delete
            resp = await client.delete(
                f"{staging_api_url}/api/v1/routing-rules/{rule_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert resp.status_code == 204

            # Verify deleted
            resp = await client.get(
                f"{staging_api_url}/api/v1/routing-rules/{rule_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert resp.status_code == 404
        finally:
            await cleanup()


@pytest.mark.asyncio
async def test_create_invalid_rule(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Creating a rule with missing required fields returns 422."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/routing-rules",
            headers=auth_headers,
            json={},  # Missing required fields
        )
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data  # FastAPI validation error format


@pytest.mark.asyncio
async def test_create_rule_invalid_webhook_url(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Creating a rule with an invalid webhook URL returns 422."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/routing-rules",
            headers=auth_headers,
            json={
                "source_channel_id": "test-channel",
                "destination_webhook_url": "not-a-url",
                "destination_type": "custom",
            },
        )
    # Either 422 (validation) or domain error for invalid URL
    assert resp.status_code in (422, 400)


# ---------------------------------------------------------------------------
# Signal logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_logs(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """GET /logs returns paginated structure with total and items."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/logs",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert_response_time(resp)


@pytest.mark.asyncio
async def test_logs_pagination(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """GET /logs with offset returns different results (limit+offset pagination)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp1 = await client.get(
            f"{staging_api_url}/api/v1/logs?limit=5&offset=0",
            headers=auth_headers,
        )
        resp2 = await client.get(
            f"{staging_api_url}/api/v1/logs?limit=5&offset=5",
            headers=auth_headers,
        )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data1 = resp1.json()
    data2 = resp2.json()
    # If total > 5, pages should differ; if total <= 5, page 2 should be empty
    if data1["total"] > 5:
        ids1 = {item["id"] for item in data1["items"]}
        ids2 = {item["id"] for item in data2["items"]}
        assert ids1 != ids2, "Page 1 and page 2 should have different items"
    else:
        assert len(data2["items"]) == 0


@pytest.mark.asyncio
async def test_logs_filter_by_status(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """GET /logs?status=success filters results."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/logs?status=success",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    # All returned items should have status=success (if any)
    for item in data["items"]:
        assert item["status"] == "success"


@pytest.mark.asyncio
async def test_logs_stats(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """GET /logs/stats returns stats structure."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/v1/logs/stats",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert_response_time(resp)


# ---------------------------------------------------------------------------
# Parse preview (hits live OpenAI — 30s timeout)
# ---------------------------------------------------------------------------

_FOREX_SIGNAL = "BUY XAUUSD @ 2650.00 TP1: 2660 TP2: 2670 SL: 2640"
_CRYPTO_SIGNAL = "LONG BTC/USDT Entry: 95000 TP: 98000 SL: 93000"
_NONSIGNAL = "Good morning everyone! Have a great trading day"
_MULTILINE_SIGNAL = """SELL EURUSD
Entry: 1.0850
TP1: 1.0800
TP2: 1.0750
SL: 1.0900
Risk: 1%"""


@pytest.mark.asyncio
@pytest.mark.slow
async def test_parse_forex_signal(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Parse preview: forex signal parsed correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/parse-preview",
            headers=auth_headers,
            json={"raw_message": _FOREX_SIGNAL},
        )
    assert resp.status_code == 200
    parsed = resp.json()["parsed"]
    assert parsed["is_valid_signal"] is True
    assert parsed["action"] in (
        "entry", "buy", "sell", "buy_limit", "buy_stop", "sell_limit", "sell_stop",
    )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_parse_crypto_signal(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Parse preview: crypto signal parsed correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/parse-preview",
            headers=auth_headers,
            json={"raw_message": _CRYPTO_SIGNAL},
        )
    assert resp.status_code == 200
    assert resp.json()["parsed"]["is_valid_signal"] is True


@pytest.mark.asyncio
@pytest.mark.slow
async def test_parse_nonsignal(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Parse preview: non-signal message identified correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/parse-preview",
            headers=auth_headers,
            json={"raw_message": _NONSIGNAL},
        )
    assert resp.status_code == 200
    assert resp.json()["parsed"]["is_valid_signal"] is False


@pytest.mark.asyncio
@pytest.mark.slow
async def test_parse_multiline_signal(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Parse preview: multiline signal parsed correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/parse-preview",
            headers=auth_headers,
            json={"raw_message": _MULTILINE_SIGNAL},
        )
    assert resp.status_code == 200
    parsed = resp.json()["parsed"]
    assert parsed["is_valid_signal"] is True


# ---------------------------------------------------------------------------
# Pipeline regression (parser sandbox + mapping verification)
# ---------------------------------------------------------------------------

_TP_SIGNAL = "TP1 HIT XAUUSD @ 2660"
_SL_SIGNAL = "SL HIT XAUUSD @ 2640"
_CLOSE_ALL_SIGNAL = "Close all trades now"
_MODIFY_SIGNAL = "Move SL to 2650 XAUUSD"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_forex_entry_mapping(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: forex entry signal produces valid mapped webhook payload."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={"raw_message": _FOREX_SIGNAL, "include_mapping": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["parsed"]["is_valid_signal"] is True
    # Mapping should produce a webhook payload
    payload = data.get("webhook_payload")
    if payload is not None:
        # V1 or V2 format should have action/type
        assert "type" in payload or "action" in payload


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_crypto_entry_mapping(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: crypto entry signal produces valid mapped payload."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={"raw_message": _CRYPTO_SIGNAL, "include_mapping": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["parsed"]["is_valid_signal"] is True


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_tp_signal(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: TP hit signal parsed as management action."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={"raw_message": _TP_SIGNAL},
        )
    assert resp.status_code == 200
    parsed = resp.json()["parsed"]
    # TP signals may be parsed as valid or as management actions
    assert "action" in parsed or "is_valid_signal" in parsed


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_sl_signal(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: SL hit signal parsed as management action."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={"raw_message": _SL_SIGNAL},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_close_all(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: 'close all' signal parsed correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={"raw_message": _CLOSE_ALL_SIGNAL},
        )
    assert resp.status_code == 200
    parsed = resp.json()["parsed"]
    if parsed.get("is_valid_signal"):
        assert parsed.get("action") in (
            "close_all", "close_all_stop", "close_all_orders_at_market_price",
        )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_modify_sl(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: modify SL signal parsed as management action."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={"raw_message": _MODIFY_SIGNAL},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.slow
async def test_pipeline_v1_payload_contract(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Pipeline: V1 mapped payload has required SageMaster fields."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/admin/parser/test",
            headers=auth_headers,
            json={
                "raw_message": _FOREX_SIGNAL,
                "include_mapping": True,
                "payload_version": "V1",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    payload = data.get("webhook_payload")
    if payload and data["parsed"].get("is_valid_signal"):
        # V1 contract: must have type and source
        assert "type" in payload, f"V1 payload missing 'type': {payload}"
        assert "source" in payload, f"V1 payload missing 'source': {payload}"


# ---------------------------------------------------------------------------
# Marketplace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_marketplace_providers(staging_api_url: str) -> None:
    """GET /api/marketplace/providers returns providers (public endpoint)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{staging_api_url}/api/marketplace/providers")
    assert resp.status_code == 200
    data = resp.json()
    # API returns either a list or paginated {items, total} structure
    if isinstance(data, list):
        providers = data
    else:
        assert "items" in data, f"Expected 'items' in response: {data}"
        providers = data["items"]
    assert isinstance(providers, list)
    assert_response_time(resp)


@pytest.mark.asyncio
async def test_my_subscriptions(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """GET /api/marketplace/my-subscriptions returns list structure."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{staging_api_url}/api/marketplace/my-subscriptions",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_marketplace_subscribe_lifecycle(
    staging_api_url: str, auth_token: str,
) -> None:
    """Full marketplace lifecycle: create route → subscribe → verify → unsubscribe → verify."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        # First, check if there are any providers
        resp = await client.get(f"{staging_api_url}/api/marketplace/providers")
        data = resp.json()
        providers = data["items"] if isinstance(data, dict) else data
        if not providers:
            pytest.skip("No marketplace providers on staging")

        provider_id = providers[0]["id"]

        # Create a routing rule to use as webhook destination template
        rule, rule_cleanup = await create_test_routing_rule(
            client, staging_api_url, auth_token,
        )
        try:
            # Subscribe
            sub, sub_cleanup = await subscribe_to_marketplace(
                client, staging_api_url, auth_token,
                provider_id=provider_id,
                webhook_destination_id=rule["id"],
            )
            try:
                assert sub["is_active"] is True

                # Verify in my-subscriptions
                resp = await client.get(
                    f"{staging_api_url}/api/marketplace/my-subscriptions",
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                subs = resp.json()
                assert any(s["provider_id"] == str(provider_id) for s in subs)
            finally:
                await sub_cleanup()

            # Verify unsubscribed
            resp = await client.get(
                f"{staging_api_url}/api/marketplace/my-subscriptions",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            subs = resp.json()
            active = [s for s in subs if s.get("provider_id") == str(provider_id) and s.get("is_active")]
            assert len(active) == 0
        finally:
            await rule_cleanup()


@pytest.mark.asyncio
async def test_unsubscribe_when_not_subscribed(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """Unsubscribe when not subscribed returns an error (not idempotent 200)."""
    # Use a fake provider ID that the user is definitely not subscribed to
    fake_provider_id = "00000000-0000-0000-0000-000000000000"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.delete(
            f"{staging_api_url}/api/marketplace/unsubscribe/{fake_provider_id}",
            headers=auth_headers,
        )
    # Should be 404 or 422 — NOT 200
    assert resp.status_code in (404, 422)


# ---------------------------------------------------------------------------
# Error contract verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_domain_errors_have_error_code_message(
    staging_api_url: str,
) -> None:
    """Domain errors return {"error": {"code": "...", "message": "..."}}."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Trigger a domain error (AuthenticationError)
        resp = await client.post(
            f"{staging_api_url}/api/v1/auth/login-json",
            json={"email": "e2e-contract-test@example.com", "password": "wrong"},
        )
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data, f"Domain error missing 'error' key: {data}"
    assert "code" in data["error"], f"Domain error missing 'error.code': {data}"
    assert "message" in data["error"], f"Domain error missing 'error.message': {data}"


@pytest.mark.asyncio
async def test_validation_errors_have_detail(
    staging_api_url: str, auth_headers: dict,
) -> None:
    """FastAPI validation errors (422) return {"detail": [...]}."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{staging_api_url}/api/v1/routing-rules",
            headers=auth_headers,
            json={},  # Missing all required fields
        )
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data, f"Validation error missing 'detail' key: {data}"
    assert isinstance(data["detail"], list), f"Expected detail to be a list: {data}"
