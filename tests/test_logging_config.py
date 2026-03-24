"""Tests for the centralised logging configuration."""

import logging
import os
from unittest.mock import patch

import pytest

import src.core.logging_config as logging_config


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset the _CONFIGURED flag and root logger between tests."""
    logging_config._CONFIGURED = False
    root = logging.getLogger()
    root.handlers.clear()
    yield
    logging_config._CONFIGURED = False
    root.handlers.clear()


class TestConfigureLogging:
    """Verify configure_logging() behaviour in both modes."""

    def test_local_mode_uses_human_readable_format(self):
        with patch.dict(os.environ, {"LOCAL_MODE": "true"}):
            logging_config.configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, logging.Formatter)
        assert "[%(name)s]" in handler.formatter._fmt

    def test_production_mode_uses_json_format(self):
        with patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            logging_config.configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        # JsonFormatter is from pythonjsonlogger
        formatter = root.handlers[0].formatter
        assert type(formatter).__name__ == "JsonFormatter"

    def test_idempotent_second_call_is_noop(self):
        with patch.dict(os.environ, {"LOCAL_MODE": "true"}):
            logging_config.configure_logging()
            logging_config.configure_logging()  # second call
        root = logging.getLogger()
        # Should still have exactly 1 handler, not 2
        assert len(root.handlers) == 1

    def test_log_level_from_env(self):
        with patch.dict(os.environ, {"LOCAL_MODE": "true", "LOG_LEVEL": "DEBUG"}):
            logging_config.configure_logging()
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_default_log_level_is_info(self):
        env = {k: v for k, v in os.environ.items() if k != "LOG_LEVEL"}
        env["LOCAL_MODE"] = "true"
        with patch.dict(os.environ, env, clear=True):
            logging_config.configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
