"""User endpoints — /me, notification preferences, signal logs, stats."""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from src.adapters.db.models import SignalLogModel, UserModel
from src.api.deps import (
    get_cache,
    get_current_user,
    get_db,
)
from src.core.models import User

from src.api.routes.schemas import (
    LogStatsResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    PaginatedLogs,
    SignalLogResponse,
    UserMeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])


# ============================================================================
# User profile
# ============================================================================


@router.get("/auth/me", response_model=UserMeResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserMeResponse:
    """Return the current authenticated user's profile."""
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        subscription_tier=current_user.subscription_tier.value,
        is_admin=current_user.is_admin,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
        accepted_tos_version=current_user.accepted_tos_version,
        accepted_risk_waiver=current_user.accepted_risk_waiver,
    )


# ============================================================================
# Signal Logs
# ============================================================================


@router.get("/logs", response_model=PaginatedLogs)
async def list_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = Query(None, alias="status"),
    rule_id: UUID | None = Query(None),
) -> PaginatedLogs:
    """Return paginated signal logs for the current user."""
    # Base filter
    base_filter = [SignalLogModel.user_id == current_user.id]
    if status_filter and status_filter != "all":
        base_filter.append(SignalLogModel.status == status_filter)
    if rule_id:
        base_filter.append(SignalLogModel.routing_rule_id == rule_id)

    # Total count
    count_result = await db.execute(
        select(func.count())
        .select_from(SignalLogModel)
        .where(*base_filter)
    )
    total = count_result.scalar_one()

    # Fetch page
    result = await db.execute(
        select(SignalLogModel)
        .where(*base_filter)
        .order_by(SignalLogModel.processed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()

    items = [
        SignalLogResponse(
            id=r.id,
            user_id=r.user_id,
            routing_rule_id=r.routing_rule_id,
            raw_message=r.raw_message,
            parsed_data=r.parsed_data,
            webhook_payload=r.webhook_payload,
            status=r.status,
            error_message=r.error_message,
            processed_at=r.processed_at.isoformat() if r.processed_at else "",
            message_id=r.message_id,
            channel_id=r.channel_id,
            reply_to_msg_id=r.reply_to_msg_id,
        )
        for r in rows
    ]

    return PaginatedLogs(total=total, limit=limit, offset=offset, items=items)


@router.get("/logs/stats", response_model=LogStatsResponse)
async def log_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> LogStatsResponse:
    """Return signal log counts by status for the current user."""
    cache_key = f"log_stats:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return LogStatsResponse(**json.loads(cached))

    result = await db.execute(
        select(SignalLogModel.status, func.count())
        .where(SignalLogModel.user_id == current_user.id)
        .group_by(SignalLogModel.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())

    stats = LogStatsResponse(
        total=total,
        success=counts.get("success", 0),
        failed=counts.get("failed", 0),
        ignored=counts.get("ignored", 0),
    )
    await cache.set(cache_key, stats.model_dump_json(), ttl_seconds=15)
    return stats


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


@router.get("/settings/notifications", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferencesResponse:
    """Return the current user's notification preferences."""
    result = await db.execute(
        select(UserModel.notification_preferences).where(
            UserModel.id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none() or {}
    return NotificationPreferencesResponse(**prefs)


@router.put("/settings/notifications", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: NotificationPreferencesUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferencesResponse:
    """Update the current user's notification preferences."""
    result = await db.execute(
        select(UserModel).where(UserModel.id == current_user.id)
    )
    user_row = result.scalar_one()

    current_prefs = dict(user_row.notification_preferences or {})
    updates = body.model_dump(exclude_none=True)
    current_prefs.update(updates)
    user_row.notification_preferences = current_prefs
    flag_modified(user_row, "notification_preferences")

    return NotificationPreferencesResponse(**current_prefs)
