"""
WILLIAM OS — Event Bus
In-process pub/sub for module decoupling.
When we extract a module to a microservice, we swap this for Redis Streams.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from app.core.metrics import increment_module_action

logger = structlog.get_logger(__name__)


class EventType(str, Enum):
    # Auth
    USER_REGISTERED = "user.registered"
    USER_LOGGED_IN = "user.logged_in"

    # Scheduler
    SCHEDULE_GENERATED = "schedule.generated"
    SCHEDULE_ITEM_COMPLETED = "schedule.item_completed"
    SCHEDULE_RESCHEDULED = "schedule.rescheduled"

    # Habits
    HABIT_CHECKED_IN = "habit.checked_in"
    HABIT_MISSED = "habit.missed"
    PROCRASTINATION_DETECTED = "procrastination.detected"

    # Health
    FITNESS_DATA_SYNCED = "fitness.data_synced"
    WORKOUT_LOGGED = "fitness.workout_logged"
    SLEEP_DATA_RECORDED = "sleep.data_recorded"
    MEDICINE_TAKEN = "medicine.taken"
    MEDICINE_MISSED = "medicine.missed"

    # Journal
    JOURNAL_ENTRY_CREATED = "journal.entry_created"

    # Study
    STUDY_SESSION_COMPLETED = "study.session_completed"

    # Decisions
    DECISION_COMPLETED_WITH_OUTCOME = "decision.completed_with_outcome"

    # Email
    EMAIL_SUMMARY_READY = "email.summary_ready"

    # Intelligence
    INTELLIGENCE_SIGNALS_COLLECTED = "intelligence.signals_collected"
    INTELLIGENCE_RULES_APPLIED = "intelligence.rules_applied"
    INTELLIGENCE_LIFE_SCORE_COMPUTED = "intelligence.life_score_computed"

    # System
    DAILY_CYCLE_MIDNIGHT = "system.midnight_cycle"
    DAILY_CYCLE_PREWAKE = "system.prewake_cycle"
    DAILY_CYCLE_NIGHT = "system.night_cycle"

    # Integrations
    INTEGRATION_TRIGGERED = "integrations.triggered"


@dataclass(frozen=True, slots=True)
class Event:
    type: EventType
    data: dict[str, Any]
    user_id: uuid.UUID | None = None
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Simple in-process async event bus."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("event_handler_registered", event_type=event_type.value)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to ALL events (useful for audit trail)."""
        self._global_handlers.append(handler)

    async def publish(self, event: Event) -> None:
        """Publish event to all matching handlers. Non-blocking."""
        module_name, _, action_name = event.type.value.partition(".")
        increment_module_action(module=module_name, action=action_name or "event")

        logger.info(
            "event_published",
            event_type=event.type.value,
            event_id=event.event_id,
            user_id=str(event.user_id) if event.user_id else None,
        )

        handlers = self._handlers.get(event.type, []) + self._global_handlers
        if not handlers:
            return

        # Fire all handlers concurrently, don't let one failure kill others
        results = await asyncio.gather(
            *[self._safe_call(h, event) for h in handlers],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "event_handler_failed",
                    event_type=event.type.value,
                    handler=handlers[i].__name__,
                    error=str(result),
                )

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.exception("event_handler_exception", error=str(e))
            raise


# ── Global singleton ─────────────────────────────────────────────
event_bus = EventBus()
