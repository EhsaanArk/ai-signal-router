"""Core marketplace logic — fan-out, stats computation, subscribe/unsubscribe.

This module is called by the API routes and (eventually) the workflow pipeline.
It depends on SQLAlchemy models and the webhook dispatcher, but keeps business
logic centralised rather than scattered across route handlers.
"""

from __future__ import annotations

import asyncio
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
    UserModel,
)
from src.core.models import ParsedSignal, RawSignal, SubscriptionTier

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

    from src.api.workflow import _process_single_rule

    semaphore = asyncio.Semaphore(10)  # max 10 concurrent dispatches

    async def _dispatch_one(sub):
        """Dispatch to one subscriber. Returns (result_dict, log_kwargs) or None."""
        rule_row = rule_rows.get(sub.routing_rule_id)
        if rule_row is None:
            return None

        sub_raw = RawSignal(
            user_id=sub.user_id,
            channel_id=channel_id,
            raw_message=raw_message,
            message_id=message_id,
            reply_to_msg_id=reply_to_msg_id,
        )

        try:
            async with semaphore:
                dispatch_result, log_kwargs = await _process_single_rule(
                    rule_row, sub_raw, parsed_signal, dispatcher,
                )
            log_kwargs["source_type"] = "marketplace"
            result_dict = {
                "subscription_id": str(sub.id),
                "user_id": str(sub.user_id),
                "status": dispatch_result.status,
                "error": dispatch_result.error_message,
            }
            return result_dict, log_kwargs

        except Exception as exc:
            logger.error(
                "Marketplace fanout failed for subscription %s (user %s): %s",
                sub.id, sub.user_id, exc,
            )
            fail_log = dict(
                user_id=sub.user_id,
                routing_rule_id=rule_row.id,
                message_id=message_id,
                channel_id=channel_id,
                reply_to_msg_id=reply_to_msg_id,
                raw_message=raw_message,
                parsed_data=parsed_signal.model_dump(),
                status="failed",
                error_message=str(exc),
                source_type="marketplace",
            )
            result_dict = {
                "subscription_id": str(sub.id),
                "user_id": str(sub.user_id),
                "status": "failed",
                "error": str(exc),
            }
            return result_dict, fail_log

    # Dispatch concurrently, then add all signal logs to session sequentially
    gather_results = await asyncio.gather(*[_dispatch_one(sub) for sub in subscriptions])

    dispatch_results: list[dict] = []
    for item in gather_results:
        if item is None:
            continue
        result_dict, log_kwargs = item
        dispatch_results.append(result_dict)
        db_session.add(SignalLogModel(**log_kwargs))

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

    # Count DISTINCT provider signals by using source_type='telegram' from admin
    # listeners for this channel. This counts original signals (one per parse),
    # not per-subscriber fan-out copies (source_type='marketplace').
    # Uses COUNT(DISTINCT message_id) to avoid counting the same signal multiple
    # times if multiple admin routing rules exist for the channel.
    total_signals = await db_session.execute(
        select(func.count(func.distinct(SignalLogModel.message_id))).select_from(SignalLogModel).where(
            SignalLogModel.channel_id == channel_id,
            SignalLogModel.source_type == "telegram",
            SignalLogModel.status.in_(["success", "failed"]),
        )
    )
    signal_count = total_signals.scalar_one()

    # Count successful distinct signals
    success_count_result = await db_session.execute(
        select(func.count(func.distinct(SignalLogModel.message_id))).select_from(SignalLogModel).where(
            SignalLogModel.channel_id == channel_id,
            SignalLogModel.source_type == "telegram",
            SignalLogModel.status == "success",
        )
    )
    success_count = success_count_result.scalar_one()

    # Win rate (success / total, excluding ignored)
    win_rate = (success_count / signal_count * 100.0) if signal_count > 0 else None

    # Track record: days between first and latest signal (from original source)
    date_range = await db_session.execute(
        select(
            func.min(SignalLogModel.processed_at),
            func.max(SignalLogModel.processed_at),
        ).where(
            SignalLogModel.channel_id == channel_id,
            SignalLogModel.source_type == "telegram",
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
            is_verified=(track_record_days >= 30 and signal_count >= 20),
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


async def compute_all_provider_stats(db_session: AsyncSession) -> int:
    """Batch-compute stats for all active marketplace providers.

    Uses aggregate queries across all providers in 3 queries total
    (signal counts, date ranges, subscriber counts) instead of
    6 queries per provider. Returns the number of providers refreshed.
    """
    from sqlalchemy import case, literal_column

    # Get all active providers
    result = await db_session.execute(
        select(
            MarketplaceProviderModel.id,
            MarketplaceProviderModel.telegram_channel_id,
        ).where(MarketplaceProviderModel.is_active.is_(True))
    )
    providers = result.all()
    if not providers:
        return 0

    channel_ids = [p.telegram_channel_id for p in providers]

    # Query 1: Signal counts + success counts per channel (batched)
    signal_stats = await db_session.execute(
        select(
            SignalLogModel.channel_id,
            func.count(func.distinct(SignalLogModel.message_id)).label("total"),
            func.count(func.distinct(
                case(
                    (SignalLogModel.status == "success", SignalLogModel.message_id),
                    else_=literal_column("NULL"),
                )
            )).label("success"),
        )
        .where(
            SignalLogModel.channel_id.in_(channel_ids),
            SignalLogModel.source_type == "telegram",
            SignalLogModel.status.in_(["success", "failed"]),
        )
        .group_by(SignalLogModel.channel_id)
    )
    counts_by_channel: dict[str, tuple[int, int]] = {}
    for row in signal_stats.all():
        counts_by_channel[row.channel_id] = (row.total, row.success)

    # Query 2: Date ranges per channel (batched)
    date_stats = await db_session.execute(
        select(
            SignalLogModel.channel_id,
            func.min(SignalLogModel.processed_at),
            func.max(SignalLogModel.processed_at),
        )
        .where(
            SignalLogModel.channel_id.in_(channel_ids),
            SignalLogModel.source_type == "telegram",
        )
        .group_by(SignalLogModel.channel_id)
    )
    dates_by_channel: dict[str, tuple] = {}
    for row in date_stats.all():
        dates_by_channel[row.channel_id] = (row[1], row[2])

    # Query 3: Subscriber counts per provider (batched)
    sub_stats = await db_session.execute(
        select(
            MarketplaceSubscriptionModel.provider_id,
            func.count().label("count"),
        )
        .where(MarketplaceSubscriptionModel.is_active.is_(True))
        .group_by(MarketplaceSubscriptionModel.provider_id)
    )
    subs_by_provider: dict[UUID, int] = {}
    for row in sub_stats.all():
        subs_by_provider[row.provider_id] = row.count

    # Update all providers in one pass
    now = datetime.now(timezone.utc)
    for provider_row in providers:
        pid = provider_row.id
        cid = provider_row.telegram_channel_id
        total, success = counts_by_channel.get(cid, (0, 0))
        win_rate = (success / total * 100.0) if total > 0 else None
        first, last = dates_by_channel.get(cid, (None, None))
        track_days = (last - first).days if first and last else 0
        sub_count = subs_by_provider.get(pid, 0)

        await db_session.execute(
            update(MarketplaceProviderModel)
            .where(MarketplaceProviderModel.id == pid)
            .values(
                win_rate=win_rate,
                signal_count=total,
                track_record_days=track_days,
                subscriber_count=sub_count,
                is_verified=(track_days >= 30 and total >= 20),
                stats_last_computed_at=now,
            )
        )

    return len(providers)


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

    # 3. Enforce tier limit — marketplace subscriptions count toward route limit
    user_row = (await db_session.execute(
        select(UserModel.subscription_tier).where(UserModel.id == user_id)
    )).scalar_one_or_none()
    user_tier = SubscriptionTier(user_row) if user_row else SubscriptionTier.free
    active_rule_count = (await db_session.execute(
        select(func.count()).select_from(RoutingRuleModel).where(
            RoutingRuleModel.user_id == user_id,
            RoutingRuleModel.is_active.is_(True),
            RoutingRuleModel.is_marketplace_template.is_(False),
        )
    )).scalar_one()
    if active_rule_count >= user_tier.max_destinations:
        raise ValueError(
            f"Your {user_tier.value} plan allows up to "
            f"{user_tier.max_destinations} route(s). "
            "Please upgrade to add more."
        )

    # 4. Load the user's existing routing rule (as a webhook destination template)
    result = await db_session.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == webhook_destination_id,
            RoutingRuleModel.user_id == user_id,
        )
    )
    destination_rule = result.scalar_one_or_none()
    if destination_rule is None:
        raise ValueError("Webhook destination not found or does not belong to user")

    # 5. Create a new routing rule for the marketplace subscription
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

    # 6. Create or reactivate subscription
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

    # 7. Create consent log (always — fresh consent required on every subscribe)
    consent = MarketplaceConsentLogModel(
        user_id=user_id,
        provider_id=provider_id,
        disclaimer_version=DISCLAIMER_VERSION,
    )
    db_session.add(consent)

    # 8. Update subscriber count (only for new subs — resubscribes already
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
