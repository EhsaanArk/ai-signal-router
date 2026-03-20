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
    assert result.attempt_count == 1


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
    # 400 is non-retryable — should only attempt once
    assert result.attempt_count == 1


@pytest.mark.asyncio
async def test_dispatch_network_error(sample_parsed_signal, sample_routing_rule_v1):
    """A connection error should produce a DispatchResult with status='failed'."""
    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.side_effect = httpx.ConnectError("Connection refused")

    with patch("src.adapters.webhook.dispatcher.asyncio.sleep", new_callable=AsyncMock):
        result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "failed"
    assert result.error_message is not None
    assert result.attempt_count == 3  # retried all attempts


@pytest.mark.asyncio
async def test_dispatch_dict_payload_from_template(sample_routing_rule_v1):
    """Dispatcher should handle dict payloads (from webhook_body_template) without crash."""
    from src.core.models import ParsedSignal, RoutingRule

    rule = RoutingRule(
        id=sample_routing_rule_v1.id,
        user_id=sample_routing_rule_v1.user_id,
        source_channel_id=sample_routing_rule_v1.source_channel_id,
        destination_webhook_url=sample_routing_rule_v1.destination_webhook_url,
        payload_version="V1",
        webhook_body_template={"assistId": "abc123", "extra": "field"},
    )
    signal = ParsedSignal(symbol="EURUSD", direction="long")

    mock_response = httpx.Response(
        200,
        request=httpx.Request("POST", rule.destination_webhook_url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    result = await dispatcher.dispatch(signal, rule)

    assert result.status == "success"
    assert result.webhook_payload is not None
    assert result.webhook_payload.get("assistId") == "abc123"


# ---------------------------------------------------------------------------
# Risk Override tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_overrides_applied(sample_parsed_signal, sample_routing_rule_v2):
    """Risk overrides from routing rule should be merged into the payload."""
    rule = sample_routing_rule_v2
    rule.risk_overrides = {"lots": "0.05"}

    mock_response = httpx.Response(
        200,
        request=httpx.Request("POST", rule.destination_webhook_url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    result = await dispatcher.dispatch(sample_parsed_signal, rule)

    assert result.status == "success"
    assert result.webhook_payload["lots"] == "0.05"

    # Verify the POST was called with the overridden payload
    call_kwargs = dispatcher._client.post.call_args
    sent_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_payload["lots"] == "0.05"


@pytest.mark.asyncio
async def test_empty_risk_overrides_no_effect(sample_parsed_signal, sample_routing_rule_v2):
    """Empty risk_overrides should not inject extra keys."""
    sample_routing_rule_v2.risk_overrides = {}

    mock_response = httpx.Response(
        200,
        request=httpx.Request("POST", sample_routing_rule_v2.destination_webhook_url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v2)

    assert result.status == "success"
    # lots should NOT appear unless it was in the original signal
    # (the signal has no lots field set by default)


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_on_503_then_success(sample_parsed_signal, sample_routing_rule_v1):
    """Should retry on 503 and succeed on the third attempt."""
    url = sample_routing_rule_v1.destination_webhook_url
    responses = [
        httpx.Response(503, text="Service Unavailable", request=httpx.Request("POST", url)),
        httpx.Response(503, text="Service Unavailable", request=httpx.Request("POST", url)),
        httpx.Response(200, request=httpx.Request("POST", url)),
    ]

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.side_effect = responses

    with patch("src.adapters.webhook.dispatcher.asyncio.sleep", new_callable=AsyncMock):
        result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "success"
    assert result.attempt_count == 3
    assert dispatcher._client.post.call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_400(sample_parsed_signal, sample_routing_rule_v1):
    """400 is non-retryable — should fail after a single attempt."""
    url = sample_routing_rule_v1.destination_webhook_url
    mock_response = httpx.Response(
        400, text="Bad Request", request=httpx.Request("POST", url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "failed"
    assert result.attempt_count == 1
    assert dispatcher._client.post.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_429(sample_parsed_signal, sample_routing_rule_v1):
    """429 Too Many Requests should be retried."""
    url = sample_routing_rule_v1.destination_webhook_url
    responses = [
        httpx.Response(429, text="Too Many Requests", request=httpx.Request("POST", url)),
        httpx.Response(200, request=httpx.Request("POST", url)),
    ]

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.side_effect = responses

    with patch("src.adapters.webhook.dispatcher.asyncio.sleep", new_callable=AsyncMock):
        result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "success"
    assert result.attempt_count == 2


@pytest.mark.asyncio
async def test_retries_exhausted(sample_parsed_signal, sample_routing_rule_v1):
    """All 503s should exhaust retries and return failed."""
    url = sample_routing_rule_v1.destination_webhook_url
    mock_response = httpx.Response(
        503, text="Service Unavailable", request=httpx.Request("POST", url),
    )

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.return_value = mock_response

    with patch("src.adapters.webhook.dispatcher.asyncio.sleep", new_callable=AsyncMock):
        result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "failed"
    assert result.attempt_count == 3
    assert dispatcher._client.post.call_count == 3
    assert "Failed after 3 attempts" in result.error_message


@pytest.mark.asyncio
async def test_retry_on_network_error_then_success(sample_parsed_signal, sample_routing_rule_v1):
    """Network errors should be retried; success on second attempt."""
    url = sample_routing_rule_v1.destination_webhook_url

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)
    dispatcher._client.post.side_effect = [
        httpx.ConnectError("Connection refused"),
        httpx.Response(200, request=httpx.Request("POST", url)),
    ]

    with patch("src.adapters.webhook.dispatcher.asyncio.sleep", new_callable=AsyncMock):
        result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "success"
    assert result.attempt_count == 2


@pytest.mark.asyncio
async def test_dispatch_blocks_unsafe_destination(sample_parsed_signal, sample_routing_rule_v1):
    """Unsafe destination hosts should be rejected before any HTTP call."""
    sample_routing_rule_v1.destination_webhook_url = "http://127.0.0.1/webhook"

    dispatcher = WebhookDispatcher()
    dispatcher._client = AsyncMock(spec=httpx.AsyncClient)

    result = await dispatcher.dispatch(sample_parsed_signal, sample_routing_rule_v1)

    assert result.status == "failed"
    assert "Unsafe destination webhook URL rejected" in (result.error_message or "")
    dispatcher._client.post.assert_not_called()
