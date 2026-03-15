"""Tests for ``src.adapters.qstash.publisher`` — QStashPublisher and LocalQueueAdapter.

Covers successful publish, HTTP error handling, and the local in-process
callback path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest

from src.adapters.qstash.publisher import LocalQueueAdapter, QStashPublisher
from src.core.models import RawSignal

SAMPLE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_TOKEN = "test-qstash-token"
SAMPLE_WORKFLOW_URL = "https://my-app.railway.app/api/workflow/process-signal"


@pytest.fixture
def raw_signal() -> RawSignal:
    return RawSignal(
        user_id=SAMPLE_USER_ID,
        channel_id="-1001234567890",
        raw_message="EURUSD BUY @ 1.1000\nSL: 1.0950\nTP1: 1.1050",
        message_id=42,
    )


# ---------------------------------------------------------------------------
# QStashPublisher — successful publish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qstash_publish_posts_to_correct_url(raw_signal: RawSignal):
    """``enqueue`` should POST to ``QSTASH_PUBLISH_URL + workflow_url``
    with the serialised RawSignal as the body and the Bearer token header."""
    publisher = QStashPublisher(SAMPLE_TOKEN, SAMPLE_WORKFLOW_URL)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.is_success = True
    mock_response.status_code = 200

    publisher._client = AsyncMock(spec=httpx.AsyncClient)
    publisher._client.post = AsyncMock(return_value=mock_response)

    await publisher.enqueue(raw_signal)

    expected_url = f"{QStashPublisher.QSTASH_PUBLISH_URL}{SAMPLE_WORKFLOW_URL}"
    publisher._client.post.assert_awaited_once_with(
        expected_url,
        content=raw_signal.model_dump_json(),
    )


@pytest.mark.asyncio
async def test_qstash_publisher_sends_bearer_token():
    """The underlying httpx client must be initialised with the
    Authorization: Bearer header."""
    publisher = QStashPublisher(SAMPLE_TOKEN, SAMPLE_WORKFLOW_URL)

    auth_header = publisher._client.headers.get("authorization")
    assert auth_header == f"Bearer {SAMPLE_TOKEN}"

    await publisher.close()


# ---------------------------------------------------------------------------
# QStashPublisher — error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qstash_publish_raises_on_http_error(raw_signal: RawSignal):
    """When QStash returns a non-success status, ``enqueue`` should call
    ``raise_for_status()`` which raises an ``httpx.HTTPStatusError``."""
    publisher = QStashPublisher(SAMPLE_TOKEN, SAMPLE_WORKFLOW_URL)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.is_success = False
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Server Error",
        request=MagicMock(spec=httpx.Request),
        response=mock_response,
    )

    publisher._client = AsyncMock(spec=httpx.AsyncClient)
    publisher._client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(httpx.HTTPStatusError):
        await publisher.enqueue(raw_signal)


# ---------------------------------------------------------------------------
# LocalQueueAdapter — callback invocation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_queue_adapter_calls_callback(raw_signal: RawSignal):
    """``enqueue`` should directly invoke the registered async callback
    with the provided ``RawSignal``."""
    callback = AsyncMock()
    adapter = LocalQueueAdapter(callback)

    await adapter.enqueue(raw_signal)

    callback.assert_awaited_once_with(raw_signal)


@pytest.mark.asyncio
async def test_local_queue_adapter_no_http_calls(raw_signal: RawSignal):
    """``LocalQueueAdapter`` must process signals entirely in-process
    without making any HTTP requests."""
    callback = AsyncMock()
    adapter = LocalQueueAdapter(callback)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        await adapter.enqueue(raw_signal)
        mock_post.assert_not_awaited()

    callback.assert_awaited_once_with(raw_signal)


@pytest.mark.asyncio
async def test_local_queue_adapter_propagates_callback_error(raw_signal: RawSignal):
    """If the callback raises, ``enqueue`` should propagate the exception."""
    callback = AsyncMock(side_effect=ValueError("processing failed"))
    adapter = LocalQueueAdapter(callback)

    with pytest.raises(ValueError, match="processing failed"):
        await adapter.enqueue(raw_signal)
