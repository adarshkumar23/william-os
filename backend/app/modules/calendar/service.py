"""Unified calendar service (Google + Apple)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from app.modules.calendar.apple_service import AppleCalendarService
from app.modules.calendar.google_service import GoogleCalendarService
from app.modules.calendar.schemas import CalendarEventResponse
from sqlalchemy.ext.asyncio import AsyncSession


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.google = GoogleCalendarService(db)
        self.apple = AppleCalendarService(db)

    async def today(self, user_id: uuid.UUID) -> list[CalendarEventResponse]:
        start = datetime.combine(date.today(), time.min)
        end = start + timedelta(days=1)
        events = await self.upcoming(user_id=user_id, days=7)
        return [event for event in events if event.start_time < end and event.end_time > start]

    async def upcoming(self, user_id: uuid.UUID, days: int = 7) -> list[CalendarEventResponse]:
        merged: list[CalendarEventResponse] = []

        try:
            if await self.google.status(user_id):
                merged.extend(await self.google.list_events(user_id=user_id, days=days))
        except Exception:
            pass

        try:
            if await self.apple.status(user_id):
                merged.extend(await self.apple.list_events(user_id=user_id, days=days))
        except Exception:
            pass

        merged.sort(key=lambda item: item.start_time)
        return merged
