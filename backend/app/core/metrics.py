"""
WILLIAM OS - Custom Prometheus metrics helpers.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

try:
    from prometheus_client import Counter, Gauge, Histogram
except Exception:  # pragma: no cover - metrics are optional in some environments
    Counter = None  # type: ignore[assignment]
    Gauge = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]


if Histogram is not None:
    api_request_duration_seconds = Histogram(
        "api_request_duration_seconds",
        "Duration of API requests in seconds",
        labelnames=("endpoint", "method", "status"),
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    ai_call_duration_seconds = Histogram(
        "ai_call_duration_seconds",
        "Duration of AI provider calls in seconds",
        labelnames=("provider",),
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 40.0),
    )
else:
    api_request_duration_seconds = None
    ai_call_duration_seconds = None

if Counter is not None:
    module_action_total = Counter(
        "module_action_total",
        "Count of module actions",
        labelnames=("module", "action"),
    )
    notification_delivery_total = Counter(
        "notification_delivery_total",
        "Notification delivery attempts by channel and status",
        labelnames=("channel", "status"),
    )
else:
    module_action_total = None
    notification_delivery_total = None

if Gauge is not None:
    life_score_gauge = Gauge(
        "life_score_gauge",
        "Current life score gauge by anonymized user",
        labelnames=("user_hash",),
    )
else:
    life_score_gauge = None


def observe_api_request(endpoint: str, method: str, status: int, duration_seconds: float) -> None:
    if api_request_duration_seconds is None:
        return
    api_request_duration_seconds.labels(
        endpoint=endpoint,
        method=method,
        status=str(status),
    ).observe(max(0.0, duration_seconds))


def increment_module_action(module: str, action: str) -> None:
    if module_action_total is None:
        return
    module_action_total.labels(module=module, action=action).inc()


def observe_ai_call(provider: str, duration_seconds: float) -> None:
    if ai_call_duration_seconds is None:
        return
    ai_call_duration_seconds.labels(provider=provider).observe(max(0.0, duration_seconds))


def increment_notification_delivery(channel: str, status: str) -> None:
    if notification_delivery_total is None:
        return
    notification_delivery_total.labels(channel=channel, status=status).inc()


def set_life_score(user_id: UUID, score: float) -> None:
    if life_score_gauge is None:
        return

    user_hash = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]
    life_score_gauge.labels(user_hash=user_hash).set(float(score))
