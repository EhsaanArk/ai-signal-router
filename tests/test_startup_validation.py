"""Tests for production startup validation in src/main.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.main import _validate_production_settings


def _make_settings(**overrides) -> MagicMock:
    """Build a mock Settings with safe production defaults."""
    defaults = {
        "JWT_SECRET_KEY": "production-strong-secret-key-32chars",
        "ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=",
        "OPENAI_API_KEY": "sk-test",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@db.prod:5432/sgm",
        "REDIS_URL": "redis://redis.prod:6379/0",
        "FRONTEND_URL": "https://app.radar.sagemaster.com",
        "TELEGRAM_API_ID": 12345,
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_BOT_WEBHOOK_SECRET": "",
        "TELEGRAM_BOT_LINK_SECRET": "",
        "RESEND_API_KEY": "re_test",
        "SENTRY_DSN": "https://sentry.io/123",
    }
    defaults.update(overrides)
    settings = MagicMock()
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def test_valid_production_settings_pass():
    """No errors when all required settings are properly configured."""
    settings = _make_settings()
    _validate_production_settings(settings)  # should not raise


def test_bot_token_without_webhook_secret_fails():
    """Setting TELEGRAM_BOT_TOKEN without TELEGRAM_BOT_WEBHOOK_SECRET must raise."""
    settings = _make_settings(
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF",
        TELEGRAM_BOT_WEBHOOK_SECRET="",
        TELEGRAM_BOT_LINK_SECRET="some-link-secret",
    )
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_WEBHOOK_SECRET"):
        _validate_production_settings(settings)


def test_bot_token_without_link_secret_fails():
    """Setting TELEGRAM_BOT_TOKEN without TELEGRAM_BOT_LINK_SECRET must raise."""
    settings = _make_settings(
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF",
        TELEGRAM_BOT_WEBHOOK_SECRET="some-webhook-secret",
        TELEGRAM_BOT_LINK_SECRET="",
    )
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_LINK_SECRET"):
        _validate_production_settings(settings)


def test_bot_token_with_both_secrets_passes():
    """When all bot secrets are set, validation should pass."""
    settings = _make_settings(
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF",
        TELEGRAM_BOT_WEBHOOK_SECRET="some-webhook-secret",
        TELEGRAM_BOT_LINK_SECRET="some-link-secret",
    )
    _validate_production_settings(settings)  # should not raise
