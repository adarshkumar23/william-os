"""
WILLIAM OS — Main Application
FastAPI entry point with lifecycle management, error handling, and middleware.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.logging import setup_logging
from app.core.middleware import RequestTimingMiddleware, SecurityHeadersMiddleware
from app.core.observability import setup_metrics, setup_sentry, setup_tracing
from app.core.offline import OfflineFallbackMiddleware
from app.core.permissions import ScopeEnforcementMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.sync import register_sync_broadcaster
from app.core.websocket import register_websocket_routes
from app.modules.audit.service import register_audit_handlers
from app.modules.gamification.service import register_gamification_handlers
from app.shared.types import (
    AuthenticationError,
    AuthorizationError,
    EncryptionError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    WilliamError,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


# ── Lifecycle ────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    setup_logging()
    setup_sentry(settings)
    logger.info("william_os_starting", version=settings.app_version, env=settings.environment)

    # Initialize database (dev: auto-create tables)
    if not settings.is_production:
        await init_db()

    # Register event handlers
    register_audit_handlers()
    register_gamification_handlers()
    register_sync_broadcaster()

    logger.info("william_os_ready")
    yield

    # Shutdown
    await close_db()
    logger.info("william_os_shutdown")


# ── App Factory ──────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)
    app.add_middleware(ScopeEnforcementMiddleware)
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(OfflineFallbackMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.state.degraded_mode = False
    app.state.degraded_reason = None
    setup_tracing(app, settings)

    # ── Exception Handlers ───────────────────────────────────
    @app.exception_handler(WilliamError)
    async def william_error_handler(request: Request, exc: WilliamError):
        status_map = {
            AuthenticationError: 401,
            AuthorizationError: 403,
            NotFoundError: 404,
            ValidationError: 422,
            RateLimitError: 429,
            EncryptionError: 400,
        }
        status = status_map.get(type(exc), 500)
        return ORJSONResponse(
            status_code=status,
            content={"ok": False, "data": None, "error": exc.message, "meta": {"code": exc.code}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = jsonable_encoder(
            exc.errors(),
            custom_encoder={ValueError: lambda value: str(value)},
        )
        return ORJSONResponse(
            status_code=422,
            content={
                "ok": False,
                "data": None,
                "error": "Validation error",
                "meta": {"details": details},
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return ORJSONResponse(
            status_code=500,
            content={
                "ok": False,
                "data": None,
                "error": "Internal server error" if settings.is_production else str(exc),
            },
        )

    # ── Routes ───────────────────────────────────────────────
    register_routes(app)
    register_gamification_handlers()
    register_websocket_routes(app)
    setup_metrics(app, enabled=settings.metrics_enabled)

    # ── Health Check ─────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health():
        return {
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.environment,
            "degraded_mode": bool(getattr(app.state, "degraded_mode", False)),
            "degraded_reason": getattr(app.state, "degraded_reason", None),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    return app


def register_routes(app: FastAPI) -> None:
    """Register all module routers under /api/v1."""
    from app.modules.agents.routes import router as agents_router  # noqa: I001
    from app.modules.auth.routes import router as auth_router
    from app.modules.briefing.routes import router as briefing_router
    from app.modules.decisions.routes import router as decisions_router
    from app.modules.email_intel.routes import router as email_router
    from app.modules.experiments.routes import router as experiments_router
    from app.modules.export.routes import router as export_router
    from app.modules.feed.routes import router as feed_router
    from app.modules.fitness.routes import router as fitness_router
    from app.modules.gamification.routes import router as gamification_router
    from app.modules.habits.routes import router as habits_router
    from app.modules.intelligence.routes import router as intelligence_router
    from app.modules.journal.routes import router as journal_router
    from app.modules.memory.routes import router as memory_router
    from app.modules.medicine.routes import router as medicine_router
    from app.modules.messaging.routes import router as messaging_router
    from app.modules.rules.routes import router as rules_router
    from app.modules.scheduler.routes import router as scheduler_router
    from app.modules.secrets.routes import router as secrets_router
    from app.modules.sleep.routes import router as sleep_router
    from app.modules.study.routes import router as study_router
    from app.modules.trading.routes import router as trading_router
    from app.modules.voice.routes import router as voice_router

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(agents_router, prefix=prefix)
    app.include_router(briefing_router, prefix=prefix)
    app.include_router(scheduler_router, prefix=prefix)
    app.include_router(habits_router, prefix=prefix)
    app.include_router(gamification_router, prefix=prefix)
    app.include_router(feed_router, prefix=prefix)
    app.include_router(intelligence_router, prefix=prefix)
    app.include_router(fitness_router, prefix=prefix)
    app.include_router(journal_router, prefix=prefix)
    app.include_router(memory_router, prefix=prefix)
    app.include_router(medicine_router, prefix=prefix)
    app.include_router(email_router, prefix=prefix)
    app.include_router(messaging_router, prefix=prefix)
    app.include_router(secrets_router, prefix=prefix)
    app.include_router(rules_router, prefix=prefix)
    app.include_router(voice_router, prefix=prefix)
    app.include_router(study_router, prefix=prefix)
    app.include_router(trading_router, prefix=prefix)
    app.include_router(sleep_router, prefix=prefix)
    app.include_router(decisions_router, prefix=prefix)
    app.include_router(experiments_router, prefix=prefix)
    app.include_router(export_router, prefix=prefix)
    # Future modules added here:
    # app.include_router(audit_router, prefix=prefix)


# ── Application instance ─────────────────────────────────────────
app = create_app()
