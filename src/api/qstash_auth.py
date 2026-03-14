"""QStash signature verification dependency for the workflow router.

QStash signs every callback with a JWT in the ``Upstash-Signature`` header.
The JWT body hash claim must match the SHA-256 of the request body.  Two
signing keys are supported (current + next) for seamless key rotation.

In ``LOCAL_MODE`` validation is skipped so the dev inject endpoint and
local queue adapter can call the workflow without a real QStash signature.
"""

import hashlib
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from src.api.deps import Settings, get_settings

logger = logging.getLogger(__name__)


async def verify_qstash_signature(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Validate the ``Upstash-Signature`` JWT header on incoming QStash callbacks.

    Skips validation entirely when ``LOCAL_MODE=true``.
    """
    if settings.LOCAL_MODE:
        return

    signature = request.headers.get("Upstash-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Upstash-Signature header",
        )

    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()

    signing_keys = [
        k for k in [settings.QSTASH_CURRENT_SIGNING_KEY, settings.QSTASH_NEXT_SIGNING_KEY] if k
    ]

    if not signing_keys:
        logger.error("No QStash signing keys configured — cannot verify signature")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="QStash signing keys not configured",
        )

    for key in signing_keys:
        try:
            claims = jwt.decode(
                signature,
                key,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            # Verify the body hash matches
            if claims.get("body") == body_hash:
                return
            logger.warning("QStash body hash mismatch: expected %s", body_hash)
        except JWTError:
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Upstash-Signature",
    )
