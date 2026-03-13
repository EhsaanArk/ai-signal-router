"""Tests for src.adapters.webhook.dispatcher — async webhook dispatch."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.adapters.webhook.dispatcher import WebhookDispatcher


@pytest.mark.asyncio
async def test_dispatch_success(sample_parsed_signal, sample_routing_rule_v1):
    """A 200 response should produce a DispatchResult with status='success'."""
    mock_response = httpx.Response(
        200,
        request=httpx.Request("POST", sample_routing_rule_v1.destination_webhook_url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "success"
    assert result.routing_rule_id == sample_routing_rule_v1.id
    assert result.webhook_payload is not None
    assert result.error_message is None


@pytest.mark.asyncio
async def test_dispatch_failure(sample_parsed_signal, sample_routing_rule_v1):
    """A 400 response should produce a DispatchResult with status='failed'."""
    mock_response = httpx.Response(
        400,
        text="Bad Request",
        request=httpx.Request("POST", sample_routing_rule_v1.destination_webhook_url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "failed"
    assert "400" in result.error_message
    assert result.webhook_payload is not None


@pytest.mark.asyncio
async def test_dispatch_network_error(sample_parsed_signal, sample_routing_rule_v1):
    """A connection error should produce a DispatchResult with status='failed'."""
    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.side_effect = httpx.ConnectError("Connection refused")

    result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "failed"
    assert result.error_message is not None
    assert result.webhook_payload is None
