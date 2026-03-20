"""Admin API router — user management, global signal monitoring, system health."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import case, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import (
    GlobalSettingModel,
    ParserConfigModel,
    RoutingRuleModel,
    SignalLogModel,
    TelegramSessionModel,
    UserModel,
)
from src.api.deps import Settings, get_admin_user, get_cache, get_db, get_settings
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


class AdminDeployHealthResponse(BaseModel):
    status: str
    deploy_health: str
    current: dict[str, Any]
    pre_deploy_snapshot: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None


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


@admin_router.get("/deploy-health", response_model=AdminDeployHealthResponse)
async def admin_deploy_health(
    _admin: Annotated[User, Depends(get_admin_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDeployHealthResponse:
    """Detailed deploy health view with per-user identifiers (admin only)."""
    from src.adapters.telegram.deploy_snapshot import compare_snapshots, read_pre_deploy_snapshot

    active_sessions = (await db.execute(
        select(func.count()).select_from(TelegramSessionModel)
        .where(TelegramSessionModel.is_active.is_(True))
    )).scalar_one()

    active_session_users = (await db.execute(
        select(TelegramSessionModel.user_id)
        .where(TelegramSessionModel.is_active.is_(True))
    )).scalars().all()

    active_channels = (await db.execute(
        select(func.count(func.distinct(
            RoutingRuleModel.source_channel_id
        ))).where(RoutingRuleModel.is_active.is_(True))
    )).scalar_one()

    last_signal = (await db.execute(
        select(SignalLogModel.processed_at)
        .order_by(SignalLogModel.processed_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    current = {
        "active_sessions": active_sessions,
        "connected_listeners": active_sessions,
        "channels_monitored": active_channels,
        "user_ids": [str(uid) for uid in active_session_users],
        "last_signal_at": last_signal.isoformat() if last_signal else None,
    }

    pre_snapshot = await read_pre_deploy_snapshot(request.app.state.cache)
    comparison = None
    deploy_health = "HEALTHY"
    if pre_snapshot:
        comparison = compare_snapshots(pre_snapshot, current)
        deploy_health = comparison["verdict"]

    return AdminDeployHealthResponse(
        status="ok",
        deploy_health=deploy_health,
        current=current,
        pre_deploy_snapshot=pre_snapshot,
        comparison=comparison,
    )


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


# ---------------------------------------------------------------------------
# AI Parser Manager
# ---------------------------------------------------------------------------


class ParserConfigResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    id: UUID
    config_key: str
    system_prompt: str | None
    model_name: str | None
    temperature: float | None
    version: int
    is_active: bool
    change_note: str | None
    changed_by_email: str | None
    created_at: str


class SystemPromptUpdate(BaseModel):
    system_prompt: str = Field(..., min_length=10, max_length=50000)
    change_note: str | None = None


class ModelConfigUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str = Field(..., pattern=r"^(gpt-4o-mini|gpt-4o|gpt-4-turbo)$")
    temperature: float = Field(..., ge=0.0, le=1.0)
    change_note: str | None = None


class TestParseRequest(BaseModel):
    raw_message: str = Field(..., min_length=1, max_length=5000)
    custom_instructions: str | None = None
    include_mapping: bool = False
    routing_rule_id: str | None = None


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    message: str


class TestParseResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    parsed: dict[str, Any]
    model_used: str
    temperature_used: float
    validation_checks: list[ValidationCheck] = []
    webhook_payload: dict[str, Any] | None = None


class TestDispatchRequest(BaseModel):
    raw_message: str = Field(..., min_length=1, max_length=5000)
    routing_rule_id: str
    custom_instructions: str | None = None


class TestDispatchResponse(BaseModel):
    status_code: int
    response_body: str


class ReplayResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    original_parsed: dict[str, Any] | None
    new_parsed: dict[str, Any]
    model_used: str
    temperature_used: float
    validation_checks: list[ValidationCheck] = []
    raw_message: str


class PaginatedParserHistory(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ParserConfigResponse]


def _config_to_response(row: ParserConfigModel) -> ParserConfigResponse:
    return ParserConfigResponse(
        id=row.id,
        config_key=row.config_key,
        system_prompt=row.system_prompt,
        model_name=row.model_name,
        temperature=row.temperature,
        version=row.version,
        is_active=row.is_active,
        change_note=row.change_note,
        changed_by_email=row.changed_by_email,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


async def _save_config_version(
    db: AsyncSession,
    cache: Any,
    config_key: str,
    admin_email: str,
    change_note: str | None = None,
    *,
    system_prompt: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
) -> ParserConfigModel:
    """Deactivate current active config, insert new version, bust cache."""
    max_version = (await db.execute(
        select(func.coalesce(func.max(ParserConfigModel.version), 0)).where(
            ParserConfigModel.config_key == config_key,
        )
    )).scalar_one()

    await db.execute(
        update(ParserConfigModel)
        .where(
            ParserConfigModel.config_key == config_key,
            ParserConfigModel.is_active.is_(True),
        )
        .values(is_active=False)
    )

    new_row = ParserConfigModel(
        config_key=config_key,
        system_prompt=system_prompt,
        model_name=model_name,
        temperature=temperature,
        version=max_version + 1,
        is_active=True,
        change_note=change_note,
        changed_by_email=admin_email,
    )
    db.add(new_row)
    await db.flush()
    await db.refresh(new_row)

    await cache.delete("parser:config")

    return new_row


@admin_router.get("/parser/prompt", response_model=ParserConfigResponse)
async def get_parser_prompt(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ParserConfigResponse:
    """Get the active system prompt, or the hardcoded default if none set."""
    row = (await db.execute(
        select(ParserConfigModel).where(
            ParserConfigModel.config_key == "system_prompt",
            ParserConfigModel.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if row:
        return _config_to_response(row)

    from src.adapters.openai.parser import OpenAISignalParser

    return ParserConfigResponse(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        config_key="system_prompt",
        system_prompt=OpenAISignalParser.get_default_system_prompt(),
        model_name=None,
        temperature=None,
        version=0,
        is_active=True,
        change_note="Hardcoded default",
        changed_by_email=None,
        created_at="",
    )


@admin_router.get("/parser/prompt/history", response_model=PaginatedParserHistory)
async def get_parser_prompt_history(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
    offset: int = 0,
) -> PaginatedParserHistory:
    """Get version history of system prompt changes."""
    base = select(ParserConfigModel).where(
        ParserConfigModel.config_key == "system_prompt",
    )

    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    rows = (await db.execute(
        base.order_by(ParserConfigModel.version.desc())
        .limit(limit)
        .offset(offset)
    )).scalars().all()

    return PaginatedParserHistory(
        total=total,
        limit=limit,
        offset=offset,
        items=[_config_to_response(r) for r in rows],
    )


@admin_router.put("/parser/prompt", response_model=ParserConfigResponse)
async def update_parser_prompt(
    body: SystemPromptUpdate,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> ParserConfigResponse:
    """Save a new system prompt version."""
    new_row = await _save_config_version(
        db, cache, "system_prompt", admin.email,
        change_note=body.change_note,
        system_prompt=body.system_prompt,
    )
    return _config_to_response(new_row)


@admin_router.post(
    "/parser/prompt/revert/{version_id}",
    response_model=ParserConfigResponse,
)
async def revert_parser_prompt(
    version_id: UUID,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> ParserConfigResponse:
    """Revert to a previous system prompt version."""
    old_row = (await db.execute(
        select(ParserConfigModel).where(ParserConfigModel.id == version_id)
    )).scalar_one_or_none()

    if old_row is None or old_row.config_key != "system_prompt":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    new_row = await _save_config_version(
        db, cache, "system_prompt", admin.email,
        change_note=f"Reverted from version {old_row.version}",
        system_prompt=old_row.system_prompt,
    )
    return _config_to_response(new_row)


@admin_router.get("/parser/model", response_model=ParserConfigResponse)
async def get_parser_model(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ParserConfigResponse:
    """Get the active model configuration."""
    row = (await db.execute(
        select(ParserConfigModel).where(
            ParserConfigModel.config_key == "model_config",
            ParserConfigModel.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if row:
        return _config_to_response(row)

    return ParserConfigResponse(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        config_key="model_config",
        system_prompt=None,
        model_name="gpt-4o-mini",
        temperature=0.0,
        version=0,
        is_active=True,
        change_note="Default configuration",
        changed_by_email=None,
        created_at="",
    )


@admin_router.put("/parser/model", response_model=ParserConfigResponse)
async def update_parser_model(
    body: ModelConfigUpdate,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> ParserConfigResponse:
    """Update model configuration."""
    new_row = await _save_config_version(
        db, cache, "model_config", admin.email,
        change_note=body.change_note,
        model_name=body.model_name,
        temperature=body.temperature,
    )
    return _config_to_response(new_row)


@admin_router.post("/parser/test", response_model=TestParseResponse)
async def test_parse_signal(
    body: TestParseRequest,
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TestParseResponse:
    """Dry-run parse a raw signal message. No signal log or webhook dispatch.

    When ``include_mapping`` is True and a ``routing_rule_id`` is provided,
    the mapper step is also run, producing the ``webhook_payload`` that would
    be sent to SageMaster. This enables full pipeline dry-run testing without
    actually dispatching.
    """
    import uuid as _uuid

    from src.adapters.openai import OpenAISignalParser
    from src.core.models import RawSignal

    system_prompt, model_name, temperature = await _load_active_parser_config(db)

    parser = OpenAISignalParser(
        api_key=settings.OPENAI_API_KEY,
        model=model_name,
        temperature=temperature,
    )

    raw = RawSignal(
        user_id=_uuid.UUID("00000000-0000-0000-0000-000000000000"),
        channel_id="test-sandbox",
        raw_message=body.raw_message,
        message_id=0,
    )

    parsed = await parser.parse(
        raw,
        custom_instructions=body.custom_instructions,
        system_prompt=system_prompt,
    )

    parsed_dict = parsed.model_dump()
    checks = _validate_parsed_signal(parsed)

    # Optional mapping step — dry-run the full pipeline
    webhook_payload: dict[str, Any] | None = None
    if body.include_mapping and parsed.is_valid_signal:
        from src.core.mapper import apply_symbol_mapping, build_webhook_payload
        from src.core.models import RoutingRule

        if body.routing_rule_id:
            rule_row = (await db.execute(
                select(RoutingRuleModel).where(
                    RoutingRuleModel.id == _uuid.UUID(body.routing_rule_id)
                )
            )).scalar_one_or_none()

            if rule_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Routing rule not found for mapping dry-run",
                )

            rule = RoutingRule(
                id=rule_row.id,
                user_id=rule_row.user_id,
                source_channel_id=rule_row.source_channel_id,
                destination_webhook_url=rule_row.destination_webhook_url,
                payload_version=rule_row.payload_version,
                symbol_mappings=rule_row.symbol_mappings or {},
                risk_overrides=rule_row.risk_overrides or {},
                webhook_body_template=rule_row.webhook_body_template,
                destination_type=rule_row.destination_type,
            )
        else:
            # Use a minimal default rule for mapping preview
            rule = RoutingRule(
                id=_uuid.UUID("00000000-0000-0000-0000-000000000000"),
                user_id=_uuid.UUID("00000000-0000-0000-0000-000000000000"),
                source_channel_id="test-sandbox",
                destination_webhook_url="https://example.com/webhook",
                payload_version="V2",
                webhook_body_template={
                    "type": "",
                    "assistId": "dry-run-preview",
                    "source": "",
                    "symbol": "",
                    "date": "",
                    "price": "",
                    "takeProfits": [],
                    "stopLoss": None,
                },
                destination_type="sagemaster_forex",
            )

        mapped_signal = apply_symbol_mapping(parsed, rule)
        try:
            webhook_payload = build_webhook_payload(mapped_signal, rule)
            checks.append(ValidationCheck(
                name="Webhook Payload",
                passed=True,
                message=f"Payload built successfully with {len(webhook_payload)} fields",
            ))
        except ValueError as exc:
            checks.append(ValidationCheck(
                name="Webhook Payload",
                passed=False,
                message=f"Mapping failed: {exc}",
            ))

    return TestParseResponse(
        parsed=parsed_dict,
        model_used=model_name,
        temperature_used=temperature,
        validation_checks=checks,
        webhook_payload=webhook_payload,
    )


def _validate_parsed_signal(parsed: Any) -> list[ValidationCheck]:
    """Run validation checks on a parsed signal."""
    checks: list[ValidationCheck] = []

    # Check is_valid_signal
    checks.append(ValidationCheck(
        name="Valid Signal",
        passed=parsed.is_valid_signal,
        message="Signal is valid" if parsed.is_valid_signal else f"Invalid: {parsed.ignore_reason or 'unknown reason'}",
    ))

    if not parsed.is_valid_signal:
        return checks  # Skip further checks for invalid signals

    # Check symbol
    checks.append(ValidationCheck(
        name="Symbol Present",
        passed=parsed.symbol != "UNKNOWN" and bool(parsed.symbol),
        message=f"Symbol: {parsed.symbol}" if parsed.symbol != "UNKNOWN" else "Symbol is UNKNOWN",
    ))

    # Check action is valid parser action (not webhook action enum)
    valid_actions = {
        "entry", "partial_close", "breakeven", "close_position",
        "close_all", "close_all_stop", "start_assist", "stop_assist",
        "modify_sl", "modify_tp", "trailing_sl", "extra_order",
    }
    action_valid = parsed.action in valid_actions
    checks.append(ValidationCheck(
        name="Valid Action",
        passed=action_valid,
        message=f"Action: {parsed.action}" if action_valid else f"Unknown action: {parsed.action}",
    ))

    # Check direction
    checks.append(ValidationCheck(
        name="Valid Direction",
        passed=parsed.direction in ("long", "short"),
        message=f"Direction: {parsed.direction}",
    ))

    # Check order_type
    checks.append(ValidationCheck(
        name="Valid Order Type",
        passed=parsed.order_type in ("market", "limit", "stop"),
        message=f"Order type: {parsed.order_type}",
    ))

    # Check asset class
    valid_classes = {"forex", "crypto", "indices", "commodities"}
    checks.append(ValidationCheck(
        name="Valid Asset Class",
        passed=parsed.source_asset_class in valid_classes,
        message=f"Asset class: {parsed.source_asset_class}",
    ))

    # Entry price consistency
    if parsed.action == "entry":
        if parsed.order_type == "limit" and parsed.entry_price is None:
            checks.append(ValidationCheck(
                name="Limit Order Price",
                passed=False,
                message="Limit order requires entry_price",
            ))
        else:
            checks.append(ValidationCheck(
                name="Entry Price",
                passed=True,
                message=f"Entry: {parsed.entry_price}" if parsed.entry_price else "Market order (no price)",
            ))

    # TP/SL sanity
    if parsed.take_profits:
        checks.append(ValidationCheck(
            name="Take Profits",
            passed=True,
            message=f"{len(parsed.take_profits)} TP levels: {parsed.take_profits}",
        ))

    if parsed.stop_loss is not None and parsed.entry_price is not None:
        if parsed.direction == "long" and parsed.stop_loss >= parsed.entry_price:
            checks.append(ValidationCheck(
                name="SL Below Entry (Long)",
                passed=False,
                message=f"SL ({parsed.stop_loss}) should be below entry ({parsed.entry_price}) for long",
            ))
        elif parsed.direction == "short" and parsed.stop_loss <= parsed.entry_price:
            checks.append(ValidationCheck(
                name="SL Above Entry (Short)",
                passed=False,
                message=f"SL ({parsed.stop_loss}) should be above entry ({parsed.entry_price}) for short",
            ))
        else:
            checks.append(ValidationCheck(
                name="SL Position",
                passed=True,
                message=f"SL: {parsed.stop_loss} (correct side of entry)",
            ))

    return checks


async def _load_active_parser_config(
    db: AsyncSession,
) -> tuple[str | None, str, float]:
    """Load active parser config from DB. Returns (system_prompt, model_name, temperature)."""
    model_row = (await db.execute(
        select(ParserConfigModel).where(
            ParserConfigModel.config_key == "model_config",
            ParserConfigModel.is_active.is_(True),
        )
    )).scalar_one_or_none()

    prompt_row = (await db.execute(
        select(ParserConfigModel).where(
            ParserConfigModel.config_key == "system_prompt",
            ParserConfigModel.is_active.is_(True),
        )
    )).scalar_one_or_none()

    model_name = model_row.model_name if model_row else "gpt-4o-mini"
    temperature = model_row.temperature if model_row else 0.0
    system_prompt = prompt_row.system_prompt if prompt_row else None

    return system_prompt, model_name, temperature


@admin_router.post("/parser/replay/{signal_log_id}", response_model=ReplayResponse)
async def replay_signal(
    signal_log_id: UUID,
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReplayResponse:
    """Re-parse a historical signal with the current parser config."""
    import uuid as _uuid

    from src.adapters.openai import OpenAISignalParser
    from src.core.models import RawSignal

    signal_log = (await db.execute(
        select(SignalLogModel).where(SignalLogModel.id == signal_log_id)
    )).scalar_one_or_none()

    if signal_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal log not found",
        )

    system_prompt, model_name, temperature = await _load_active_parser_config(db)

    parser = OpenAISignalParser(
        api_key=settings.OPENAI_API_KEY,
        model=model_name,
        temperature=temperature,
    )

    raw = RawSignal(
        user_id=signal_log.user_id,
        channel_id=signal_log.channel_id or "replay",
        raw_message=signal_log.raw_message,
        message_id=signal_log.message_id or 0,
    )

    parsed = await parser.parse(raw, system_prompt=system_prompt)
    checks = _validate_parsed_signal(parsed)

    return ReplayResponse(
        original_parsed=signal_log.parsed_data,
        new_parsed=parsed.model_dump(),
        model_used=model_name,
        temperature_used=temperature,
        validation_checks=checks,
        raw_message=signal_log.raw_message,
    )


@admin_router.post("/parser/test-dispatch", response_model=TestDispatchResponse)
async def test_dispatch_signal(
    body: TestDispatchRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TestDispatchResponse:
    """Parse a signal and dispatch to a routing rule's webhook (sandbox test)."""
    import uuid as _uuid

    from src.adapters.openai import OpenAISignalParser
    from src.adapters.webhook import WebhookDispatcher
    from src.core.models import RawSignal, RoutingRule

    # Load routing rule
    rule_row = (await db.execute(
        select(RoutingRuleModel).where(RoutingRuleModel.id == _uuid.UUID(body.routing_rule_id))
    )).scalar_one_or_none()

    if rule_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routing rule not found",
        )

    system_prompt, model_name, temperature = await _load_active_parser_config(db)

    parser = OpenAISignalParser(
        api_key=settings.OPENAI_API_KEY,
        model=model_name,
        temperature=temperature,
    )

    raw = RawSignal(
        user_id=admin.id,
        channel_id="test-sandbox",
        raw_message=body.raw_message,
    )

    parsed = await parser.parse(
        raw,
        custom_instructions=body.custom_instructions,
        system_prompt=system_prompt,
    )

    if not parsed.is_valid_signal:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Signal is not valid: {parsed.ignore_reason}",
        )

    # Build routing rule domain object
    rule = RoutingRule(
        id=rule_row.id,
        user_id=rule_row.user_id,
        source_channel_id=rule_row.source_channel_id,
        destination_webhook_url=rule_row.destination_webhook_url,
        payload_version=rule_row.payload_version,
        symbol_mappings=rule_row.symbol_mappings or {},
        risk_overrides=rule_row.risk_overrides or {},
        webhook_body_template=rule_row.webhook_body_template,
        destination_type=rule_row.destination_type,
    )

    # Dispatch via webhook dispatcher (handles mapping, payload, retries)
    async with WebhookDispatcher() as dispatcher:
        result = await dispatcher.dispatch(parsed, rule)

    return TestDispatchResponse(
        status_code=200 if result.success else 500,
        response_body=result.error_message or "Dispatched successfully",
    )


# ---------------------------------------------------------------------------
# Global Settings
# ---------------------------------------------------------------------------


class GlobalSettingResponse(BaseModel):
    key: str
    value: str
    description: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None


class GlobalSettingsUpdateRequest(BaseModel):
    settings: dict[str, str] = Field(
        ...,
        description="Key-value pairs to update. Only known keys are accepted.",
    )


# Keys that admin can configure, with type + bounds for validation
KNOWN_SETTING_KEYS: dict[str, dict] = {
    "backfill_max_age_seconds": {
        "type": "int",
        "min": 10,
        "max": 600,
        "description": "Max age (seconds) for a signal to be considered fresh during backfill.",
    },
}


@admin_router.get("/settings", response_model=list[GlobalSettingResponse])
async def get_global_settings(
    _admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Fetch all global settings."""
    result = await db.execute(select(GlobalSettingModel))
    rows = result.scalars().all()
    return [
        GlobalSettingResponse(
            key=r.key,
            value=r.value,
            description=r.description,
            updated_by=r.updated_by,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in rows
    ]


@admin_router.put("/settings", response_model=list[GlobalSettingResponse])
async def update_global_settings(
    body: GlobalSettingsUpdateRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update one or more global settings. Only known keys are accepted."""
    errors = []
    for key, value in body.settings.items():
        if key not in KNOWN_SETTING_KEYS:
            errors.append(f"Unknown setting: {key}")
            continue
        spec = KNOWN_SETTING_KEYS[key]
        if spec["type"] == "int":
            try:
                int_val = int(value)
            except ValueError:
                errors.append(f"{key}: must be an integer")
                continue
            if int_val < spec["min"] or int_val > spec["max"]:
                errors.append(f"{key}: must be between {spec['min']} and {spec['max']}")
                continue

    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    for key, value in body.settings.items():
        result = await db.execute(
            select(GlobalSettingModel).where(GlobalSettingModel.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_by = admin.email
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(GlobalSettingModel(
                key=key,
                value=value,
                description=KNOWN_SETTING_KEYS[key].get("description"),
                updated_by=admin.email,
            ))

    await db.commit()

    # Return updated settings
    result = await db.execute(select(GlobalSettingModel))
    rows = result.scalars().all()
    return [
        GlobalSettingResponse(
            key=r.key,
            value=r.value,
            description=r.description,
            updated_by=r.updated_by,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in rows
    ]
