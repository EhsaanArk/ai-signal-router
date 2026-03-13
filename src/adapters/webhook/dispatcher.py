"""Webhook adapter implementing the ``SignalDispatcher`` protocol.

Uses ``httpx.AsyncClient`` to POST structured payloads to SageMaster webhook
URLs defined in each routing rule.
"""

from __future__ import annotations

import logging

import httpx

from src.core.mapper import apply_symbol_mapping, build_webhook_payload
from src.core.models import DispatchResult, ParsedSignal, RoutingRule

logger = logging.getLogger(__name__)


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

        Returns a ``DispatchResult`` with ``status='success'`` on a 2xx
        response, or ``status='failed'`` with an error message otherwise.
        """
        try:
            # 1. Apply symbol mapping from routing rule
            mapped_signal = apply_symbol_mapping(signal, rule)

            # 2. Build the webhook payload (V1 or V2) via core mapper
            payload = build_webhook_payload(mapped_signal, rule)

            # 3. POST to the destination webhook URL
            response = await self._client.post(
                rule.destination_webhook_url,
                json=payload,
            )

            # 4. Determine success/failure from status code
            if response.is_success:
                logger.info(
                    "Dispatched signal to %s — HTTP %d",
                    rule.destination_webhook_url,
                    response.status_code,
                )
                return DispatchResult(
                    routing_rule_id=rule.id,
                    status="success",
                    webhook_payload=payload,
                )
            else:
                error_msg = (
                    f"HTTP {response.status_code}: {response.text[:500]}"
                )
                logger.warning(
                    "Webhook returned non-success for rule %s: %s",
                    rule.id,
                    error_msg,
                )
                return DispatchResult(
                    routing_rule_id=rule.id,
                    status="failed",
                    error_message=error_msg,
                    webhook_payload=payload,
                )

        except httpx.HTTPError as exc:
            error_msg = f"HTTP error dispatching to {rule.destination_webhook_url}: {exc}"
            logger.error(error_msg)
            return DispatchResult(
                routing_rule_id=rule.id,
                status="failed",
                error_message=error_msg,
            )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> WebhookDispatcher:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
