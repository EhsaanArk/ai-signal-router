"""Shared helpers for E2E regression tests.

Factory functions for test data creation/cleanup and assertion helpers
for verifying API error contracts and response times.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Awaitable, Callable

import httpx


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


async def create_test_routing_rule(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    **overrides: Any,
) -> tuple[dict, Callable[[], Awaitable[None]]]:
    """Create a routing rule on staging, return (rule_data, async_cleanup_fn).

    Uses a unique webhook URL to avoid cross-account conflicts.
    The destination_type is set to 'custom' to skip SageMaster template validation.
    """
    unique_id = uuid.uuid4().hex[:8]
    defaults = {
        "source_channel_id": f"test-channel-{unique_id}",
        "source_channel_name": f"E2E Test Channel {unique_id}",
        "destination_webhook_url": f"https://httpbin.org/post?test={unique_id}",
        "payload_version": "V1",
        "destination_type": "custom",
        "rule_name": f"E2E Test Rule {unique_id}",
    }
    defaults.update(overrides)

    resp = await client.post(
        f"{base_url}/api/v1/routing-rules",
        headers={"Authorization": f"Bearer {token}"},
        json=defaults,
    )
    resp.raise_for_status()
    rule_data = resp.json()

    async def cleanup() -> None:
        try:
            await client.delete(
                f"{base_url}/api/v1/routing-rules/{rule_data['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except Exception:
            pass  # Best-effort cleanup — don't fail the test

    return rule_data, cleanup


async def subscribe_to_marketplace(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    provider_id: str,
    webhook_destination_id: str,
) -> tuple[dict, Callable[[], Awaitable[None]]]:
    """Subscribe to a marketplace provider, return (subscription_data, async_cleanup_fn)."""
    resp = await client.post(
        f"{base_url}/api/marketplace/subscribe/{provider_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "webhook_destination_id": webhook_destination_id,
            "consent": True,
        },
    )
    resp.raise_for_status()
    sub_data = resp.json()

    async def cleanup() -> None:
        try:
            await client.delete(
                f"{base_url}/api/marketplace/unsubscribe/{provider_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except Exception:
            pass

    return sub_data, cleanup


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_error_response(
    resp: httpx.Response,
    expected_status: int,
    message_pattern: str | None = None,
) -> None:
    """Assert error response matches expected status and contains a message.

    Handles two API error formats:
    - Domain errors (SageRadarError): {"error": {"code": "...", "message": "..."}}
    - FastAPI validation errors (422): {"detail": [...]} or {"detail": "..."}
    """
    assert resp.status_code == expected_status, (
        f"Expected {expected_status}, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()

    # Extract message from whichever format is present
    msg = None
    if "error" in data and isinstance(data["error"], dict):
        msg = data["error"].get("message", "")
    elif "detail" in data:
        msg = str(data["detail"])

    assert msg is not None, f"No error message found in response: {data}"

    if message_pattern:
        assert re.search(message_pattern, msg, re.IGNORECASE), (
            f"Error '{msg}' doesn't match pattern '{message_pattern}'"
        )


def assert_response_time(resp: httpx.Response, max_ms: int = 3000) -> None:
    """Assert response completed within threshold (generous default for staging)."""
    elapsed_ms = resp.elapsed.total_seconds() * 1000
    assert elapsed_ms < max_ms, (
        f"Response took {elapsed_ms:.0f}ms, exceeds {max_ms}ms threshold"
    )
