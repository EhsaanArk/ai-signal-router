"""Core marketplace logic — fan-out, stats computation, subscribe/unsubscribe.

This module is called by the API routes and (eventually) the workflow pipeline.
It depends on SQLAlchemy models and the webhook dispatcher, but keeps business
logic centralised rather than scattered across route handlers.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import (
    MarketplaceConsentLogModel,
    MarketplaceProviderModel,
    MarketplaceSubscriptionModel,
    RoutingRuleModel,
    SignalLogModel,
)
from src.core.models import DispatchResult, ParsedSignal, RoutingRule, normalize_enabled_actions

logger = logging.getLogger(__name__)

DISCLAIMER_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Fan-out: dispatch a parsed signal to all marketplace subscribers
# ---------------------------------------------------------------------------


async def marketplace_fanout(
    parsed_signal: ParsedSignal,
    channel_id: str,
    raw_message: str,
    message_id: int | None,
    reply_to_msg_id: int | None,
    dispatcher,  # WebhookDispatcher instance
    db_session: AsyncSession,
) -> list[dict]:
    """Fan out a parsed signal to all active marketplace subscribers of a channel.

    Returns a list of dicts with dispatch results per subscriber.
    Each subscriber's dispatch is isolated — one failure does not block others.
    """
    if os.getenv("MARKETPLACE_ENABLED", "false").lower() not in ("true", "1", "yes"):
        return []

    # Find the marketplace provider for this channel
    result = await db_session.execute(
        select(MarketplaceProviderModel).where(
            MarketplaceProviderModel.telegram_channel_id == channel_id,
            MarketplaceProviderModel.is_active.is_(True),
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        return []

    # Find all active subscriptions with their routing rules
    result = await db_session.execute(
        select(MarketplaceSubscriptionModel)
        .where(
            MarketplaceSubscriptionModel.provider_id == provider.id,
            MarketplaceSubscriptionModel.is_active.is_(True),
            MarketplaceSubscriptionModel.routing_rule_id.isnot(None),
        )
    )
    subscriptions = result.scalars().all()
    if not subscriptions:
        return []

    # Load all routing rules for these subscriptions
    rule_ids = [s.routing_rule_id for s in subscriptions if s.routing_rule_id]
    if not rule_ids:
        return []

    result = await db_session.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id.in_(rule_ids),
            RoutingRuleModel.is_active.is_(True),
        )
    )
    rule_rows = {r.id: r for r in result.scalars().all()}

    dispatch_results: list[dict] = []

    for sub in subscriptions:
        rule_row = rule_rows.get(sub.routing_rule_id)
        if rule_row is None:
            continue

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
            enabled_actions=normalize_enabled_actions(rule_row.enabled_actions),
            keyword_blacklist=rule_row.keyword_blacklist or [],
        )

        try:
            dispatch_result: DispatchResult = await dispatcher.dispatch(
                parsed_signal, rule
            )

            # Build the payload dict for logging (if dispatch returned it)
            payload_dict = dispatch_result.webhook_payload

            # Log each dispatch as a signal_log with source_type='marketplace'
            log_entry = SignalLogModel(
                user_id=sub.user_id,
                routing_rule_id=rule.id,
                message_id=message_id,
                channel_id=channel_id,
                reply_to_msg_id=reply_to_msg_id,
                raw_message=raw_message,
                parsed_data=parsed_signal.model_dump(),
                webhook_payload=payload_dict,
                status=dispatch_result.status,
                error_message=dispatch_result.error_message,
                source_type="marketplace",
            )
            db_session.add(log_entry)

            dispatch_results.append({
                "subscription_id": str(sub.id),
                "user_id": str(sub.user_id),
                "status": dispatch_result.status,
                "error": dispatch_result.error_message,
            })

        except Exception as exc:
            logger.error(
                "Marketplace fanout failed for subscription %s (user %s): %s",
                sub.id, sub.user_id, exc,
            )
            # Log the failure
            log_entry = SignalLogModel(
                user_id=sub.user_id,
                routing_rule_id=rule.id if rule_row else None,
                message_id=message_id,
                channel_id=channel_id,
                reply_to_msg_id=reply_to_msg_id,
                raw_message=raw_message,
                parsed_data=parsed_signal.model_dump(),
                status="failed",
                error_message=str(exc),
                source_type="marketplace",
            )
            db_session.add(log_entry)

            dispatch_results.append({
                "subscription_id": str(sub.id),
                "user_id": str(sub.user_id),
                "status": "failed",
                "error": str(exc),
            })

    return dispatch_results


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------


async def compute_provider_stats(
    provider_id: UUID,
    db_session: AsyncSession,
) -> dict:
    """Compute performance stats from signal_logs for a marketplace provider.

    Calculates win_rate, total_pnl_pips, max_drawdown_pips, signal_count,
    and track_record_days.  Updates the provider's cached stat columns.
    """
    # Get provider
    result = await db_session.execute(
        select(MarketplaceProviderModel).where(
            MarketplaceProviderModel.id == provider_id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise ValueError(f"Provider {provider_id} not found")

    channel_id = provider.telegram_channel_id

    # Count total signals dispatched for this channel via marketplace
    total_signals = await db_session.execute(
        select(func.count()).select_from(SignalLogModel).where(
            SignalLogModel.channel_id == channel_id,
            SignalLogModel.source_type == "marketplace",
            SignalLogModel.status.in_(["success", "failed"]),
        )
    )
    signal_count = total_signals.scalar_one()

    # Count successful signals
    success_count_result = await db_session.execute(
        select(func.count()).select_from(SignalLogModel).where(
            SignalLogModel.channel_id == channel_id,
            SignalLogModel.source_type == "marketplace",
            SignalLogModel.status == "success",
        )
    )
    success_count = success_count_result.scalar_one()

    # Win rate (success / total, excluding ignored)
    win_rate = (success_count / signal_count * 100.0) if signal_count > 0 else None

    # Track record: days between first and latest signal
    date_range = await db_session.execute(
        select(
            func.min(SignalLogModel.processed_at),
            func.max(SignalLogModel.processed_at),
        ).where(
            SignalLogModel.channel_id == channel_id,
            SignalLogModel.source_type == "marketplace",
        )
    )
    first_signal, last_signal = date_range.one()
    if first_signal and last_signal:
        track_record_days = (last_signal - first_signal).days
    else:
        track_record_days = 0

    # Count active subscribers
    sub_count_result = await db_session.execute(
        select(func.count()).select_from(MarketplaceSubscriptionModel).where(
            MarketplaceSubscriptionModel.provider_id == provider_id,
            MarketplaceSubscriptionModel.is_active.is_(True),
        )
    )
    subscriber_count = sub_count_result.scalar_one()

    # Update provider stats cache
    now = datetime.now(timezone.utc)
    await db_session.execute(
        update(MarketplaceProviderModel)
        .where(MarketplaceProviderModel.id == provider_id)
        .values(
            win_rate=win_rate,
            signal_count=signal_count,
            track_record_days=track_record_days,
            subscriber_count=subscriber_count,
            stats_last_computed_at=now,
            # total_pnl_pips and max_drawdown_pips require closed-trade PnL data
            # which is not yet tracked — leave as-is for V1
        )
    )

    stats = {
        "provider_id": str(provider_id),
        "win_rate": win_rate,
        "signal_count": signal_count,
        "track_record_days": track_record_days,
        "subscriber_count": subscriber_count,
        "total_pnl_pips": provider.total_pnl_pips,
        "max_drawdown_pips": provider.max_drawdown_pips,
        "stats_last_computed_at": now.isoformat(),
    }
    return stats


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe
# ---------------------------------------------------------------------------


async def subscribe_to_provider(
    user_id: UUID,
    provider_id: UUID,
    webhook_destination_id: UUID,
    db_session: AsyncSession,
) -> dict:
    """Subscribe a user to a marketplace provider.

    Creates a routing rule linking the provider's channel to the user's
    webhook destination, then creates the subscription and consent log.

    Parameters
    ----------
    user_id : UUID
        The subscribing user.
    provider_id : UUID
        The marketplace provider to subscribe to.
    webhook_destination_id : UUID
        An existing routing rule ID owned by the user, used as a template
        for the webhook URL and destination settings.
    db_session : AsyncSession
        Active database session.
    """
    # 1. Check provider exists and is active
    result = await db_session.execute(
        select(MarketplaceProviderModel).where(
            MarketplaceProviderModel.id == provider_id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise ValueError("Provider not found")
    if not provider.is_active:
        raise ValueError("Provider is not active")

    # 2. Check for existing subscription (active OR inactive for re-subscribe)
    existing_result = await db_session.execute(
        select(MarketplaceSubscriptionModel).where(
            MarketplaceSubscriptionModel.user_id == user_id,
            MarketplaceSubscriptionModel.provider_id == provider_id,
        )
    )
    existing_sub = existing_result.scalar_one_or_none()
    if existing_sub is not None and existing_sub.is_active:
        raise ValueError("Already subscribed to this provider")

    # 3. Load the user's existing routing rule (as a webhook destination template)
    result = await db_session.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == webhook_destination_id,
            RoutingRuleModel.user_id == user_id,
        )
    )
    destination_rule = result.scalar_one_or_none()
    if destination_rule is None:
        raise ValueError("Webhook destination not found or does not belong to user")

    # 4. Create a new routing rule for the marketplace subscription
    marketplace_rule = RoutingRuleModel(
        user_id=user_id,
        source_channel_id=provider.telegram_channel_id,
        source_channel_name=provider.name,
        destination_webhook_url=destination_rule.destination_webhook_url,
        payload_version=destination_rule.payload_version,
        symbol_mappings=destination_rule.symbol_mappings or {},
        risk_overrides=destination_rule.risk_overrides or {},
        webhook_body_template=destination_rule.webhook_body_template,
        rule_name=f"Marketplace: {provider.name}",
        destination_label=destination_rule.destination_label,
        destination_type=destination_rule.destination_type,
        enabled_actions=destination_rule.enabled_actions,
        keyword_blacklist=destination_rule.keyword_blacklist or [],
        is_active=True,
    )
    db_session.add(marketplace_rule)
    await db_session.flush()  # get the rule's ID

    # 5. Create or reactivate subscription
    is_resubscribe = existing_sub is not None
    if is_resubscribe:
        # Re-subscribe: deactivate old routing rule, then reactivate subscription
        old_rule_id = existing_sub.routing_rule_id
        if old_rule_id:
            await db_session.execute(
                update(RoutingRuleModel)
                .where(RoutingRuleModel.id == old_rule_id)
                .values(is_active=False)
            )
        existing_sub.is_active = True
        existing_sub.routing_rule_id = marketplace_rule.id
        existing_sub.updated_at = datetime.now(timezone.utc)
        subscription = existing_sub
    else:
        # First-time subscribe: create new row
        subscription = MarketplaceSubscriptionModel(
            user_id=user_id,
            provider_id=provider_id,
            routing_rule_id=marketplace_rule.id,
            is_active=True,
        )
        db_session.add(subscription)

    # 6. Create consent log (always — fresh consent required on every subscribe)
    consent = MarketplaceConsentLogModel(
        user_id=user_id,
        provider_id=provider_id,
        disclaimer_version=DISCLAIMER_VERSION,
    )
    db_session.add(consent)

    # 7. Update subscriber count (only for new subs — resubscribes already
    #    had the count decremented on unsubscribe, so increment is correct)
    await db_session.execute(
        update(MarketplaceProviderModel)
        .where(MarketplaceProviderModel.id == provider_id)
        .values(subscriber_count=MarketplaceProviderModel.subscriber_count + 1)
    )

    await db_session.flush()

    return {
        "subscription_id": str(subscription.id),
        "provider_id": str(provider_id),
        "provider_name": provider.name,
        "routing_rule_id": str(marketplace_rule.id),
        "is_active": True,
    }


async def unsubscribe_from_provider(
    user_id: UUID,
    provider_id: UUID,
    db_session: AsyncSession,
) -> None:
    """Unsubscribe a user from a marketplace provider.

    Sets the subscription and its associated routing rule to inactive.
    """
    result = await db_session.execute(
        select(MarketplaceSubscriptionModel).where(
            MarketplaceSubscriptionModel.user_id == user_id,
            MarketplaceSubscriptionModel.provider_id == provider_id,
            MarketplaceSubscriptionModel.is_active.is_(True),
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise ValueError("No active subscription found for this provider")

    # Deactivate subscription
    subscription.is_active = False

    # Deactivate the associated routing rule
    if subscription.routing_rule_id:
        await db_session.execute(
            update(RoutingRuleModel)
            .where(RoutingRuleModel.id == subscription.routing_rule_id)
            .values(is_active=False)
        )

    # Decrement subscriber count (floor at 0)
    await db_session.execute(
        update(MarketplaceProviderModel)
        .where(
            MarketplaceProviderModel.id == provider_id,
            MarketplaceProviderModel.subscriber_count > 0,
        )
        .values(subscriber_count=MarketplaceProviderModel.subscriber_count - 1)
    )
