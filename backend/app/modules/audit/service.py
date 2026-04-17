"""
WILLIAM OS — Audit Service
Subscribes to ALL events and persists them as immutable audit logs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import and_, func, select

from app.core.database import async_session_factory
from app.core.events import Event, EventType, event_bus
from app.modules.audit.models import AuditAction, AuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger = structlog.get_logger(__name__)

# Map event types to audit actions
EVENT_TO_ACTION: dict[EventType, AuditAction] = {
    EventType.USER_REGISTERED: AuditAction.USER_REGISTER,
    EventType.USER_LOGGED_IN: AuditAction.USER_LOGIN,
    EventType.SCHEDULE_GENERATED: AuditAction.SCHEDULE_GENERATE,
    EventType.SCHEDULE_RESCHEDULED: AuditAction.SCHEDULE_RESCHEDULE,
    EventType.SCHEDULE_ITEM_COMPLETED: AuditAction.BLOCK_COMPLETE,
    EventType.HABIT_CHECKED_IN: AuditAction.HABIT_CHECK_IN,
    EventType.JOURNAL_ENTRY_CREATED: AuditAction.JOURNAL_CREATE,
    EventType.MEDICINE_TAKEN: AuditAction.MEDICINE_TAKEN,
    EventType.MEDICINE_MISSED: AuditAction.MEDICINE_MISSED,
    # M16: chat executor actions flow through INTEGRATION_TRIGGERED
    EventType.INTEGRATION_TRIGGERED: AuditAction.AI_CALL,
}


async def audit_event_handler(event: Event) -> None:
    """Global event handler — logs every event to audit trail."""
    action = EVENT_TO_ACTION.get(event.type)
    if not action:
        # H15: removed dead code; skip cleanly for unmapped events
        logger.debug("audit_unmapped_event", event_type=event.type.value)
        return

    try:
        async with async_session_factory() as session:
            log = AuditLog(
                user_id=event.user_id,
                action=action,
                details=event.data,
                module=event.type.value.split(".")[0],
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.error("audit_log_failed", error=str(e), event_type=event.type.value)


def register_audit_handlers() -> None:
    """Subscribe to all events. Called at app startup."""
    event_bus.subscribe_all(audit_event_handler)
    logger.info("audit_handlers_registered")


class AuditService:
    """Query audit logs for display and export."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_logs(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        action_filter: AuditAction | None = None,
        module_filter: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        query = select(AuditLog).where(AuditLog.user_id == user_id)

        if action_filter:
            query = query.where(AuditLog.action == action_filter)
        if module_filter:
            query = query.where(AuditLog.module == module_filter)
        if date_from:
            query = query.where(
                AuditLog.created_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to:
            query = query.where(
                AuditLog.created_at <= datetime.combine(date_to, datetime.max.time())
            )

        query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        logs = result.scalars().all()

        return [
            {
                "id": str(log.id),
                "action": log.action.value,
                "module": log.module,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    async def get_stats(self, user_id: uuid.UUID, days: int = 30) -> dict:
        """Aggregate audit stats for dashboard."""
        cutoff = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        ) - timedelta(days=days)
        result = await self.db.execute(
            select(AuditLog.action, func.count())
            .where(and_(AuditLog.user_id == user_id, AuditLog.created_at >= cutoff))
            .group_by(AuditLog.action)
        )
        return {row[0].value: row[1] for row in result.all()}
