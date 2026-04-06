"""
WILLIAM OS — Event-to-WebSocket Sync Bridge
Broadcast key event-bus updates to all active user devices.
"""

from __future__ import annotations

import structlog

from app.core.events import Event, EventType, event_bus
from app.core.websocket import connection_manager

logger = structlog.get_logger(__name__)

EVENT_TO_MESSAGE_TYPE: dict[EventType, str] = {
    EventType.SCHEDULE_GENERATED: "schedule_updated",
    EventType.SCHEDULE_RESCHEDULED: "schedule_updated",
    EventType.SCHEDULE_ITEM_COMPLETED: "block_completed",
    EventType.HABIT_CHECKED_IN: "habit_checked_in",
    EventType.MEDICINE_TAKEN: "medicine_logged",
    EventType.JOURNAL_ENTRY_CREATED: "journal_created",
}


class SyncBroadcaster:
    def __init__(self) -> None:
        self._registered = False

    def register(self) -> None:
        if self._registered:
            return

        for event_type in EVENT_TO_MESSAGE_TYPE:
            event_bus.subscribe(event_type, self._handle_event)

        self._registered = True
        logger.info("sync_broadcaster_registered")

    async def _handle_event(self, event: Event) -> None:
        if event.user_id is None:
            return

        message_type = EVENT_TO_MESSAGE_TYPE.get(event.type)
        if message_type is None:
            return

        await connection_manager.broadcast(
            user_id=event.user_id,
            message={
                "type": message_type,
                "event_type": event.type.value,
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
            },
        )


sync_broadcaster = SyncBroadcaster()


def register_sync_broadcaster() -> None:
    sync_broadcaster.register()
