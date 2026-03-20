"""Tests for src.api.qstash_auth — QStash signature verification."""

import hashlib
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
import jwt

SIGNING_KEY = "test-signing-key-current"
NEXT_SIGNING_KEY = "test-signing-key-next"


def _make_app(*, local_mode: bool = False, current_key: str = "", next_key: str = "") -> FastAPI:
    """Build a minimal FastAPI app with the QStash auth dependency."""
    from src.api.deps import Settings
    from src.api.qstash_auth import verify_qstash_signature

    settings = Settings(
        LOCAL_MODE=local_mode,
        QSTASH_CURRENT_SIGNING_KEY=current_key,
        QSTASH_NEXT_SIGNING_KEY=next_key,
    )

    app = FastAPI()

    @app.post("/protected")
    async def protected(request: Request):
        await verify_qstash_signature(request, settings)
        return {"ok": True}

    return app


def _sign_body(body: bytes, key: str) -> str:
    """Create a valid QStash-style JWT with body hash claim."""
    body_hash = hashlib.sha256(body).hexdigest()
    return jwt.encode({"body": body_hash, "iss": "Upstash"}, key, algorithm="HS256")


def test_local_mode_skips_validation():
    """In LOCAL_MODE, requests should pass without a signature."""
    app = _make_app(local_mode=True)
    client = TestClient(app)

    response = client.post("/protected", json={"message": "test"})
    assert response.status_code == 200


def test_missing_signature_rejected():
    """Without LOCAL_MODE, missing signature should return 401."""
    app = _make_app(local_mode=False, current_key=SIGNING_KEY)
    client = TestClient(app)

    response = client.post("/protected", json={"message": "test"})
    assert response.status_code == 401
    assert "Missing" in response.json()["detail"]


def test_valid_signature_accepted():
    """A valid signature with matching body hash should pass."""
    app = _make_app(local_mode=False, current_key=SIGNING_KEY)
    client = TestClient(app)

    body = b'{"message": "test"}'
    signature = _sign_body(body, SIGNING_KEY)

    response = client.post(
        "/protected",
        content=body,
        headers={"Upstash-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200


def test_invalid_signature_rejected():
    """A signature signed with the wrong key should return 401."""
    app = _make_app(local_mode=False, current_key=SIGNING_KEY)
    client = TestClient(app)

    body = b'{"message": "test"}'
    signature = _sign_body(body, "wrong-key")

    response = client.post(
        "/protected",
        content=body,
        headers={"Upstash-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_key_rotation_fallback():
    """If current key fails, next key should be tried."""
    app = _make_app(local_mode=False, current_key=SIGNING_KEY, next_key=NEXT_SIGNING_KEY)
    client = TestClient(app)

    body = b'{"message": "test"}'
    # Sign with the NEXT key (simulating key rotation)
    signature = _sign_body(body, NEXT_SIGNING_KEY)

    response = client.post(
        "/protected",
        content=body,
        headers={"Upstash-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200


def test_no_signing_keys_configured():
    """If no signing keys are set in production mode, return 500."""
    app = _make_app(local_mode=False, current_key="", next_key="")
    client = TestClient(app)

    response = client.post(
        "/protected",
        json={"message": "test"},
        headers={"Upstash-Signature": "some-token"},
    )
    assert response.status_code == 500
