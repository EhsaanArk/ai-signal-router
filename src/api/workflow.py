"""Internal workflow router - signal processing pipeline.

This router exposes the /api/workflow/process-signal endpoint and the
/api/workflow/dispatch-signal endpoint (two-stage dispatch pipeline).
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import os
from typing import Annotated

import sentry_sdk

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import MarketplaceProviderModel, MarketplaceSubscriptionModel, ParserConfigModel, RoutingRuleModel, SignalLogModel
from src.adapters.telemetry import get_tracer
from src.adapters.webhook import WebhookDispatcher
from src.api.deps import Settings, get_db, get_dispatcher, get_settings
from src.api.qstash_auth import verify_qstash_signature
from src.core.constants import PARSER_CONFIG_CACHE_TTL_SECONDS
from src.core.models import (
    DispatchJob, DispatchResult, ParsedSignal, RawSignal, RawSignalMeta,
    RoutingRule, normalize_enabled_actions,
)

logger = logging.getLogger(__name__)
tracer = get_tracer("signal.pipeline")
workflow_router = APIRouter(tags=["workflow"])


def _message_lock_key(raw_signal: RawSignal) -> int:
    material = f"{raw_signal.user_id}:{raw_signal.channel_id}:{raw_signal.message_id}".encode("utf-8")
    digest = hashlib.blake2b(material, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def _dispatch_lock_key(channel_id: str, message_id: int | None, routing_rule_id) -> int:
    """Lock key for Stage-2 dispatch dedup — scoped to (message_id, routing_rule_id)."""
    material = f"dispatch:{channel_id}:{message_id}:{routing_rule_id}".encode("utf-8")
    digest = hashlib.blake2b(material, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


async def _acquire_message_lock(db: AsyncSession, raw_signal: RawSignal) -> bool:
    if not raw_signal.message_id:
        logger.warning("Signal from channel %s has no message_id", raw_signal.channel_id)
        return True
    bind = None
    try:
        bind_getter = getattr(db, "get_bind", None)
        if callable(bind_getter):
            maybe_bind = bind_getter()
            bind = await maybe_bind if inspect.isawaitable(maybe_bind) else maybe_bind
    except Exception:
        return True
    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
    if dialect_name != "postgresql":
        return True
    result = await db.execute(text("SELECT pg_try_advisory_xact_lock(:lock_key)"), {"lock_key": _message_lock_key(raw_signal)})
    return bool(result.scalar_one())


async def _get_parser_config(request: Request, db: AsyncSession) -> tuple[str | None, str, float]:
    import json
    cache = getattr(request.app.state, "cache", None)
    if cache:
        try:
            cached = await cache.get("parser:config")
            if cached:
                data = json.loads(cached)
                return data.get("system_prompt"), data["model_name"], data["temperature"]
        except Exception:
            pass
    try:
        model_row = (await db.execute(select(ParserConfigModel).where(ParserConfigModel.config_key == "model_config", ParserConfigModel.is_active.is_(True)))).scalar_one_or_none()
        prompt_row = (await db.execute(select(ParserConfigModel).where(ParserConfigModel.config_key == "system_prompt", ParserConfigModel.is_active.is_(True)))).scalar_one_or_none()
        model_name = model_row.model_name if model_row else "gpt-4o-mini"
        temperature = model_row.temperature if model_row else 0.0
        system_prompt = prompt_row.system_prompt if prompt_row else None
    except Exception:
        return None, "gpt-4o-mini", 0.0
    if cache:
        try:
            await cache.set("parser:config", json.dumps({"system_prompt": system_prompt, "model_name": model_name, "temperature": temperature}), ttl_seconds=PARSER_CONFIG_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return system_prompt, model_name, temperature


def _build_routing_rule(rule_row: RoutingRuleModel) -> RoutingRule:
    return RoutingRule(id=rule_row.id, user_id=rule_row.user_id, source_channel_id=rule_row.source_channel_id, source_channel_name=rule_row.source_channel_name, destination_webhook_url=rule_row.destination_webhook_url, payload_version=rule_row.payload_version, symbol_mappings=rule_row.symbol_mappings or {}, risk_overrides=rule_row.risk_overrides or {}, webhook_body_template=rule_row.webhook_body_template, rule_name=rule_row.rule_name, destination_label=rule_row.destination_label, destination_type=rule_row.destination_type, custom_ai_instructions=rule_row.custom_ai_instructions, is_active=rule_row.is_active, enabled_actions=normalize_enabled_actions(rule_row.enabled_actions), keyword_blacklist=rule_row.keyword_blacklist or [])


async def _process_single_rule(rule_row: RoutingRuleModel, raw_signal: RawSignal, parsed: ParsedSignal, dispatcher: WebhookDispatcher) -> tuple[DispatchResult, dict]:
    from src.core.mapper import _signal_action, apply_symbol_mapping, check_asset_class_mismatch, check_template_symbol_mismatch
    rule = _build_routing_rule(rule_row)
    base_log = dict(user_id=raw_signal.user_id, message_id=raw_signal.message_id, channel_id=raw_signal.channel_id, reply_to_msg_id=raw_signal.reply_to_msg_id, routing_rule_id=rule.id, raw_message=raw_signal.raw_message, parsed_data=parsed.model_dump(), source_type="telegram")
    if rule.keyword_blacklist:
        raw_lower = raw_signal.raw_message.lower()
        matched_kw = next((kw for kw in rule.keyword_blacklist if kw.lower() in raw_lower), None)
        if matched_kw:
            dr = DispatchResult(routing_rule_id=rule.id, status="ignored", error_message=f"Message contains blacklisted keyword \'{matched_kw}\'")
            return dr, {**base_log, "status": "ignored", "error_message": dr.error_message}
    try:
        computed_action = _signal_action(parsed)
        if rule.enabled_actions is not None and computed_action.value not in rule.enabled_actions:
            dr = DispatchResult(routing_rule_id=rule.id, status="ignored", error_message=f"Action \'{computed_action.value}\' is disabled for this route")
            return dr, {**base_log, "status": "ignored", "error_message": dr.error_message}
    except ValueError as exc:
        dr = DispatchResult(routing_rule_id=rule.id, status="ignored", error_message=str(exc))
        return dr, {**base_log, "status": "ignored", "error_message": dr.error_message}
    mapped_signal = apply_symbol_mapping(parsed, rule)
    mismatch_reason = check_template_symbol_mismatch(mapped_signal, rule)
    if mismatch_reason:
        dr = DispatchResult(routing_rule_id=rule.id, status="ignored", error_message=mismatch_reason)
        return dr, {**base_log, "status": "ignored", "error_message": mismatch_reason}
    asset_mismatch = check_asset_class_mismatch(parsed, rule)
    if asset_mismatch:
        dr = DispatchResult(routing_rule_id=rule.id, status="ignored", error_message=asset_mismatch)
        return dr, {**base_log, "status": "ignored", "error_message": asset_mismatch}
    with tracer.start_as_current_span("signal.dispatch") as dispatch_span:
        dispatch_span.set_attribute("dispatch.rule_id", str(rule.id))
        dispatch_span.set_attribute("dispatch.destination_type", rule.destination_type or "")
        dispatch_span.set_attribute("dispatch.destination_label", rule.destination_label or "")
        try:
            dr = await dispatcher.dispatch(parsed, rule)
            dispatch_span.set_attribute("dispatch.status", dr.status)
        except Exception as exc:
            dispatch_span.record_exception(exc)
            sentry_sdk.capture_exception(exc)
            dr = DispatchResult(routing_rule_id=rule.id, status="failed", error_message=str(exc))
    return dr, {**base_log, "webhook_payload": dr.webhook_payload, "status": dr.status, "error_message": dr.error_message}


async def _send_dispatch_notifications(db, settings, user_id, parsed, results):
    actionable = [r for r in results if r.status in ("success", "failed")]
    if not actionable:
        return
    try:
        from src.adapters.db.models import UserModel
        from src.adapters.email import ResendNotifier
        from src.core.notifications import NotificationPreference
        user_row = (await db.execute(select(UserModel.email, UserModel.notification_preferences).where(UserModel.id == user_id))).one_or_none()
        if not user_row:
            return
        prefs = NotificationPreference(**(user_row.notification_preferences or {}))
        has_f = any(r.status == "failed" for r in actionable)
        has_s = any(r.status == "success" for r in actionable)
        if (prefs.email_on_failure and has_f) or (prefs.email_on_success and has_s):
            notifier = ResendNotifier(api_key=settings.RESEND_API_KEY)
            await notifier.send_dispatch_summary(user_email=user_row.email, signal_symbol=parsed.symbol or "UNKNOWN", results=actionable)
        if ((prefs.telegram_on_failure and has_f) or (prefs.telegram_on_success and has_s)) and prefs.telegram_bot_chat_id:
            from src.adapters.telegram.notifier import TelegramNotifier
            tg = TelegramNotifier(bot_token=settings.TELEGRAM_BOT_TOKEN)
            await tg.send_dispatch_summary(chat_id=prefs.telegram_bot_chat_id, signal_symbol=parsed.symbol or "UNKNOWN", results=actionable)
    except Exception as exc:
        logger.error("Notification failed (non-blocking): %s", exc)
        sentry_sdk.capture_exception(exc)


async def _check_first_signal_milestone(db, settings, user_id, parsed, results):
    if not any(r.status == "success" for r in results) or not settings.RESEND_API_KEY:
        return
    try:
        prior = (await db.execute(select(func.count()).where(SignalLogModel.user_id == user_id, SignalLogModel.status == "success"))).scalar_one()
        current = sum(1 for r in results if r.status == "success")
        if prior <= current:
            from src.adapters.db.models import UserModel
            from src.adapters.email import ResendNotifier
            email = (await db.execute(select(UserModel.email).where(UserModel.id == user_id))).scalar_one_or_none()
            if email:
                n = ResendNotifier(api_key=settings.RESEND_API_KEY)
                await n.send_first_signal_routed(user_email=email, symbol=parsed.symbol or "UNKNOWN", frontend_url=settings.FRONTEND_URL)
    except Exception as exc:
        logger.error("First-signal milestone email failed: %s", exc)
        sentry_sdk.capture_exception(exc)


async def _maybe_marketplace_fanout(
    *,
    raw_signal: RawSignal,
    parsed: ParsedSignal,
    dispatcher: WebhookDispatcher,
    db: AsyncSession,
    dispatch_queue=None,
) -> None:
    """Trigger marketplace fan-out if the channel is an active marketplace provider.

    Checks channel_id against marketplace_providers directly (no is_admin check).
    In two-stage mode (dispatch_queue provided), enqueues individual DispatchJobs
    per subscriber via QStash. Otherwise, dispatches directly.
    """
    if os.getenv("MARKETPLACE_ENABLED", "false").lower() not in ("true", "1", "yes"):
        return
    try:
        mp_result = await db.execute(
            select(MarketplaceProviderModel.id).where(
                MarketplaceProviderModel.telegram_channel_id == raw_signal.channel_id,
                MarketplaceProviderModel.is_active.is_(True),
            ).limit(1)
        )
        if mp_result.scalar_one_or_none() is None:
            return

        if dispatch_queue is not None:
            # Two-stage: enqueue per-subscriber dispatch jobs via QStash
            subs_result = await db.execute(
                select(MarketplaceSubscriptionModel.routing_rule_id, MarketplaceSubscriptionModel.user_id).where(
                    MarketplaceSubscriptionModel.provider_id == (
                        select(MarketplaceProviderModel.id).where(
                            MarketplaceProviderModel.telegram_channel_id == raw_signal.channel_id,
                            MarketplaceProviderModel.is_active.is_(True),
                        ).limit(1).correlate(None).scalar_subquery()
                    ),
                    MarketplaceSubscriptionModel.is_active.is_(True),
                    MarketplaceSubscriptionModel.routing_rule_id.isnot(None),
                )
            )
            sub_rows = subs_result.all()
            for rule_id, user_id in sub_rows:
                meta = RawSignalMeta(
                    user_id=user_id,
                    channel_id=raw_signal.channel_id,
                    message_id=raw_signal.message_id,
                    reply_to_msg_id=raw_signal.reply_to_msg_id,
                    raw_message=raw_signal.raw_message,
                    timestamp=raw_signal.timestamp,
                )
                job = DispatchJob(
                    parsed_signal=parsed,
                    routing_rule_id=rule_id,
                    raw_signal_meta=meta,
                    source_type="marketplace",
                )
                try:
                    await dispatch_queue.enqueue_dispatch_job(job)
                except Exception as exc:
                    sentry_sdk.capture_exception(exc)
                    logger.error("Marketplace enqueue failed for rule %s: %s", rule_id, exc)
            if sub_rows:
                logger.info("Marketplace fan-out (queued) for channel %s: %d jobs", raw_signal.channel_id, len(sub_rows))
        else:
            # Direct dispatch path
            from src.core.marketplace import marketplace_fanout
            fanout_results = await marketplace_fanout(
                parsed_signal=parsed,
                channel_id=raw_signal.channel_id,
                raw_message=raw_signal.raw_message,
                message_id=raw_signal.message_id,
                reply_to_msg_id=raw_signal.reply_to_msg_id,
                dispatcher=dispatcher,
                db_session=db,
            )
            logger.info("Marketplace fan-out for channel %s: %d dispatches", raw_signal.channel_id, len(fanout_results))
    except Exception as exc:
        logger.error("Marketplace fan-out failed for channel %s: %s", raw_signal.channel_id, exc)
        sentry_sdk.capture_exception(exc)


@workflow_router.post("/api/workflow/process-signal", response_model=list[DispatchResult], dependencies=[Depends(verify_qstash_signature)])
async def process_signal(raw_signal: RawSignal, request: Request, db: Annotated[AsyncSession, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)], dispatcher: Annotated[WebhookDispatcher, Depends(get_dispatcher)]) -> list[DispatchResult]:
    if raw_signal.message_id:
        locked = await _acquire_message_lock(db, raw_signal)
        if not locked:
            return []
        existing = await db.execute(select(SignalLogModel.id).where(SignalLogModel.channel_id == raw_signal.channel_id, SignalLogModel.message_id == raw_signal.message_id, SignalLogModel.user_id == raw_signal.user_id, SignalLogModel.status.in_(["success", "ignored"])).limit(1))
        if existing.scalar_one_or_none() is not None:
            return []
    result = await db.execute(select(RoutingRuleModel).where(RoutingRuleModel.source_channel_id == raw_signal.channel_id, RoutingRuleModel.user_id == raw_signal.user_id, RoutingRuleModel.is_active.is_(True)))
    rules = result.scalars().all()
    if not rules:
        return []
    original_message_text = None
    if raw_signal.reply_to_msg_id:
        row = await db.execute(select(SignalLogModel.raw_message).where(SignalLogModel.channel_id == raw_signal.channel_id, SignalLogModel.message_id == raw_signal.reply_to_msg_id).limit(1))
        original_message_text = row.scalar_one_or_none()
    custom_instructions = next((r.custom_ai_instructions for r in rules if r.custom_ai_instructions), None)
    parsed: ParsedSignal
    with tracer.start_as_current_span("signal.parse") as span:
        span.set_attribute("signal.channel_id", raw_signal.channel_id)
        span.set_attribute("signal.message_id", raw_signal.message_id or 0)
        try:
            from src.adapters.openai import OpenAISignalParser
            sys_prompt, model_name, temp = await _get_parser_config(request, db)
            parser = OpenAISignalParser(api_key=settings.OPENAI_API_KEY, model=model_name, temperature=temp)
            parsed = await parser.parse(raw_signal, original_context=original_message_text, custom_instructions=custom_instructions, system_prompt=sys_prompt)
            span.set_attribute("signal.is_valid", parsed.is_valid_signal)
        except Exception as exc:
            span.record_exception(exc)
            logger.error("Signal parsing failed: %s", exc)
            db.add(SignalLogModel(user_id=raw_signal.user_id, message_id=raw_signal.message_id, channel_id=raw_signal.channel_id, reply_to_msg_id=raw_signal.reply_to_msg_id, raw_message=raw_signal.raw_message, status="failed", error_message=f"Parse error: {exc}", source_type="telegram"))
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Failed to parse signal: {exc}") from exc
    if not parsed.is_valid_signal:
        db.add(SignalLogModel(user_id=raw_signal.user_id, message_id=raw_signal.message_id, channel_id=raw_signal.channel_id, reply_to_msg_id=raw_signal.reply_to_msg_id, raw_message=raw_signal.raw_message, parsed_data=parsed.model_dump(), status="ignored", error_message=parsed.ignore_reason, source_type="telegram"))
        return [DispatchResult(routing_rule_id=None, status="ignored", error_message=parsed.ignore_reason)]
    if settings.TWO_STAGE_DISPATCH:
        dispatch_queue = request.app.state.dispatch_queue
        meta = RawSignalMeta(user_id=raw_signal.user_id, channel_id=raw_signal.channel_id, message_id=raw_signal.message_id, reply_to_msg_id=raw_signal.reply_to_msg_id, raw_message=raw_signal.raw_message, timestamp=raw_signal.timestamp)
        queued_results: list[DispatchResult] = []
        for rule_row in rules:
            job = DispatchJob(parsed_signal=parsed, routing_rule_id=rule_row.id, raw_signal_meta=meta)
            try:
                await dispatch_queue.enqueue_dispatch_job(job)
                queued_results.append(DispatchResult(routing_rule_id=rule_row.id, status="queued"))
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                queued_results.append(DispatchResult(routing_rule_id=rule_row.id, status="failed", error_message=f"Enqueue failed: {exc}"))
        # Marketplace fan-out (two-stage path) — enqueue subscriber dispatches via QStash
        await _maybe_marketplace_fanout(raw_signal=raw_signal, parsed=parsed, dispatcher=dispatcher, db=db, dispatch_queue=dispatch_queue)
        return queued_results
    outcomes = await asyncio.gather(*[_process_single_rule(rule_row, raw_signal, parsed, dispatcher) for rule_row in rules], return_exceptions=True)
    results: list[DispatchResult] = []
    for i, outcome in enumerate(outcomes):
        if isinstance(outcome, Exception):
            sentry_sdk.capture_exception(outcome)
            dr = DispatchResult(routing_rule_id=rules[i].id, status="failed", error_message=str(outcome))
            results.append(dr)
            db.add(SignalLogModel(user_id=raw_signal.user_id, message_id=raw_signal.message_id, channel_id=raw_signal.channel_id, reply_to_msg_id=raw_signal.reply_to_msg_id, routing_rule_id=rules[i].id, raw_message=raw_signal.raw_message, parsed_data=parsed.model_dump(), status="failed", error_message=str(outcome), source_type="telegram"))
        else:
            dispatch_result, log_kwargs = outcome
            results.append(dispatch_result)
            db.add(SignalLogModel(**log_kwargs))
    try:
        cache = request.app.state.cache
        await cache.delete(f"log_stats:{raw_signal.user_id}")
    except Exception:
        pass

    # Marketplace fan-out — dispatch to all marketplace subscribers of this channel
    await _maybe_marketplace_fanout(raw_signal=raw_signal, parsed=parsed, dispatcher=dispatcher, db=db)
    await _send_dispatch_notifications(db, settings, raw_signal.user_id, parsed, results)
    await _check_first_signal_milestone(db, settings, raw_signal.user_id, parsed, results)
    return results


@workflow_router.post("/api/workflow/dispatch-signal", response_model=DispatchResult, dependencies=[Depends(verify_qstash_signature)])
async def dispatch_signal(job: DispatchJob, request: Request, db: Annotated[AsyncSession, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)], dispatcher: Annotated[WebhookDispatcher, Depends(get_dispatcher)]) -> DispatchResult:
    meta = job.raw_signal_meta
    # Advisory lock to prevent duplicate dispatch under QStash retry concurrency
    if meta.message_id:
        lock_key = _dispatch_lock_key(meta.channel_id, meta.message_id, job.routing_rule_id)
        try:
            lock_result = await db.execute(text("SELECT pg_try_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
            if not bool(lock_result.scalar_one()):
                return DispatchResult(routing_rule_id=job.routing_rule_id, status="ignored", error_message="Concurrent dispatch in progress (advisory lock)")
        except Exception:
            pass  # Non-PostgreSQL or lock unavailable — fall through to dedup check
    existing = await db.execute(select(SignalLogModel.id).where(SignalLogModel.channel_id == meta.channel_id, SignalLogModel.message_id == meta.message_id, SignalLogModel.routing_rule_id == job.routing_rule_id, SignalLogModel.status.in_(["success", "ignored"])).limit(1))
    if existing.scalar_one_or_none() is not None:
        return DispatchResult(routing_rule_id=job.routing_rule_id, status="ignored", error_message="Already processed (Stage 2 dedup)")
    rule_row = (await db.execute(select(RoutingRuleModel).where(RoutingRuleModel.id == job.routing_rule_id))).scalar_one_or_none()
    if rule_row is None or not rule_row.is_active:
        return DispatchResult(routing_rule_id=job.routing_rule_id, status="ignored", error_message="Rule no longer active")
    raw_signal = RawSignal(user_id=meta.user_id, channel_id=meta.channel_id, raw_message=meta.raw_message, message_id=meta.message_id, reply_to_msg_id=meta.reply_to_msg_id, timestamp=meta.timestamp)
    dispatch_result, log_kwargs = await _process_single_rule(rule_row, raw_signal, job.parsed_signal, dispatcher)
    log_kwargs["source_type"] = job.source_type
    db.add(SignalLogModel(**log_kwargs))
    try:
        cache = request.app.state.cache
        await cache.delete(f"log_stats:{meta.user_id}")
    except Exception:
        pass
    await _send_dispatch_notifications(db, settings, meta.user_id, job.parsed_signal, [dispatch_result])
    await _check_first_signal_milestone(db, settings, meta.user_id, job.parsed_signal, [dispatch_result])
    return dispatch_result
