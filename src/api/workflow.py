"""Internal workflow router — signal processing pipeline.

This router exposes the ``/api/workflow/process-signal`` endpoint that
receives a raw signal (typically enqueued by QStash or the dev inject
endpoint) and runs the full parse → route → dispatch pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import RoutingRuleModel, SignalLogModel
from src.adapters.webhook import WebhookDispatcher
from src.api.deps import Settings, get_db, get_dispatcher, get_settings
from src.api.qstash_auth import verify_qstash_signature
from src.core.models import DispatchResult, ParsedSignal, RawSignal, RoutingRule

logger = logging.getLogger(__name__)

workflow_router = APIRouter(tags=["workflow"])


@workflow_router.post(
    "/api/workflow/process-signal",
    response_model=list[DispatchResult],
    dependencies=[Depends(verify_qstash_signature)],
)
async def process_signal(
    raw_signal: RawSignal,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    dispatcher: Annotated[WebhookDispatcher, Depends(get_dispatcher)],
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
    # Step 1a — Look up original message if this is a reply
    # ------------------------------------------------------------------
    original_message_text: str | None = None
    if raw_signal.reply_to_msg_id:
        row = await db.execute(
            select(SignalLogModel.raw_message).where(
                SignalLogModel.channel_id == raw_signal.channel_id,
                SignalLogModel.message_id == raw_signal.reply_to_msg_id,
            ).limit(1)
        )
        original_message_text = row.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Step 1b — Load custom AI instructions for this channel (if any)
    # ------------------------------------------------------------------
    custom_instructions_row = await db.execute(
        select(RoutingRuleModel.custom_ai_instructions).where(
            RoutingRuleModel.user_id == raw_signal.user_id,
            RoutingRuleModel.source_channel_id == raw_signal.channel_id,
            RoutingRuleModel.is_active.is_(True),
            RoutingRuleModel.custom_ai_instructions.isnot(None),
            RoutingRuleModel.custom_ai_instructions != "",
        ).limit(1)
    )
    custom_instructions = custom_instructions_row.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Step 1c — Parse
    # ------------------------------------------------------------------
    parsed: ParsedSignal
    try:
        from src.adapters.openai import OpenAISignalParser

        parser = OpenAISignalParser(api_key=settings.OPENAI_API_KEY)
        parsed = await parser.parse(
            raw_signal,
            original_context=original_message_text,
            custom_instructions=custom_instructions,
        )
    except Exception as exc:
        logger.error("Signal parsing failed: %s", exc)
        # Log the failure
        db.add(
            SignalLogModel(
                user_id=raw_signal.user_id,
                message_id=raw_signal.message_id,
                channel_id=raw_signal.channel_id,
                reply_to_msg_id=raw_signal.reply_to_msg_id,
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
                message_id=raw_signal.message_id,
                channel_id=raw_signal.channel_id,
                reply_to_msg_id=raw_signal.reply_to_msg_id,
                raw_message=raw_signal.raw_message,
                parsed_data=parsed.model_dump(),
                status="ignored",
                error_message=parsed.ignore_reason,
            )
        )
        return [
            DispatchResult(
                routing_rule_id=None,
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
                message_id=raw_signal.message_id,
                channel_id=raw_signal.channel_id,
                reply_to_msg_id=raw_signal.reply_to_msg_id,
                raw_message=raw_signal.raw_message,
                parsed_data=parsed.model_dump(),
                status="ignored",
                error_message="No routing rules configured for this channel",
            )
        )
        return []

    # ------------------------------------------------------------------
    # Step 4 — Dispatch to each destination (in parallel)
    # ------------------------------------------------------------------
    from src.core.mapper import _signal_action, apply_symbol_mapping, check_template_symbol_mismatch

    async def _process_single_rule(
        rule_row: RoutingRuleModel,
    ) -> tuple[DispatchResult, dict]:
        """Process one routing rule and return (result, signal_log_kwargs).

        Does NOT write to the DB — the caller batches all writes after
        ``asyncio.gather`` completes (AsyncSession is not safe for
        concurrent use).
        """
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
            enabled_actions=rule_row.enabled_actions,
            keyword_blacklist=rule_row.keyword_blacklist or [],
        )

        base_log = dict(
            user_id=raw_signal.user_id,
            message_id=raw_signal.message_id,
            channel_id=raw_signal.channel_id,
            reply_to_msg_id=raw_signal.reply_to_msg_id,
            routing_rule_id=rule.id,
            raw_message=raw_signal.raw_message,
            parsed_data=parsed.model_dump(),
        )

        # Pre-dispatch filtering: keyword blacklist check
        if rule.keyword_blacklist:
            raw_lower = raw_signal.raw_message.lower()
            matched_kw = next(
                (kw for kw in rule.keyword_blacklist if kw.lower() in raw_lower),
                None,
            )
            if matched_kw:
                logger.info(
                    "Keyword '%s' blacklisted for rule %s",
                    matched_kw, rule.id,
                )
                dr = DispatchResult(
                    routing_rule_id=rule.id,
                    status="ignored",
                    error_message=f"Message contains blacklisted keyword '{matched_kw}'",
                )
                return dr, {**base_log, "status": "ignored", "error_message": dr.error_message}

        # Pre-dispatch filtering: enabled_actions check
        try:
            computed_action = _signal_action(parsed)
            if rule.enabled_actions is not None and computed_action.value not in rule.enabled_actions:
                logger.info(
                    "Action '%s' disabled for rule %s",
                    computed_action.value, rule.id,
                )
                dr = DispatchResult(
                    routing_rule_id=rule.id,
                    status="ignored",
                    error_message=f"Action '{computed_action.value}' is disabled for this route",
                )
                return dr, {**base_log, "status": "ignored", "error_message": dr.error_message}
        except ValueError as exc:
            # Unsupported actions (e.g. modify_tp) — log as ignored
            logger.info(
                "Action '%s' unsupported for rule %s: %s",
                parsed.action, rule.id, exc,
            )
            dr = DispatchResult(
                routing_rule_id=rule.id,
                status="ignored",
                error_message=str(exc),
            )
            return dr, {**base_log, "status": "ignored", "error_message": dr.error_message}

        # Symbol mismatch filter
        mapped_signal = apply_symbol_mapping(parsed, rule)
        mismatch_reason = check_template_symbol_mismatch(mapped_signal, rule)
        if mismatch_reason:
            logger.info(
                "Symbol mismatch for rule %s: %s", rule.id, mismatch_reason,
            )
            dr = DispatchResult(
                routing_rule_id=rule.id,
                status="ignored",
                error_message=mismatch_reason,
            )
            return dr, {**base_log, "status": "ignored", "error_message": mismatch_reason}

        # Dispatch webhook
        try:
            dr = await dispatcher.dispatch(parsed, rule)
        except Exception as exc:
            logger.error("Webhook dispatch failed for rule %s: %s", rule.id, exc)
            dr = DispatchResult(
                routing_rule_id=rule.id,
                status="failed",
                error_message=str(exc),
            )

        return dr, {
            **base_log,
            "webhook_payload": dr.webhook_payload,
            "status": dr.status,
            "error_message": dr.error_message,
        }

    # Run all rules in parallel
    outcomes = await asyncio.gather(
        *[_process_single_rule(rule_row) for rule_row in rules],
        return_exceptions=True,
    )

    # ------------------------------------------------------------------
    # Step 5 — Collect results and log sequentially (session-safe)
    # ------------------------------------------------------------------
    results: list[DispatchResult] = []
    for i, outcome in enumerate(outcomes):
        if isinstance(outcome, Exception):
            logger.error("Unexpected error processing rule %s: %s", rules[i].id, outcome)
            dr = DispatchResult(
                routing_rule_id=rules[i].id,
                status="failed",
                error_message=str(outcome),
            )
            results.append(dr)
            db.add(SignalLogModel(
                user_id=raw_signal.user_id,
                message_id=raw_signal.message_id,
                channel_id=raw_signal.channel_id,
                reply_to_msg_id=raw_signal.reply_to_msg_id,
                routing_rule_id=rules[i].id,
                raw_message=raw_signal.raw_message,
                parsed_data=parsed.model_dump(),
                status="failed",
                error_message=str(outcome),
            ))
        else:
            dispatch_result, log_kwargs = outcome
            results.append(dispatch_result)
            db.add(SignalLogModel(**log_kwargs))

    # Invalidate log stats cache after logging new signals
    try:
        cache = request.app.state.cache
        await cache.delete(f"log_stats:{raw_signal.user_id}")
    except Exception:
        logger.debug("Failed to invalidate log stats cache")

    # ------------------------------------------------------------------
    # Step 6 — Send notification if configured
    # ------------------------------------------------------------------
    actionable_results = [r for r in results if r.status in ("success", "failed")]
    if actionable_results:
        try:
            from src.adapters.db.models import UserModel
            from src.adapters.email import ResendNotifier
            from src.core.notifications import NotificationPreference

            user_row = (
                await db.execute(
                    select(UserModel.email, UserModel.notification_preferences).where(
                        UserModel.id == raw_signal.user_id
                    )
                )
            ).one_or_none()

            if user_row:
                prefs = NotificationPreference(**(user_row.notification_preferences or {}))
                has_failures = any(r.status == "failed" for r in actionable_results)
                has_successes = any(r.status == "success" for r in actionable_results)

                should_notify = (
                    (prefs.email_on_failure and has_failures)
                    or (prefs.email_on_success and has_successes)
                )

                if should_notify:
                    notifier = ResendNotifier(api_key=settings.RESEND_API_KEY)
                    await notifier.send_dispatch_summary(
                        user_email=user_row.email,
                        signal_symbol=parsed.symbol or "UNKNOWN",
                        results=actionable_results,
                    )
        except Exception as exc:
            logger.error("Email notification failed (non-blocking): %s", exc)

        # Telegram notification
        try:
            should_tg_notify = (
                (prefs.telegram_on_failure and has_failures)
                or (prefs.telegram_on_success and has_successes)
            )

            if should_tg_notify and prefs.telegram_bot_chat_id:
                from src.adapters.telegram.notifier import TelegramNotifier

                tg_notifier = TelegramNotifier(bot_token=settings.TELEGRAM_BOT_TOKEN)
                await tg_notifier.send_dispatch_summary(
                    chat_id=prefs.telegram_bot_chat_id,
                    signal_symbol=parsed.symbol or "UNKNOWN",
                    results=actionable_results,
                )
        except Exception as exc:
            logger.error("Telegram notification failed (non-blocking): %s", exc)

    return results
