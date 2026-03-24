"""Marketplace API routes — provider discovery, subscribe/unsubscribe, admin CRUD."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import (
    MarketplaceProviderModel,
    MarketplaceSubscriptionModel,
    RoutingRuleModel,
)
from src.api.deps import (
    get_admin_user,
    get_current_user,
    get_db,
    limiter,
)
from src.core.marketplace import (
    compute_provider_stats,
    subscribe_to_provider,
    unsubscribe_from_provider,
)
from src.core.models import User

logger = logging.getLogger(__name__)

marketplace_router = APIRouter(tags=["marketplace"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ProviderResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    asset_class: str
    is_active: bool
    win_rate: float | None
    total_pnl_pips: float | None
    max_drawdown_pips: float | None
    signal_count: int
    subscriber_count: int
    track_record_days: int
    stats_last_computed_at: str | None
    created_at: str


class ProviderListResponse(BaseModel):
    total: int
    items: list[ProviderResponse]


class ProviderStatsResponse(BaseModel):
    provider_id: str
    win_rate: float | None
    signal_count: int
    track_record_days: int
    subscriber_count: int
    total_pnl_pips: float | None
    max_drawdown_pips: float | None
    stats_last_computed_at: str | None


class SubscribeRequest(BaseModel):
    webhook_destination_id: UUID = Field(
        ..., description="ID of an existing routing rule to use as webhook destination template"
    )
    consent: bool = Field(
        ..., description="User must explicitly consent to the risk disclaimer"
    )


class SubscriptionResponse(BaseModel):
    subscription_id: str
    provider_id: str
    provider_name: str
    routing_rule_id: str
    is_active: bool


class MySubscriptionItem(BaseModel):
    subscription_id: UUID
    provider_id: UUID
    provider_name: str
    provider_asset_class: str
    routing_rule_id: UUID | None
    is_active: bool
    created_at: str


class CreateProviderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    asset_class: str = Field(..., pattern="^(forex|crypto|both)$")
    telegram_channel_id: str = Field(..., min_length=1, max_length=255)


class UpdateProviderRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    asset_class: str | None = Field(None, pattern="^(forex|crypto|both)$")
    telegram_channel_id: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class AdminProviderResponse(ProviderResponse):
    telegram_channel_id: str


class MarketplaceStatsResponse(BaseModel):
    total_providers: int
    active_providers: int
    total_subscriptions: int
    active_subscriptions: int
    total_signals_routed: int


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _provider_to_response(p: MarketplaceProviderModel) -> ProviderResponse:
    return ProviderResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        asset_class=p.asset_class,
        is_active=p.is_active,
        win_rate=p.win_rate,
        total_pnl_pips=p.total_pnl_pips,
        max_drawdown_pips=p.max_drawdown_pips,
        signal_count=p.signal_count,
        subscriber_count=p.subscriber_count,
        track_record_days=p.track_record_days,
        stats_last_computed_at=(
            p.stats_last_computed_at.isoformat() if p.stats_last_computed_at else None
        ),
        created_at=p.created_at.isoformat() if p.created_at else "",
    )


def _provider_to_admin_response(p: MarketplaceProviderModel) -> AdminProviderResponse:
    return AdminProviderResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        asset_class=p.asset_class,
        telegram_channel_id=p.telegram_channel_id,
        is_active=p.is_active,
        win_rate=p.win_rate,
        total_pnl_pips=p.total_pnl_pips,
        max_drawdown_pips=p.max_drawdown_pips,
        signal_count=p.signal_count,
        subscriber_count=p.subscriber_count,
        track_record_days=p.track_record_days,
        stats_last_computed_at=(
            p.stats_last_computed_at.isoformat() if p.stats_last_computed_at else None
        ),
        created_at=p.created_at.isoformat() if p.created_at else "",
    )


# ===========================================================================
# Public endpoints (rate-limited, no auth)
# ===========================================================================


@marketplace_router.get("/api/marketplace/providers")
@limiter.limit("60/minute")
async def list_providers(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    asset_class: str | None = Query(default=None, pattern="^(forex|crypto|both)$"),
    sort: str | None = Query(default=None, pattern="^(win_rate|pnl|signals|subscribers)$"),
) -> ProviderListResponse:
    """List active marketplace providers with cached stats."""
    query = select(MarketplaceProviderModel).where(
        MarketplaceProviderModel.is_active.is_(True),
    )
    if asset_class:
        query = query.where(
            MarketplaceProviderModel.asset_class.in_([asset_class, "both"])
        )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Paginated results
    sort_map = {
        "win_rate": MarketplaceProviderModel.win_rate.desc().nulls_last(),
        "pnl": MarketplaceProviderModel.total_pnl_pips.desc().nulls_last(),
        "signals": MarketplaceProviderModel.signal_count.desc(),
        "subscribers": MarketplaceProviderModel.subscriber_count.desc(),
    }
    order_clause = sort_map.get(sort, MarketplaceProviderModel.subscriber_count.desc())
    query = query.order_by(order_clause).offset(offset).limit(limit)
    result = await db.execute(query)
    providers = result.scalars().all()

    return ProviderListResponse(
        total=total,
        items=[_provider_to_response(p) for p in providers],
    )


@marketplace_router.get("/api/marketplace/providers/{provider_id}/stats")
@limiter.limit("60/minute")
async def get_provider_stats(
    request: Request,
    provider_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderStatsResponse:
    """Get detailed stats for a single provider. Recomputes from signal_logs."""
    try:
        stats = await compute_provider_stats(provider_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ProviderStatsResponse(**stats)


# ===========================================================================
# Authenticated endpoints
# ===========================================================================


@marketplace_router.post("/api/marketplace/subscribe/{provider_id}")
@limiter.limit("10/minute")
async def subscribe(
    request: Request,
    provider_id: UUID,
    body: SubscribeRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionResponse:
    """Subscribe to a marketplace provider. Requires explicit consent."""
    if not body.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must consent to the risk disclaimer to subscribe",
        )

    try:
        result = await subscribe_to_provider(
            user_id=user.id,
            provider_id=provider_id,
            webhook_destination_id=body.webhook_destination_id,
            db_session=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return SubscriptionResponse(**result)


@marketplace_router.delete("/api/marketplace/unsubscribe/{provider_id}")
@limiter.limit("10/minute")
async def unsubscribe(
    request: Request,
    provider_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Unsubscribe from a marketplace provider."""
    try:
        await unsubscribe_from_provider(
            user_id=user.id,
            provider_id=provider_id,
            db_session=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {"status": "unsubscribed", "provider_id": str(provider_id)}


@marketplace_router.get("/api/marketplace/my-subscriptions")
async def my_subscriptions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MySubscriptionItem]:
    """List the current user's active marketplace subscriptions."""
    result = await db.execute(
        select(MarketplaceSubscriptionModel, MarketplaceProviderModel)
        .join(
            MarketplaceProviderModel,
            MarketplaceSubscriptionModel.provider_id == MarketplaceProviderModel.id,
        )
        .where(
            MarketplaceSubscriptionModel.user_id == user.id,
            MarketplaceSubscriptionModel.is_active.is_(True),
        )
        .order_by(MarketplaceSubscriptionModel.created_at.desc())
    )
    rows = result.all()

    return [
        MySubscriptionItem(
            subscription_id=sub.id,
            provider_id=sub.provider_id,
            provider_name=provider.name,
            provider_asset_class=provider.asset_class,
            routing_rule_id=sub.routing_rule_id,
            is_active=sub.is_active,
            created_at=sub.created_at.isoformat() if sub.created_at else "",
        )
        for sub, provider in rows
    ]


# ===========================================================================
# Admin endpoints
# ===========================================================================


@marketplace_router.post("/api/admin/marketplace/providers")
async def admin_create_provider(
    body: CreateProviderRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminProviderResponse:
    """Create a new marketplace provider (admin only)."""
    # Check channel not already registered
    existing = await db.execute(
        select(MarketplaceProviderModel).where(
            MarketplaceProviderModel.telegram_channel_id == body.telegram_channel_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A provider with this Telegram channel already exists",
        )

    provider = MarketplaceProviderModel(
        name=body.name,
        description=body.description,
        asset_class=body.asset_class,
        telegram_channel_id=body.telegram_channel_id,
    )
    db.add(provider)
    await db.flush()

    return _provider_to_admin_response(provider)


@marketplace_router.get("/api/admin/marketplace/providers")
async def admin_list_providers(
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=True),
) -> list[AdminProviderResponse]:
    """List all marketplace providers including inactive ones (admin only)."""
    query = select(MarketplaceProviderModel)
    if not include_inactive:
        query = query.where(MarketplaceProviderModel.is_active.is_(True))

    query = query.order_by(MarketplaceProviderModel.created_at.desc())
    result = await db.execute(query)
    providers = result.scalars().all()

    return [_provider_to_admin_response(p) for p in providers]


@marketplace_router.put("/api/admin/marketplace/providers/{provider_id}")
async def admin_update_provider(
    provider_id: UUID,
    body: UpdateProviderRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminProviderResponse:
    """Update a marketplace provider (admin only)."""
    result = await db.execute(
        select(MarketplaceProviderModel).where(
            MarketplaceProviderModel.id == provider_id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Check channel uniqueness if changing it
    if "telegram_channel_id" in update_data:
        existing = await db.execute(
            select(MarketplaceProviderModel).where(
                MarketplaceProviderModel.telegram_channel_id == update_data["telegram_channel_id"],
                MarketplaceProviderModel.id != provider_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another provider already uses this Telegram channel",
            )

    for field, value in update_data.items():
        setattr(provider, field, value)

    await db.flush()
    return _provider_to_admin_response(provider)


@marketplace_router.delete("/api/admin/marketplace/providers/{provider_id}")
async def admin_delete_provider(
    provider_id: UUID,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Soft-delete a marketplace provider by setting it inactive (admin only)."""
    result = await db.execute(
        select(MarketplaceProviderModel).where(
            MarketplaceProviderModel.id == provider_id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.is_active = False

    # Also deactivate all subscriptions and their routing rules
    subs_result = await db.execute(
        select(MarketplaceSubscriptionModel).where(
            MarketplaceSubscriptionModel.provider_id == provider_id,
            MarketplaceSubscriptionModel.is_active.is_(True),
        )
    )
    active_subs = subs_result.scalars().all()
    rule_ids_to_deactivate = []
    for sub in active_subs:
        sub.is_active = False
        if sub.routing_rule_id:
            rule_ids_to_deactivate.append(sub.routing_rule_id)

    if rule_ids_to_deactivate:
        await db.execute(
            update(RoutingRuleModel)
            .where(RoutingRuleModel.id.in_(rule_ids_to_deactivate))
            .values(is_active=False)
        )

    await db.flush()

    return {
        "status": "deactivated",
        "provider_id": str(provider_id),
        "subscriptions_deactivated": len(active_subs),
    }


@marketplace_router.get("/api/admin/marketplace/stats")
async def admin_marketplace_stats(
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MarketplaceStatsResponse:
    """Get marketplace-wide statistics (admin only)."""
    from src.adapters.db.models import SignalLogModel

    total_providers = (await db.execute(
        select(func.count()).select_from(MarketplaceProviderModel)
    )).scalar_one()

    active_providers = (await db.execute(
        select(func.count()).select_from(MarketplaceProviderModel).where(
            MarketplaceProviderModel.is_active.is_(True),
        )
    )).scalar_one()

    total_subscriptions = (await db.execute(
        select(func.count()).select_from(MarketplaceSubscriptionModel)
    )).scalar_one()

    active_subscriptions = (await db.execute(
        select(func.count()).select_from(MarketplaceSubscriptionModel).where(
            MarketplaceSubscriptionModel.is_active.is_(True),
        )
    )).scalar_one()

    total_signals_routed = (await db.execute(
        select(func.count()).select_from(SignalLogModel).where(
            SignalLogModel.source_type == "marketplace",
        )
    )).scalar_one()

    return MarketplaceStatsResponse(
        total_providers=total_providers,
        active_providers=active_providers,
        total_subscriptions=total_subscriptions,
        active_subscriptions=active_subscriptions,
        total_signals_routed=total_signals_routed,
    )
