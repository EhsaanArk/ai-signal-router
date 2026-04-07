"""Domain exception hierarchy for the SGM Telegram Signal Copier.

Provides a clear taxonomy of error categories that map to HTTP status
codes via the global exception handler registered in ``src/main.py``.
This replaces scattered ``HTTPException`` raises and gives an acquiring
team's engineers immediate visibility into the system's failure modes.
"""

from __future__ import annotations


class SageRadarError(Exception):
    """Base exception for all Sage Radar domain errors."""

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(message)


# -- Authentication & Authorization (401 / 403) -------------------------


class AuthenticationError(SageRadarError):
    """Invalid, expired, or missing credentials (HTTP 401)."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class AuthorizationError(SageRadarError):
    """Caller lacks permission for this action (HTTP 403)."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class TierLimitError(AuthorizationError):
    """Subscription tier limit exceeded (HTTP 403)."""

    def __init__(self, message: str = "Subscription tier limit exceeded") -> None:
        super().__init__(message)


class RegistrationDisabledError(AuthorizationError):
    """New user registration is temporarily closed (HTTP 403)."""

    def __init__(self, message: str = "Registration is currently closed") -> None:
        super().__init__(message)


# -- Resource errors (404 / 409) -----------------------------------------


class ResourceNotFoundError(SageRadarError):
    """Requested entity does not exist (HTTP 404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ConflictError(SageRadarError):
    """Operation conflicts with existing state (HTTP 409)."""

    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message)


# -- Validation (422) ----------------------------------------------------


class InputValidationError(SageRadarError):
    """Client-supplied data is invalid (HTTP 422).

    Named ``InputValidationError`` to avoid collision with
    ``pydantic.ValidationError``.
    """

    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(message)


# -- External services (502) ---------------------------------------------


class ExternalServiceError(SageRadarError):
    """Upstream service (OpenAI, QStash, Telegram) returned an error (HTTP 502)."""

    def __init__(self, message: str = "External service error") -> None:
        super().__init__(message)


class DispatchError(ExternalServiceError):
    """Webhook delivery to SageMaster failed (HTTP 502)."""

    def __init__(self, message: str = "Signal dispatch failed") -> None:
        super().__init__(message)
