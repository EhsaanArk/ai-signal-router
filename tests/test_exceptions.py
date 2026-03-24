"""Tests for the domain exception hierarchy and global handler."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DispatchError,
    ExternalServiceError,
    InputValidationError,
    ResourceNotFoundError,
    SageRadarError,
    TierLimitError,
)


# ---------------------------------------------------------------------------
# Exception hierarchy tests
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Verify the exception class taxonomy."""

    def test_base_exception_has_message(self):
        exc = SageRadarError("test message")
        assert exc.message == "test message"
        assert str(exc) == "test message"

    def test_base_exception_default_message(self):
        exc = SageRadarError()
        assert exc.message == "An unexpected error occurred"

    def test_authentication_error_is_sage_radar_error(self):
        assert issubclass(AuthenticationError, SageRadarError)

    def test_authorization_error_is_sage_radar_error(self):
        assert issubclass(AuthorizationError, SageRadarError)

    def test_tier_limit_is_authorization_error(self):
        assert issubclass(TierLimitError, AuthorizationError)

    def test_resource_not_found_is_sage_radar_error(self):
        assert issubclass(ResourceNotFoundError, SageRadarError)

    def test_conflict_is_sage_radar_error(self):
        assert issubclass(ConflictError, SageRadarError)

    def test_input_validation_is_sage_radar_error(self):
        assert issubclass(InputValidationError, SageRadarError)

    def test_external_service_is_sage_radar_error(self):
        assert issubclass(ExternalServiceError, SageRadarError)

    def test_dispatch_error_is_external_service_error(self):
        assert issubclass(DispatchError, ExternalServiceError)


# ---------------------------------------------------------------------------
# Global handler integration tests
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the domain exception handler."""
    from src.main import create_app

    app = create_app()

    @app.get("/test/auth-error")
    async def _auth_error():
        raise AuthenticationError("bad token")

    @app.get("/test/authz-error")
    async def _authz_error():
        raise AuthorizationError("not admin")

    @app.get("/test/tier-limit")
    async def _tier_limit():
        raise TierLimitError("free plan max")

    @app.get("/test/not-found")
    async def _not_found():
        raise ResourceNotFoundError("rule missing")

    @app.get("/test/conflict")
    async def _conflict():
        raise ConflictError("duplicate")

    @app.get("/test/validation")
    async def _validation():
        raise InputValidationError("bad input")

    @app.get("/test/external")
    async def _external():
        raise ExternalServiceError("openai down")

    @app.get("/test/dispatch")
    async def _dispatch():
        raise DispatchError("webhook failed")

    @app.get("/test/base")
    async def _base():
        raise SageRadarError("unknown")

    return app


@pytest.fixture(scope="module")
def client():
    app = _make_test_app()
    return TestClient(app, raise_server_exceptions=False)


class TestGlobalExceptionHandler:
    """Verify status codes and response shape from the global handler."""

    def test_authentication_error_returns_401(self, client):
        resp = client.get("/test/auth-error")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "AuthenticationError"
        assert body["error"]["message"] == "bad token"

    def test_401_includes_www_authenticate_header(self, client):
        resp = client.get("/test/auth-error")
        assert resp.headers.get("WWW-Authenticate") == "Bearer"

    def test_authorization_error_returns_403(self, client):
        resp = client.get("/test/authz-error")
        assert resp.status_code == 403

    def test_tier_limit_returns_403(self, client):
        resp = client.get("/test/tier-limit")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "TierLimitError"

    def test_not_found_returns_404(self, client):
        resp = client.get("/test/not-found")
        assert resp.status_code == 404

    def test_conflict_returns_409(self, client):
        resp = client.get("/test/conflict")
        assert resp.status_code == 409

    def test_validation_returns_422(self, client):
        resp = client.get("/test/validation")
        assert resp.status_code == 422

    def test_external_service_returns_502(self, client):
        resp = client.get("/test/external")
        assert resp.status_code == 502

    def test_dispatch_error_returns_502(self, client):
        resp = client.get("/test/dispatch")
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "DispatchError"

    def test_base_error_returns_500(self, client):
        resp = client.get("/test/base")
        assert resp.status_code == 500

    def test_error_response_shape(self, client):
        resp = client.get("/test/validation")
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
