"""Admin API router — user management, global signal monitoring, system health."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import (
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.api.deps import get_admin_user, get_cache, get_db
from src.core.models import User

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminUserSummary(BaseModel):
    id: UUID
    email: str
    subscription_tier: str
    is_admin: bool
    is_disabled: bool
    created_at: str
    rule_count: int
    signal_count: int
    telegram_connected: bool


class PaginatedAdminUsers(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AdminUserSummary]


class AdminRoutingRule(BaseModel):
    id: UUID
    source_channel_id: str
    source_channel_name: str | None
    destination_webhook_url: str
    payload_version: str
    rule_name: str | None
    destination_type: str
    is_active: bool


class AdminSignalLog(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    routing_rule_id: UUID | None
    raw_message: str
    parsed_data: dict | None
    webhook_payload: dict | None
    status: str
    error_message: str | None
    processed_at: str
    message_id: int | None
    channel_id: str | None


class AdminUserDetail(BaseModel):
    id: UUID
    email: str
    subscription_tier: str
    is_admin: bool
    is_disabled: bool
    created_at: str
    rule_count: int
    signal_count: int
    telegram_connected: bool
    routing_rules: list[AdminRoutingRule]
    recent_signals: list[AdminSignalLog]
    notification_preferences: dict


class AdminUserUpdate(BaseModel):
    subscription_tier: str | None = None
    is_disabled: bool | None = None


class PaginatedAdminSignals(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AdminSignalLog]


class FailingChannel(BaseModel):
    channel_id: str
    fail_count: int


class AdminSignalStats(BaseModel):
    total_today: int
    success_rate_24h: float
    top_failing_channels: list[FailingChannel]


class AdminHealthStats(BaseModel):
    total_users: int
    active_users_7d: int
    signals_today: int
    signals_this_week: int
    success_rate_24h: float
    active_routing_rules: int
    active_telegram_sessions: int


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------


@admin_router.get("/users", response_model=PaginatedAdminUsers)
async def admin_list_users(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
    search: str | None = Query(None),
) -> PaginatedAdminUsers:
    """List all users with aggregate stats."""
    base_filter = []
    if search:
        base_filter.append(UserModel.email.ilike(f"%{search}%"))

    # Total count
    count_q = select(func.count()).select_from(UserModel).where(*base_filter) if base_filter else select(func.count()).select_from(UserModel)
    total = (await db.execute(count_q)).scalar_one()

    # Correlated subqueries for counts
    rule_count_sq = (
        select(func.count())
        .where(RoutingRuleModel.user_id == UserModel.id)
        .correlate(UserModel)
        .scalar_subquery()
    )
    signal_count_sq = (
        select(func.count())
        .where(SignalLogModel.user_id == UserModel.id)
        .correlate(UserModel)
        .scalar_subquery()
    )
    tg_connected_sq = (
        exists(
            select(TelegramSessionModel.id).where(
                TelegramSessionModel.user_id == UserModel.id,
                TelegramSessionModel.is_active.is_(True),
            )
        )
        .correlate(UserModel)
    )

    query = (
        select(
            UserModel,
            rule_count_sq.label("rule_count"),
            signal_count_sq.label("signal_count"),
            tg_connected_sq.label("telegram_connected"),
        )
        .order_by(UserModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if base_filter:
        query = query.where(*base_filter)

    result = await db.execute(query)
    rows = result.all()

    items = [
        AdminUserSummary(
            id=row.UserModel.id,
            email=row.UserModel.email,
            subscription_tier=row.UserModel.subscription_tier,
            is_admin=getattr(row.UserModel, "is_admin", False),
            is_disabled=getattr(row.UserModel, "is_disabled", False),
            created_at=row.UserModel.created_at.isoformat() if row.UserModel.created_at else "",
            rule_count=row.rule_count,
            signal_count=row.signal_count,
            telegram_connected=row.telegram_connected,
        )
        for row in rows
    ]

    return PaginatedAdminUsers(total=total, limit=limit, offset=offset, items=items)


@admin_router.get("/users/{user_id}", response_model=AdminUserDetail)
async def admin_get_user(
    user_id: UUID,
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserDetail:
    """Get detailed user info including their rules and recent signals."""
    user_row = (await db.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
    if user_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Routing rules
    rules_result = await db.execute(
        select(RoutingRuleModel)
        .where(RoutingRuleModel.user_id == user_id)
        .order_by(RoutingRuleModel.created_at.desc())
        .limit(50)
    )
    rules = [
        AdminRoutingRule(
            id=r.id,
            source_channel_id=r.source_channel_id,
            source_channel_name=r.source_channel_name,
            destination_webhook_url=r.destination_webhook_url,
            payload_version=r.payload_version,
            rule_name=r.rule_name,
            destination_type=r.destination_type,
            is_active=r.is_active,
        )
        for r in rules_result.scalars().all()
    ]

    # Recent signals
    signals_result = await db.execute(
        select(SignalLogModel)
        .where(SignalLogModel.user_id == user_id)
        .order_by(SignalLogModel.processed_at.desc())
        .limit(20)
    )
    signals = [
        AdminSignalLog(
            id=s.id,
            user_id=s.user_id,
            user_email=user_row.email,
            routing_rule_id=s.routing_rule_id,
            raw_message=s.raw_message,
            parsed_data=s.parsed_data,
            webhook_payload=s.webhook_payload,
            status=s.status,
            error_message=s.error_message,
            processed_at=s.processed_at.isoformat() if s.processed_at else "",
            message_id=s.message_id,
            channel_id=s.channel_id,
        )
        for s in signals_result.scalars().all()
    ]

    # Counts
    rule_count = len(rules)
    signal_count = (await db.execute(
        select(func.count()).select_from(SignalLogModel).where(SignalLogModel.user_id == user_id)
    )).scalar_one()

    # Telegram status
    tg = (await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.user_id == user_id,
            TelegramSessionModel.is_active.is_(True),
        )
    )).scalar_one_or_none()

    return AdminUserDetail(
        id=user_row.id,
        email=user_row.email,
        subscription_tier=user_row.subscription_tier,
        is_admin=getattr(user_row, "is_admin", False),
        is_disabled=getattr(user_row, "is_disabled", False),
        created_at=user_row.created_at.isoformat() if user_row.created_at else "",
        rule_count=rule_count,
        signal_count=signal_count,
        telegram_connected=tg is not None,
        routing_rules=rules,
        recent_signals=signals,
        notification_preferences=user_row.notification_preferences or {},
    )


@admin_router.patch("/users/{user_id}", response_model=AdminUserSummary)
async def admin_update_user(
    user_id: UUID,
    body: AdminUserUpdate,
    request: Request,
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserSummary:
    """Update a user's tier or disabled status."""
    user_row = (await db.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
    if user_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.subscription_tier is not None:
        valid_tiers = {"free", "starter", "pro", "elite"}
        if body.subscription_tier not in valid_tiers:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid tier. Must be one of: {', '.join(sorted(valid_tiers))}",
            )
        user_row.subscription_tier = body.subscription_tier

    if body.is_disabled is not None:
        user_row.is_disabled = body.is_disabled

    await db.flush()
    await db.refresh(user_row)

    # Bust user cache so changes (tier, disable) are reflected immediately
    cache = request.app.state.cache
    await cache.delete(f"user:{user_id}")

    # Get counts for response
    rule_count = (await db.execute(
        select(func.count()).select_from(RoutingRuleModel).where(RoutingRuleModel.user_id == user_id)
    )).scalar_one()
    signal_count = (await db.execute(
        select(func.count()).select_from(SignalLogModel).where(SignalLogModel.user_id == user_id)
    )).scalar_one()
    tg = (await db.execute(
        select(TelegramSessionModel).where(
            TelegramSessionModel.user_id == user_id,
            TelegramSessionModel.is_active.is_(True),
        )
    )).scalar_one_or_none()

    return AdminUserSummary(
        id=user_row.id,
        email=user_row.email,
        subscription_tier=user_row.subscription_tier,
        is_admin=getattr(user_row, "is_admin", False),
        is_disabled=getattr(user_row, "is_disabled", False),
        created_at=user_row.created_at.isoformat() if user_row.created_at else "",
        rule_count=rule_count,
        signal_count=signal_count,
        telegram_connected=tg is not None,
    )


# ---------------------------------------------------------------------------
# Global Signal Monitoring
# ---------------------------------------------------------------------------


@admin_router.get("/signals", response_model=PaginatedAdminSignals)
async def admin_list_signals(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user_email: str | None = Query(None),
    channel_id: str | None = Query(None),
) -> PaginatedAdminSignals:
    """List all signal logs across all users."""
    base_filter = []
    if status_filter and status_filter != "all":
        base_filter.append(SignalLogModel.status == status_filter)
    if channel_id:
        base_filter.append(SignalLogModel.channel_id == channel_id)
    if date_from:
        try:
            base_filter.append(SignalLogModel.processed_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            base_filter.append(SignalLogModel.processed_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass
    if user_email:
        base_filter.append(UserModel.email.ilike(f"%{user_email}%"))

    # Count
    count_q = (
        select(func.count())
        .select_from(SignalLogModel)
        .join(UserModel, SignalLogModel.user_id == UserModel.id)
    )
    if base_filter:
        count_q = count_q.where(*base_filter)
    total = (await db.execute(count_q)).scalar_one()

    # Fetch
    query = (
        select(SignalLogModel, UserModel.email.label("user_email"))
        .join(UserModel, SignalLogModel.user_id == UserModel.id)
        .order_by(SignalLogModel.processed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if base_filter:
        query = query.where(*base_filter)

    result = await db.execute(query)
    rows = result.all()

    items = [
        AdminSignalLog(
            id=row.SignalLogModel.id,
            user_id=row.SignalLogModel.user_id,
            user_email=row.user_email,
            routing_rule_id=row.SignalLogModel.routing_rule_id,
            raw_message=row.SignalLogModel.raw_message,
            parsed_data=row.SignalLogModel.parsed_data,
            webhook_payload=row.SignalLogModel.webhook_payload,
            status=row.SignalLogModel.status,
            error_message=row.SignalLogModel.error_message,
            processed_at=row.SignalLogModel.processed_at.isoformat() if row.SignalLogModel.processed_at else "",
            message_id=row.SignalLogModel.message_id,
            channel_id=row.SignalLogModel.channel_id,
        )
        for row in rows
    ]

    return PaginatedAdminSignals(total=total, limit=limit, offset=offset, items=items)


@admin_router.get("/signals/stats", response_model=AdminSignalStats)
async def admin_signal_stats(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> AdminSignalStats:
    """Global signal stats: today's count, 24h success rate, top failing channels."""
    import json

    cache_key = "admin:signal_stats"
    cached = await cache.get(cache_key)
    if cached:
        return AdminSignalStats(**json.loads(cached))

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(hours=24)

    # Total today
    total_today = (await db.execute(
        select(func.count()).select_from(SignalLogModel).where(
            SignalLogModel.processed_at >= today_start
        )
    )).scalar_one()

    # Success rate 24h
    counts_24h = (await db.execute(
        select(SignalLogModel.status, func.count())
        .where(SignalLogModel.processed_at >= last_24h)
        .group_by(SignalLogModel.status)
    )).all()
    count_map = {row[0]: row[1] for row in counts_24h}
    total_24h = sum(count_map.values())
    success_24h = count_map.get("success", 0)
    success_rate = round((success_24h / total_24h * 100) if total_24h > 0 else 0.0, 1)

    # Top failing channels (last 7 days)
    seven_days_ago = now - timedelta(days=7)
    failing = (await db.execute(
        select(SignalLogModel.channel_id, func.count().label("cnt"))
        .where(
            SignalLogModel.status == "failed",
            SignalLogModel.processed_at >= seven_days_ago,
            SignalLogModel.channel_id.isnot(None),
        )
        .group_by(SignalLogModel.channel_id)
        .order_by(func.count().desc())
        .limit(5)
    )).all()
    top_failing = [
        FailingChannel(channel_id=row[0], fail_count=row[1])
        for row in failing
    ]

    stats = AdminSignalStats(
        total_today=total_today,
        success_rate_24h=success_rate,
        top_failing_channels=top_failing,
    )
    await cache.set(cache_key, stats.model_dump_json(), ttl_seconds=30)
    return stats


# ---------------------------------------------------------------------------
# System Health
# ---------------------------------------------------------------------------


@admin_router.get("/health", response_model=AdminHealthStats)
async def admin_health(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> AdminHealthStats:
    """System-wide health stats."""
    import json

    cache_key = "admin:health"
    cached = await cache.get(cache_key)
    if cached:
        return AdminHealthStats(**json.loads(cached))

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    last_24h = now - timedelta(hours=24)

    total_users = (await db.execute(select(func.count()).select_from(UserModel))).scalar_one()

    active_users_7d = (await db.execute(
        select(func.count(func.distinct(SignalLogModel.user_id)))
        .where(SignalLogModel.processed_at >= week_ago)
    )).scalar_one()

    signals_today = (await db.execute(
        select(func.count()).select_from(SignalLogModel)
        .where(SignalLogModel.processed_at >= today_start)
    )).scalar_one()

    signals_this_week = (await db.execute(
        select(func.count()).select_from(SignalLogModel)
        .where(SignalLogModel.processed_at >= week_ago)
    )).scalar_one()

    # Success rate 24h
    counts = (await db.execute(
        select(SignalLogModel.status, func.count())
        .where(SignalLogModel.processed_at >= last_24h)
        .group_by(SignalLogModel.status)
    )).all()
    count_map = {row[0]: row[1] for row in counts}
    total_24h = sum(count_map.values())
    success_rate = round(
        (count_map.get("success", 0) / total_24h * 100) if total_24h > 0 else 0.0, 1
    )

    active_rules = (await db.execute(
        select(func.count()).select_from(RoutingRuleModel)
        .where(RoutingRuleModel.is_active.is_(True))
    )).scalar_one()

    active_tg = (await db.execute(
        select(func.count()).select_from(TelegramSessionModel)
        .where(TelegramSessionModel.is_active.is_(True))
    )).scalar_one()

    stats = AdminHealthStats(
        total_users=total_users,
        active_users_7d=active_users_7d,
        signals_today=signals_today,
        signals_this_week=signals_this_week,
        success_rate_24h=success_rate,
        active_routing_rules=active_rules,
        active_telegram_sessions=active_tg,
    )
    await cache.set(cache_key, stats.model_dump_json(), ttl_seconds=60)
    return stats


# ---------------------------------------------------------------------------
# Listener Health
# ---------------------------------------------------------------------------


class ListenerSessionInfo(BaseModel):
    user_id: UUID
    user_email: str
    phone_number: str
    is_active: bool
    disconnected_reason: str | None
    disconnected_at: str | None
    last_active: str | None
    connected_at: str | None
    routing_rule_count: int


class ListenerHealthResponse(BaseModel):
    active_sessions: int
    inactive_sessions: int
    sessions: list[ListenerSessionInfo]


@admin_router.get("/listener-health", response_model=ListenerHealthResponse)
async def admin_listener_health(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ListenerHealthResponse:
    """Listener health overview — shows all Telegram sessions with status."""
    rule_count_sq = (
        select(func.count())
        .where(
            RoutingRuleModel.user_id == TelegramSessionModel.user_id,
            RoutingRuleModel.is_active.is_(True),
        )
        .correlate(TelegramSessionModel)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            TelegramSessionModel,
            UserModel.email.label("user_email"),
            rule_count_sq.label("rule_count"),
        )
        .join(UserModel, TelegramSessionModel.user_id == UserModel.id)
        .order_by(TelegramSessionModel.is_active.desc(), TelegramSessionModel.created_at.desc())
    )
    rows = result.all()

    sessions = [
        ListenerSessionInfo(
            user_id=row.TelegramSessionModel.user_id,
            user_email=row.user_email,
            phone_number=row.TelegramSessionModel.phone_number,
            is_active=row.TelegramSessionModel.is_active,
            disconnected_reason=row.TelegramSessionModel.disconnected_reason,
            disconnected_at=(
                row.TelegramSessionModel.disconnected_at.isoformat()
                if row.TelegramSessionModel.disconnected_at else None
            ),
            last_active=(
                row.TelegramSessionModel.last_active.isoformat()
                if row.TelegramSessionModel.last_active else None
            ),
            connected_at=(
                row.TelegramSessionModel.created_at.isoformat()
                if row.TelegramSessionModel.created_at else None
            ),
            routing_rule_count=row.rule_count,
        )
        for row in rows
    ]

    active = sum(1 for s in sessions if s.is_active)
    return ListenerHealthResponse(
        active_sessions=active,
        inactive_sessions=len(sessions) - active,
        sessions=sessions,
    )
