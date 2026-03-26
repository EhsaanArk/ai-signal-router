"""Routing Rules endpoints — CRUD, test webhook, parse preview, symbol check."""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import RoutingRuleModel
from src.api.deps import (
    Settings,
    get_cache,
    get_current_user,
    get_db,
    get_settings,
    limiter,
)
from src.core.exceptions import (
    ConflictError,
    ExternalServiceError,
    InputValidationError,
    ResourceNotFoundError,
    TierLimitError,
)
from src.core.models import SubscriptionTier, User, normalize_enabled_actions
from src.core.security import validate_outbound_webhook_url

from src.api.routes.schemas import (
    ParsePreviewRequest,
    ParsePreviewResponse,
    RoutingRuleCreate,
    RoutingRuleResponse,
    RoutingRuleUpdate,
    TestWebhookRequest,
    TestWebhookResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _rule_to_response(r: RoutingRuleModel) -> RoutingRuleResponse:
    """Convert a RoutingRuleModel row to a RoutingRuleResponse."""
    return RoutingRuleResponse(
        id=r.id,
        user_id=r.user_id,
        source_channel_id=r.source_channel_id,
        source_channel_name=r.source_channel_name,
        destination_webhook_url=r.destination_webhook_url,
        payload_version=r.payload_version,
        symbol_mappings=r.symbol_mappings or {},
        risk_overrides=r.risk_overrides or {},
        webhook_body_template=r.webhook_body_template,
        rule_name=r.rule_name,
        destination_label=r.destination_label,
        destination_type=r.destination_type,
        custom_ai_instructions=r.custom_ai_instructions,
        enabled_actions=r.enabled_actions,
        keyword_blacklist=r.keyword_blacklist or [],
        is_active=r.is_active,
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


def _check_tier_limit(
    tier: SubscriptionTier,
    current_rule_count: int,
) -> None:
    """Raise if the user has reached their destination limit."""
    if current_rule_count >= tier.max_destinations:
        raise TierLimitError(
            f"Your {tier.value} plan allows up to "
            f"{tier.max_destinations} route(s). "
            "Please upgrade to add more."
        )


# ============================================================================
# Routing Rules
# ============================================================================


@router.get("/routing-rules", response_model=list[RoutingRuleResponse])
async def list_routing_rules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
) -> list[RoutingRuleResponse]:
    """Return all routing rules belonging to the current user."""
    cache_key = f"rules:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return [RoutingRuleResponse(**r) for r in json.loads(cached)]

    result = await db.execute(
        select(RoutingRuleModel)
        .where(
            RoutingRuleModel.user_id == current_user.id,
            RoutingRuleModel.is_marketplace_template.is_(False),
        )
        .order_by(RoutingRuleModel.created_at.desc())
    )
    rows = result.scalars().all()
    rules = [_rule_to_response(r) for r in rows]
    await cache.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in rules]),
        ttl_seconds=30,
    )
    return rules


@router.post(
    "/routing-rules",
    response_model=RoutingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_routing_rule(
    body: RoutingRuleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache=Depends(get_cache),
) -> RoutingRuleResponse:
    """Create a new routing rule after verifying the user's tier limit."""
    allowed_url, reason, _ips = validate_outbound_webhook_url(
        body.destination_webhook_url,
        local_mode=settings.LOCAL_MODE,
    )
    if not allowed_url:
        raise InputValidationError(f"Invalid destination webhook URL: {reason}")

    # Marketplace template rules are exempt from tier limits and template validation
    is_template = getattr(body, "is_marketplace_template", False)

    if not is_template:
        # Count existing active rules (excluding marketplace templates)
        count_result = await db.execute(
            select(func.count())
            .select_from(RoutingRuleModel)
            .where(
                RoutingRuleModel.user_id == current_user.id,
                RoutingRuleModel.is_active.is_(True),
                RoutingRuleModel.is_marketplace_template.is_(False),
            )
        )
        current_count = count_result.scalar_one()

        _check_tier_limit(current_user.subscription_tier, current_count)

    # Prevent duplicate webhook URLs across accounts (same user can reuse).
    # Admin users are exempt — they need to test with shared webhook URLs.
    if not current_user.is_admin:
        dup_result = await db.execute(
            select(RoutingRuleModel.id)
            .where(
                RoutingRuleModel.destination_webhook_url == body.destination_webhook_url,
                RoutingRuleModel.user_id != current_user.id,
                RoutingRuleModel.is_active.is_(True),
            )
            .limit(1)
        )
        if dup_result.scalar_one_or_none() is not None:
            raise ConflictError(
                "This webhook URL is already in use by another account. "
                "Each SageMaster Assist can only be connected to one Sage Radar account."
            )

    # Template is required for SageMaster destinations (contains assistId)
    # Marketplace template rules skip this — they only store the webhook URL
    if not is_template and body.destination_type in ("sagemaster_forex", "sagemaster_crypto") and not body.webhook_body_template:
        raise InputValidationError(
            "Webhook body template is required for SageMaster destinations. "
            "Copy the JSON from your SageMaster Assists overview page > "
            "alert configuration in SageMaster."
        )

    new_rule = RoutingRuleModel(
        user_id=current_user.id,
        source_channel_id=body.source_channel_id,
        source_channel_name=body.source_channel_name,
        destination_webhook_url=body.destination_webhook_url,
        payload_version=body.payload_version,
        symbol_mappings=body.symbol_mappings,
        risk_overrides=body.risk_overrides,
        webhook_body_template=body.webhook_body_template,
        rule_name=body.rule_name,
        destination_label=body.destination_label,
        destination_type=body.destination_type,
        custom_ai_instructions=body.custom_ai_instructions,
        enabled_actions=normalize_enabled_actions(body.enabled_actions),
        keyword_blacklist=body.keyword_blacklist,
        is_active=True,
        is_marketplace_template=is_template,
    )
    db.add(new_rule)
    await db.flush()  # populate default values (id, timestamps)
    await cache.delete(f"rules:{current_user.id}")

    return _rule_to_response(new_rule)


@router.get("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def get_routing_rule(
    rule_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoutingRuleResponse:
    """Return a single routing rule by ID, scoped to the current user."""
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Routing rule not found")
    return _rule_to_response(row)


@router.put("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def update_routing_rule(
    rule_id: UUID,
    body: RoutingRuleUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache=Depends(get_cache),
) -> RoutingRuleResponse:
    """Update a routing rule by ID, scoped to the current user."""
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Routing rule not found")

    update_data = body.model_dump(exclude_unset=True)

    effective_url = update_data.get("destination_webhook_url", row.destination_webhook_url)
    allowed_url, reason, _ips = validate_outbound_webhook_url(
        effective_url,
        local_mode=settings.LOCAL_MODE,
    )
    if not allowed_url:
        raise InputValidationError(f"Invalid destination webhook URL: {reason}")

    # Prevent duplicate webhook URLs across accounts:
    # - when URL is changed to one already used by another account
    # - when reactivating a rule whose URL is now used by another account
    url_changed = "destination_webhook_url" in update_data and update_data["destination_webhook_url"] != row.destination_webhook_url
    reactivating = update_data.get("is_active") is True and not row.is_active
    if url_changed or reactivating:
        check_url = update_data.get("destination_webhook_url", row.destination_webhook_url)
        dup_result = await db.execute(
            select(RoutingRuleModel.id)
            .where(
                RoutingRuleModel.destination_webhook_url == check_url,
                RoutingRuleModel.user_id != current_user.id,
                RoutingRuleModel.is_active.is_(True),
            )
            .limit(1)
        )
        if dup_result.scalar_one_or_none() is not None:
            raise ConflictError(
                "This webhook URL is already in use by another account. "
                "Each SageMaster Assist can only be connected to one Sage Radar account."
            )

    # Determine the effective destination_type and template after update
    effective_type = update_data.get("destination_type", row.destination_type)
    effective_template = update_data.get("webhook_body_template", row.webhook_body_template)
    if effective_type in ("sagemaster_forex", "sagemaster_crypto") and not effective_template:
        raise InputValidationError(
            "Webhook body template is required for SageMaster destinations. "
            "Copy the JSON from your SageMaster Assists overview page > "
            "alert configuration in SageMaster."
        )

    if "enabled_actions" in update_data:
        update_data["enabled_actions"] = normalize_enabled_actions(update_data["enabled_actions"])

    for field, value in update_data.items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    await cache.delete(f"rules:{current_user.id}")

    return _rule_to_response(row)


@router.delete(
    "/routing-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_routing_rule(
    rule_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache=Depends(get_cache),
):
    """Delete a routing rule by ID, scoped to the current user."""
    result = await db.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Routing rule not found")
    await db.delete(row)
    await cache.delete(f"rules:{current_user.id}")


@router.post("/parse-preview", response_model=ParsePreviewResponse)
@limiter.limit("10/minute")
async def parse_preview(
    request: Request,
    body: ParsePreviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Preview how the AI parser interprets a signal message.

    This is a sandbox endpoint — it does NOT dispatch to any webhook,
    does NOT log to signal_logs, and does NOT expose the system prompt.
    Rate limited to 10 requests/minute per user.
    """
    import asyncio
    from src.adapters.openai import OpenAISignalParser
    from src.core.models import RawSignal

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise ExternalServiceError("Parser not available — OpenAI API key not configured.")

    parser = OpenAISignalParser(api_key=settings.OPENAI_API_KEY)

    # Build a stub RawSignal for the parser
    stub_signal = RawSignal(
        user_id=current_user.id,
        channel_id="preview",
        raw_message=body.message,
        message_id=0,
    )

    try:
        parsed = await asyncio.wait_for(
            parser.parse(stub_signal),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        raise ExternalServiceError("Parser timed out. Try again.")
    except Exception as exc:
        logger.warning("Parse preview failed: %s", exc)
        raise InputValidationError("Couldn't parse this message. Try different wording.")

    # Compute forwarding verdict against supplied enabled_actions
    display_label: str | None = None
    would_forward: bool | None = None
    blocked: str | None = None

    if parsed.is_valid_signal:
        from src.core.mapper import _signal_action

        try:
            computed = _signal_action(parsed)
            display_label = computed.value
            normalized = normalize_enabled_actions(body.enabled_actions)
            if normalized is not None and computed.value not in normalized:
                would_forward = False
                blocked = f"Action '{computed.value}' is disabled for this route"
            else:
                would_forward = True
        except ValueError:
            display_label = parsed.action
            would_forward = False
            blocked = f"Action '{parsed.action}' is not supported"

    return ParsePreviewResponse(
        is_valid_signal=parsed.is_valid_signal,
        action=parsed.action if parsed.is_valid_signal else None,
        symbol=parsed.symbol if parsed.is_valid_signal and parsed.symbol != "UNKNOWN" else None,
        direction=parsed.direction if parsed.is_valid_signal else None,
        order_type=parsed.order_type if parsed.is_valid_signal else None,
        entry_price=parsed.entry_price,
        stop_loss=parsed.stop_loss,
        take_profits=parsed.take_profits,
        percentage=parsed.percentage,
        ignore_reason=parsed.ignore_reason if not parsed.is_valid_signal else None,
        display_action_label=display_label,
        route_would_forward=would_forward,
        blocked_reason=blocked,
    )


@router.post("/webhook/test", response_model=TestWebhookResponse)
async def test_webhook(
    body: TestWebhookRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TestWebhookResponse:
    """Send a test ping to a webhook URL to verify connectivity."""
    import httpx

    try:
        url = body.url
        allowed, reason, _ips = validate_outbound_webhook_url(
            url,
            local_mode=settings.LOCAL_MODE,
        )
        if not allowed:
            raise InputValidationError(f"Invalid webhook URL: {reason}")

        test_payload = {
            "type": "test",
            "source": "sagemaster-signal-copier",
            "message": "This is a test ping from SageMaster Signal Copier.",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=test_payload)
            return TestWebhookResponse(
                success=resp.status_code < 400,
                status_code=resp.status_code,
                error=None if resp.status_code < 400 else f"HTTP {resp.status_code}",
            )
    except httpx.TimeoutException:
        return TestWebhookResponse(success=False, error="Request timed out")
    except InputValidationError:
        raise
    except Exception as exc:
        return TestWebhookResponse(success=False, error=str(exc))
