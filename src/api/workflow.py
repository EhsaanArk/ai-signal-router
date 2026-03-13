"""Internal workflow router — signal processing pipeline.

This router exposes the ``/api/workflow/process-signal`` endpoint that
receives a raw signal (typically enqueued by QStash or the dev inject
endpoint) and runs the full parse → route → dispatch pipeline.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import RoutingRuleModel, SignalLogModel
from src.api.deps import Settings, get_db, get_settings
from src.core.mapper import apply_symbol_mapping, build_webhook_payload
from src.core.models import DispatchResult, ParsedSignal, RawSignal

logger = logging.getLogger(__name__)

workflow_router = APIRouter(tags=["workflow"])


# TODO: In production mode, validate the Upstash-Signature header from
# QStash to ensure the request is authentic.  For MVP / LOCAL_MODE this
# validation is skipped.


@workflow_router.post("/api/workflow/process-signal", response_model=list[DispatchResult])
async def process_signal(
    raw_signal: RawSignal,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DispatchResult]:
    """Execute the full signal processing pipeline.

    Steps
    -----
    1. Parse the raw message via the OpenAI adapter → ``ParsedSignal``.
    2. If the signal is not valid, log as *ignored* and return early.
    3. Look up active routing rules for the originating channel.
    4. For each rule: apply symbol mapping, build webhook payload, dispatch.
    5. Persist a ``SignalLogModel`` row for every dispatch attempt.
    """

    # ------------------------------------------------------------------
    # Step 1 — Parse
    # ------------------------------------------------------------------
    parsed: ParsedSignal
    try:
        from src.adapters.openai import OpenAISignalParser

        parser = OpenAISignalParser(api_key=settings.OPENAI_API_KEY)
        parsed = await parser.parse(raw_signal)
    except Exception as exc:
        logger.error("Signal parsing failed: %s", exc)
        # Log the failure
        db.add(
            SignalLogModel(
                user_id=raw_signal.user_id,
                raw_message=raw_signal.raw_message,
                status="failed",
                error_message=f"Parse error: {exc}",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse signal: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # Step 2 — Early exit for invalid signals
    # ------------------------------------------------------------------
    if not parsed.is_valid_signal:
        logger.info(
            "Signal ignored (channel=%s): %s",
            raw_signal.channel_id,
            parsed.ignore_reason,
        )
        db.add(
            SignalLogModel(
                user_id=raw_signal.user_id,
                raw_message=raw_signal.raw_message,
                parsed_data=parsed.model_dump(),
                status="ignored",
                error_message=parsed.ignore_reason,
            )
        )
        return [
            DispatchResult(
                routing_rule_id=raw_signal.user_id,  # placeholder — no rule
                status="ignored",
                error_message=parsed.ignore_reason,
            )
        ]

    # ------------------------------------------------------------------
    # Step 3 — Look up routing rules for this channel
    # ------------------------------------------------------------------
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.source_channel_id == raw_signal.channel_id,
            RoutingRuleModel.user_id == raw_signal.user_id,
            RoutingRuleModel.is_active.is_(True),
        )
    )
    rules = result.scalars().all()

    if not rules:
        logger.warning(
            "No active routing rules for channel %s / user %s",
            raw_signal.channel_id,
            raw_signal.user_id,
        )
        db.add(
            SignalLogModel(
                user_id=raw_signal.user_id,
                raw_message=raw_signal.raw_message,
                parsed_data=parsed.model_dump(),
                status="ignored",
                error_message="No routing rules configured for this channel",
            )
        )
        return []

    # ------------------------------------------------------------------
    # Step 4 — Dispatch to each destination
    # ------------------------------------------------------------------
    from src.adapters.webhook import WebhookDispatcher
    from src.core.models import RoutingRule

    dispatcher = WebhookDispatcher()
    results: list[DispatchResult] = []

    for rule_row in rules:
        rule = RoutingRule(
            id=rule_row.id,
            user_id=rule_row.user_id,
            source_channel_id=rule_row.source_channel_id,
            source_channel_name=rule_row.source_channel_name,
            destination_webhook_url=rule_row.destination_webhook_url,
            payload_version=rule_row.payload_version,
            symbol_mappings=rule_row.symbol_mappings or {},
            risk_overrides=rule_row.risk_overrides or {},
            is_active=rule_row.is_active,
        )

        # Apply symbol mapping
        mapped_signal = apply_symbol_mapping(parsed, rule)

        # Build payload
        payload = build_webhook_payload(mapped_signal, rule)

        # Dispatch
        try:
            dispatch_result = await dispatcher.dispatch(mapped_signal, rule)
            dispatch_result.webhook_payload = payload
        except Exception as exc:
            logger.error("Webhook dispatch failed for rule %s: %s", rule.id, exc)
            dispatch_result = DispatchResult(
                routing_rule_id=rule.id,
                status="failed",
                error_message=str(exc),
                webhook_payload=payload,
            )

        results.append(dispatch_result)

        # ------------------------------------------------------------------
        # Step 5 — Log each dispatch result
        # ------------------------------------------------------------------
        db.add(
            SignalLogModel(
                user_id=raw_signal.user_id,
                routing_rule_id=rule.id,
                raw_message=raw_signal.raw_message,
                parsed_data=parsed.model_dump(),
                webhook_payload=payload,
                status=dispatch_result.status,
                error_message=dispatch_result.error_message,
            )
        )

    return results
