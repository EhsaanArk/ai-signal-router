"""Centralised logging configuration.

Call :func:`configure_logging` once at application startup (inside
``create_app()``) to set the root logger format.

* **Production** (``LOCAL_MODE=false``): JSON lines via *python-json-logger*
  for structured log aggregation (Railway, Datadog, etc.).
* **Local** (``LOCAL_MODE=true``): human-readable coloured output.
"""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure_logging() -> None:
    """Configure the root logger based on the current environment.

    Idempotent — safe to call more than once.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    local_mode = os.getenv("LOCAL_MODE", "true").lower() in ("true", "1", "yes")

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers (e.g. from basicConfig)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if local_mode:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        from pythonjsonlogger.json import JsonFormatter

        formatter = JsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s %(funcName)s %(lineno)d",
            rename_fields={
                "levelname": "level",
                "asctime": "timestamp",
            },
            timestamp=True,
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)
