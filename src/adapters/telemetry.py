"""OpenTelemetry instrumentation for the SGM Signal Copier.

Initialises tracing, metrics, and log-correlation exporters that ship data
to an OTLP-compatible collector (e.g. Grafana Alloy → Tempo / Mimir / Loki).

Behaviour is controlled entirely via standard OTel environment variables:

    OTEL_EXPORTER_OTLP_ENDPOINT   – collector URL  (default: http://localhost:4317)
    OTEL_SERVICE_NAME             – service name    (default: signal-copier-api)
    OTEL_SDK_DISABLED             – set "true" to disable all instrumentation

When ``OTEL_SDK_DISABLED=true`` or the SDK packages are missing, all public
functions in this module become safe no-ops.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_initialised = False


def init_telemetry() -> None:
    """Bootstrap OpenTelemetry providers and auto-instrumentors.

    Safe to call multiple times — only the first invocation takes effect.
    """
    global _initialised
    if _initialised:
        return

    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1"):
        logger.info("OpenTelemetry SDK disabled via OTEL_SDK_DISABLED")
        _initialised = True
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed — skipping instrumentation. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp"
        )
        _initialised = True
        return

    service_name = os.environ.get("OTEL_SERVICE_NAME", "signal-copier-api")
    resource = Resource.create({"service.name": service_name})

    # -- Traces ------------------------------------------------------------
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # -- Metrics -----------------------------------------------------------
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # -- Auto-instrumentation ----------------------------------------------
    _auto_instrument()

    _initialised = True
    logger.info("OpenTelemetry initialised (service=%s)", service_name)


def _auto_instrument() -> None:
    """Activate auto-instrumentors for FastAPI, SQLAlchemy, and httpx."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
    except ImportError:
        logger.debug("FastAPI auto-instrumentation not available")

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument()
    except ImportError:
        logger.debug("SQLAlchemy auto-instrumentation not available")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except ImportError:
        logger.debug("httpx auto-instrumentation not available")

    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=True)
    except ImportError:
        logger.debug("Logging auto-instrumentation not available")


def shutdown_telemetry() -> None:
    """Flush and shut down all OTel providers.  Safe to call even if
    ``init_telemetry`` was never called or the SDK is disabled."""
    try:
        from opentelemetry import trace, metrics

        tp = trace.get_tracer_provider()
        if hasattr(tp, "shutdown"):
            tp.shutdown()

        mp = metrics.get_meter_provider()
        if hasattr(mp, "shutdown"):
            mp.shutdown()
    except Exception:
        logger.debug("OTel shutdown skipped (not initialised or SDK missing)")


def get_tracer(name: str = __name__):
    """Return an OTel tracer.  Falls back to a no-op tracer if the SDK is
    not available."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        # Return a dummy object whose methods are all no-ops.
        from contextlib import contextmanager

        class _NoOpSpan:
            def set_attribute(self, *a, **kw): ...
            def set_status(self, *a, **kw): ...
            def record_exception(self, *a, **kw): ...
            def __enter__(self): return self
            def __exit__(self, *a): ...

        class _NoOpTracer:
            @contextmanager
            def start_as_current_span(self, *a, **kw):
                yield _NoOpSpan()

        return _NoOpTracer()
