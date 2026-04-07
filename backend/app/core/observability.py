"""
WILLIAM OS - Observability bootstrap (Prometheus metrics and Sentry).
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.core.config import Settings

logger = structlog.get_logger(__name__)


def _setup_tracer_provider(settings: Settings) -> None:
    trace = importlib.import_module("opentelemetry.trace")
    resource_mod = importlib.import_module("opentelemetry.sdk.resources")
    trace_mod = importlib.import_module("opentelemetry.sdk.trace")
    export_mod = importlib.import_module("opentelemetry.sdk.trace.export")
    sampling_mod = importlib.import_module("opentelemetry.sdk.trace.sampling")

    Resource = resource_mod.Resource
    TracerProvider = trace_mod.TracerProvider
    BatchSpanProcessor = export_mod.BatchSpanProcessor
    ConsoleSpanExporter = export_mod.ConsoleSpanExporter
    TraceIdRatioBased = sampling_mod.TraceIdRatioBased

    endpoint = settings.otel_exporter_otlp_endpoint.strip()
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name}),
        sampler=TraceIdRatioBased(settings.otel_traces_sample_rate),
    )

    if endpoint:
        exporter_mod = importlib.import_module(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter"
        )
        OTLPSpanExporter = exporter_mod.OTLPSpanExporter

        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            timeout=settings.otel_exporter_timeout_seconds,
        )
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def setup_metrics(app, enabled: bool) -> None:
    if not enabled:
        return

    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,
        )
    except Exception as exc:
        logger.warning("metrics_setup_failed", error=str(exc))


def setup_tracing(app, settings: Settings) -> None:
    if not settings.otel_enabled:
        return

    if getattr(app.state, "otel_instrumented", False):
        return

    try:
        fastapi_mod = importlib.import_module("opentelemetry.instrumentation.fastapi")
        FastAPIInstrumentor = fastapi_mod.FastAPIInstrumentor

        _setup_tracer_provider(settings)
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/metrics")
        app.state.otel_instrumented = True
        logger.info("otel_fastapi_initialized", service=settings.otel_service_name)
    except Exception as exc:
        logger.warning("otel_fastapi_setup_failed", error=str(exc))


def setup_celery_tracing(celery_app, settings: Settings) -> None:
    if not settings.otel_enabled:
        return

    if getattr(celery_app.conf, "otel_instrumented", False):
        return

    try:
        celery_mod = importlib.import_module("opentelemetry.instrumentation.celery")
        CeleryInstrumentor = celery_mod.CeleryInstrumentor

        _setup_tracer_provider(settings)
        CeleryInstrumentor().instrument()
        celery_app.conf.otel_instrumented = True
        logger.info("otel_celery_initialized", service=settings.otel_service_name)
    except Exception as exc:
        logger.warning("otel_celery_setup_failed", error=str(exc))


def setup_sentry(settings: Settings) -> None:
    dsn = settings.sentry_dsn.get_secret_value().strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        logging_integration = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR,
        )

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            environment=settings.environment,
            release=settings.app_version,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                CeleryIntegration(monitor_beat_tasks=True),
                logging_integration,
            ],
        )
        logger.info("sentry_initialized", environment=settings.environment)
    except Exception as exc:
        logger.warning("sentry_setup_failed", error=str(exc))
