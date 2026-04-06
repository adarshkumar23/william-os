"""
WILLIAM OS - Observability bootstrap (Prometheus metrics and Sentry).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.core.config import Settings

logger = structlog.get_logger(__name__)


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


def setup_sentry(settings: Settings) -> None:
    dsn = settings.sentry_dsn.get_secret_value().strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.environment,
            release=settings.app_version,
            integrations=[FastApiIntegration()],
        )
        logger.info("sentry_initialized", environment=settings.environment)
    except Exception as exc:
        logger.warning("sentry_setup_failed", error=str(exc))
