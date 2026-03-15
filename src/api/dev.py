"""Development-only router — available when LOCAL_MODE=true.

Provides convenience endpoints for injecting test signals without needing
a running Telegram listener or QStash.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.webhook import WebhookDispatcher
from src.api.deps import Settings, get_db, get_dispatcher, get_settings
from src.core.models import DispatchResult, ParsedSignal, RawSignal

logger = logging.getLogger(__name__)

dev_router = APIRouter(prefix="/api/dev", tags=["dev"])

# A fixed dummy user ID for local development injection
_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class InjectSignalRequest(BaseModel):
    """Payload for the dev signal-injection endpoint."""

    text: str
    channel_id: str = "dev-channel"
    user_id: UUID = Field(default=_DEV_USER_ID, description="Override the dummy user ID if needed")
    message_id: int = 0
    reply_to_msg_id: int | None = None
    dry_run: bool = Field(default=False, description="If true, parse and map but don't dispatch or persist")


class InjectSignalResponse(BaseModel):
    raw_signal: RawSignal
    results: list[DispatchResult]
    parsed: dict[str, Any] | None = None
    mapped_payloads: list[dict[str, Any]] | None = None


@dev_router.post("/inject-signal", response_model=InjectSignalResponse)
async def inject_signal(
    body: InjectSignalRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    dispatcher: Annotated[WebhookDispatcher, Depends(get_dispatcher)],
) -> InjectSignalResponse:
    """Inject a fake signal and run it through the processing pipeline.

    This endpoint creates a :class:`RawSignal` with a dummy user ID and
    the current timestamp, then invokes the same ``process_signal`` pipeline
    used by the production workflow endpoint.

    When ``dry_run=True``, the signal is parsed and mapped but NOT dispatched
    or persisted.  The response includes the parsed data and mapped payloads.
    """
    raw_signal = RawSignal(
        user_id=body.user_id,
        channel_id=body.channel_id,
        raw_message=body.text,
        message_id=body.message_id,
        reply_to_msg_id=body.reply_to_msg_id,
        timestamp=datetime.now(timezone.utc),
    )

    logger.info(
        "DEV inject-signal: channel=%s dry_run=%s text=%s",
        body.channel_id,
        body.dry_run,
        body.text[:80],
    )

    if body.dry_run:
        return await _dry_run(raw_signal, db, settings)

    # Import and call the same pipeline used by the workflow endpoint
    from src.api.workflow import process_signal

    results = await process_signal(
        raw_signal=raw_signal,
        request=request,
        db=db,
        settings=settings,
        dispatcher=dispatcher,
    )

    return InjectSignalResponse(raw_signal=raw_signal, results=results)


async def _dry_run(
    raw_signal: RawSignal,
    db: AsyncSession,
    settings: Settings,
) -> InjectSignalResponse:
    """Parse and map without dispatching or persisting."""
    from src.adapters.db.models import RoutingRuleModel
    from src.adapters.openai import OpenAISignalParser
    from src.core.mapper import apply_symbol_mapping, build_webhook_payload
    from src.core.models import RoutingRule

    # Look up original message for reply context
    original_text: str | None = None
    if raw_signal.reply_to_msg_id:
        from src.adapters.db.models import SignalLogModel
        row = await db.execute(
            select(SignalLogModel.raw_message).where(
                SignalLogModel.channel_id == raw_signal.channel_id,
                SignalLogModel.message_id == raw_signal.reply_to_msg_id,
            ).limit(1)
        )
        original_text = row.scalar_one_or_none()

    # Load custom AI instructions
    ci_row = await db.execute(
        select(RoutingRuleModel.custom_ai_instructions).where(
            RoutingRuleModel.user_id == raw_signal.user_id,
            RoutingRuleModel.source_channel_id == raw_signal.channel_id,
            RoutingRuleModel.is_active.is_(True),
            RoutingRuleModel.custom_ai_instructions.isnot(None),
            RoutingRuleModel.custom_ai_instructions != "",
        ).limit(1)
    )
    custom_instructions = ci_row.scalar_one_or_none()

    # Parse
    parser = OpenAISignalParser(api_key=settings.OPENAI_API_KEY)
    parsed = await parser.parse(
        raw_signal,
        original_context=original_text,
        custom_instructions=custom_instructions,
    )

    parsed_dict = parsed.model_dump()

    if not parsed.is_valid_signal:
        return InjectSignalResponse(
            raw_signal=raw_signal,
            results=[DispatchResult(status="ignored", error_message=parsed.ignore_reason)],
            parsed=parsed_dict,
            mapped_payloads=[],
        )

    # Load routing rules and map
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.source_channel_id == raw_signal.channel_id,
            RoutingRuleModel.user_id == raw_signal.user_id,
            RoutingRuleModel.is_active.is_(True),
        )
    )
    rules = result.scalars().all()

    mapped_payloads: list[dict] = []
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
            webhook_body_template=rule_row.webhook_body_template,
            rule_name=rule_row.rule_name,
            destination_label=rule_row.destination_label,
            destination_type=rule_row.destination_type,
            custom_ai_instructions=rule_row.custom_ai_instructions,
            is_active=rule_row.is_active,
        )
        mapped_signal = apply_symbol_mapping(parsed, rule)
        try:
            payload = build_webhook_payload(mapped_signal, rule)
            payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
            mapped_payloads.append({
                "rule_id": str(rule.id),
                "rule_name": rule.rule_name,
                "destination_label": rule.destination_label,
                "payload": payload_dict,
            })
        except Exception as exc:
            mapped_payloads.append({
                "rule_id": str(rule.id),
                "rule_name": rule.rule_name,
                "error": str(exc),
            })

    return InjectSignalResponse(
        raw_signal=raw_signal,
        results=[],
        parsed=parsed_dict,
        mapped_payloads=mapped_payloads,
    )
