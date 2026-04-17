"""Native calendar event service (William-owned events)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from .models import WilliamEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def parse_datetime(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Datetime string is required")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def serialize_event(event: WilliamEvent) -> dict:
    start = event.start_time.isoformat() if event.start_time else ""
    end = event.end_time.isoformat() if event.end_time else ""
    return {
        "id": str(event.event_id or event.id),
        "title": event.title,
        "start": start,
        "end": end,
        "source": "native",
        "location": event.location,
        "description": event.description,
    }


async def list_events(db: AsyncSession, user_id: uuid.UUID, days: int = 30) -> list[dict]:
    now = _utcnow_naive()
    end = now + timedelta(days=max(1, min(days, 365)))

    result = await db.execute(
        select(WilliamEvent)
        .where(WilliamEvent.user_id == str(user_id))
        .where(WilliamEvent.source == "native")
        .where(WilliamEvent.start_time < end)
        .where(WilliamEvent.end_time >= now)
        .order_by(WilliamEvent.start_time.asc())
    )
    rows = result.scalars().all()
    return [serialize_event(row) for row in rows]


async def list_today_events(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    today = _utcnow_naive().date()
    day_start = datetime.combine(today, time.min)
    day_end = day_start + timedelta(days=1)
    result = await db.execute(
        select(WilliamEvent)
        .where(WilliamEvent.user_id == str(user_id))
        .where(WilliamEvent.source == "native")
        .where(WilliamEvent.start_time >= day_start)
        .where(WilliamEvent.start_time < day_end)
        .order_by(WilliamEvent.start_time.asc())
    )
    rows = result.scalars().all()
    return [serialize_event(row) for row in rows]


async def create_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    start: str,
    end: str,
    description: str | None = "",
    location: str | None = "",
) -> dict:
    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end)
    if end_dt <= start_dt:
        raise ValueError("end must be after start")

    row = WilliamEvent(
        user_id=str(user_id),
        source="native",
        event_id=uuid.uuid4().hex,
        title=(title or "Untitled Event").strip() or "Untitled Event",
        start_time=start_dt,
        end_time=end_dt,
        location=(location or "").strip() or None,
        description=(description or "").strip() or None,
        last_synced=_utcnow_naive(),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return serialize_event(row)


async def update_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_id: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> dict | None:
    result = await db.execute(
        select(WilliamEvent)
        .where(WilliamEvent.user_id == str(user_id))
        .where(WilliamEvent.source == "native")
        .where(WilliamEvent.event_id == event_id)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    if title is not None:
        row.title = title.strip() or row.title
    if location is not None:
        row.location = location.strip() or None
    if description is not None:
        row.description = description.strip() or None
    if start is not None:
        row.start_time = parse_datetime(start)
    if end is not None:
        row.end_time = parse_datetime(end)

    if row.start_time and row.end_time and row.end_time <= row.start_time:
        raise ValueError("end must be after start")

    row.last_synced = _utcnow_naive()
    await db.flush()
    await db.refresh(row)
    return serialize_event(row)


async def delete_event(db: AsyncSession, user_id: uuid.UUID, event_id: str) -> bool:
    result = await db.execute(
        select(WilliamEvent)
        .where(WilliamEvent.user_id == str(user_id))
        .where(WilliamEvent.source == "native")
        .where(WilliamEvent.event_id == event_id)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False

    await db.delete(row)
    await db.flush()
    return True


async def events_for_date(db: AsyncSession, user_id: uuid.UUID, target_date: date) -> list[dict]:
    day_start = datetime.combine(target_date, time.min)
    day_end = day_start + timedelta(days=1)
    result = await db.execute(
        select(WilliamEvent)
        .where(WilliamEvent.user_id == str(user_id))
        .where(WilliamEvent.source == "native")
        .where(WilliamEvent.start_time >= day_start)
        .where(WilliamEvent.start_time < day_end)
        .order_by(WilliamEvent.start_time.asc())
    )
    rows = result.scalars().all()
    return [serialize_event(item) for item in rows]
