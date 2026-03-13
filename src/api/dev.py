"""Development-only router — available when LOCAL_MODE=true.

Provides convenience endpoints for injecting test signals without needing
a running Telegram listener or QStash.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Settings, get_db, get_settings
from src.core.models import DispatchResult, RawSignal

logger = logging.getLogger(__name__)

dev_router = APIRouter(prefix="/api/dev", tags=["dev"])

# A fixed dummy user ID for local development injection
_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class InjectSignalRequest(BaseModel):
    """Payload for the dev signal-injection endpoint."""

    text: str
    channel_id: str = "dev-channel"
    user_id: UUID = Field(default=_DEV_USER_ID, description="Override the dummy user ID if needed")


class InjectSignalResponse(BaseModel):
    raw_signal: RawSignal
    results: list[DispatchResult]


@dev_router.post("/inject-signal", response_model=InjectSignalResponse)
async def inject_signal(
    body: InjectSignalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InjectSignalResponse:
    """Inject a fake signal and run it through the processing pipeline.

    This endpoint creates a :class:`RawSignal` with a dummy user ID and
    the current timestamp, then invokes the same ``process_signal`` pipeline
    used by the production workflow endpoint.
    """
    raw_signal = RawSignal(
        user_id=body.user_id,
        channel_id=body.channel_id,
        raw_message=body.text,
        message_id=0,
        timestamp=datetime.now(timezone.utc),
    )

    logger.info(
        "DEV inject-signal: channel=%s text=%s",
        body.channel_id,
        body.text[:80],
    )

    # Import and call the same pipeline used by the workflow endpoint
    from src.api.workflow import process_signal

    results = await process_signal(
        raw_signal=raw_signal,
        db=db,
        settings=settings,
    )

    return InjectSignalResponse(raw_signal=raw_signal, results=results)
