"""Webhook adapter implementing the ``SignalDispatcher`` protocol.

Uses ``httpx.AsyncClient`` to POST structured payloads to SageMaster webhook
URLs defined in each routing rule.
"""

from __future__ import annotations

import asyncio
import logging
import random

import httpx
import sentry_sdk

from src.core.mapper import apply_symbol_mapping, build_webhook_payload
from src.core.models import DispatchResult, ParsedSignal, RoutingRule

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5  # seconds
_RETRYABLE_CODES = {429, 500, 502, 503, 504}


class WebhookDispatcher:
    """Concrete ``SignalDispatcher`` that delivers payloads over HTTP POST.

    An internal ``httpx.AsyncClient`` is reused across dispatches for
    connection pooling.  Call :meth:`close` (or use as an async context
    manager) to release resources when done.
    """

    def __init__(self, timeout: float = 15.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

    async def dispatch(
        self,
        signal: ParsedSignal,
        rule: RoutingRule,
    ) -> DispatchResult:
        """Apply symbol mapping, build the payload, and POST to the webhook.

        Retries up to ``MAX_RETRIES`` times on transient failures (5xx, 429,
        network errors) with exponential backoff.  Non-retryable 4xx responses
        are returned immediately as failures.
        """
        # 1. Apply symbol mapping from routing rule
        mapped_signal = apply_symbol_mapping(signal, rule)

        # 2. Build the webhook payload (V1 or V2) via core mapper
        payload_model = build_webhook_payload(mapped_signal, rule)
        if isinstance(payload_model, dict):
            payload = {k: v for k, v in payload_model.items() if v is not None}
        else:
            payload = payload_model.model_dump(exclude_none=True)

        # 3. Apply per-destination risk overrides (e.g. lot size)
        if rule.risk_overrides:
            payload.update(rule.risk_overrides)

        # 4. POST with retry logic
        last_error: str = ""
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.post(
                    rule.destination_webhook_url,
                    json=payload,
                )

                if response.is_success:
                    logger.info(
                        "Dispatched signal to %s — HTTP %d (attempt %d)",
                        rule.destination_webhook_url,
                        response.status_code,
                        attempt + 1,
                    )
                    return DispatchResult(
                        routing_rule_id=rule.id,
                        status="success",
                        webhook_payload=payload,
                        attempt_count=attempt + 1,
                    )

                last_error = f"HTTP {response.status_code}: {response.text[:500]}"

                if response.status_code not in _RETRYABLE_CODES:
                    logger.warning(
                        "Webhook returned non-retryable %d for rule %s: %s",
                        response.status_code,
                        rule.id,
                        last_error,
                    )
                    return DispatchResult(
                        routing_rule_id=rule.id,
                        status="failed",
                        error_message=last_error,
                        webhook_payload=payload,
                        attempt_count=attempt + 1,
                    )

                logger.warning(
                    "Retryable HTTP %d for rule %s (attempt %d/%d)",
                    response.status_code,
                    rule.id,
                    attempt + 1,
                    MAX_RETRIES,
                )

            except httpx.HTTPError as exc:
                last_error = f"HTTP error dispatching to {rule.destination_webhook_url}: {exc}"
                logger.warning(
                    "Network error for rule %s (attempt %d/%d): %s",
                    rule.id,
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )

            # Exponential backoff with jitter before next attempt
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.25)
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "All %d attempts exhausted for rule %s: %s",
            MAX_RETRIES,
            rule.id,
            last_error,
        )
        sentry_sdk.capture_message(
            f"Webhook dispatch failed after {MAX_RETRIES} retries for rule {rule.id}: {last_error}",
            level="error",
        )
        return DispatchResult(
            routing_rule_id=rule.id,
            status="failed",
            error_message=f"Failed after {MAX_RETRIES} attempts: {last_error}",
            webhook_payload=payload,
            attempt_count=MAX_RETRIES,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> WebhookDispatcher:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
