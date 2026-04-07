"""
WILLIAM OS - HTTP middleware for security headers and response timing.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.metrics import observe_api_request
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from fastapi.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to all HTTP responses."""

    def __init__(self, app, *, is_production: bool = False) -> None:
        super().__init__(app)
        self.is_production = is_production

    async def dispatch(self, request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if self.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Expose request duration in milliseconds for lightweight performance checks."""

    async def dispatch(self, request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_seconds = time.perf_counter() - start
        elapsed_ms = elapsed_seconds * 1000
        route = request.scope.get("route")
        endpoint = getattr(route, "path", request.url.path)
        observe_api_request(
            endpoint=endpoint,
            method=request.method,
            status=response.status_code,
            duration_seconds=elapsed_seconds,
        )
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
        return response
