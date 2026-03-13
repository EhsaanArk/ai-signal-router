"""QStash / local queue adapters implementing the ``QueuePort`` protocol.

Two implementations are provided:

* ``QStashPublisher`` — production mode.  Publishes ``RawSignal`` payloads to
  an Upstash QStash topic via HTTP POST so that the workflow endpoint can
  process them asynchronously.
* ``LocalQueueAdapter`` — local development mode.  Calls an async callback
  directly in-process, bypassing all external queue infrastructure.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

import httpx

from src.core.models import RawSignal

logger = logging.getLogger(__name__)


class QStashPublisher:
    """Production ``QueuePort`` that publishes signals to Upstash QStash.

    Parameters
    ----------
    qstash_token:
        Bearer token for the QStash REST API.
    workflow_url:
        The destination URL that QStash will deliver the message to
        (i.e. the ``/api/workflow/process-signal`` endpoint on the
        FastAPI backend).
    """

    QSTASH_PUBLISH_URL = "https://qstash.upstash.io/v2/publish/"

    def __init__(self, qstash_token: str, workflow_url: str) -> None:
        self._token = qstash_token
        self._workflow_url = workflow_url
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    async def enqueue(self, raw_signal: RawSignal) -> None:
        """Publish *raw_signal* as JSON to QStash for async processing."""
        url = f"{self.QSTASH_PUBLISH_URL}{self._workflow_url}"
        payload = raw_signal.model_dump_json()

        response = await self._client.post(
            url,
            content=payload,
        )

        if response.is_success:
            logger.info(
                "Published signal (msg %d) to QStash",
                raw_signal.message_id,
            )
        else:
            logger.error(
                "QStash publish failed — HTTP %d: %s",
                response.status_code,
                response.text[:500],
            )
            response.raise_for_status()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


class LocalQueueAdapter:
    """Development ``QueuePort`` that processes signals in-process.

    Instead of publishing to an external queue, the adapter invokes the
    provided *callback* directly.  This removes the need for QStash,
    Upstash Workflow, or any network infrastructure during local testing.

    Parameters
    ----------
    callback:
        An async callable that receives a ``RawSignal`` and processes it
        (e.g. parses, routes, and dispatches).
    """

    def __init__(self, callback: Callable[[RawSignal], Awaitable[None]]) -> None:
        self._callback = callback

    async def enqueue(self, raw_signal: RawSignal) -> None:
        """Process *raw_signal* synchronously via the registered callback."""
        logger.debug(
            "LocalQueueAdapter: processing signal (msg %d) in-process",
            raw_signal.message_id,
        )
        await self._callback(raw_signal)
