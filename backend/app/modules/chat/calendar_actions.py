"""Calendar action executor for William chat actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.modules.calendar import native_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _parse_naive_datetime(raw: str) -> datetime:
    value = (raw or "").strip()
    if not value:
        raise ValueError("datetime value is required")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _format_datetime(dt: datetime) -> str:
    hour = dt.strftime("%I").lstrip("0") or "0"
    return f"{dt.strftime('%b')} {dt.day} at {hour}{dt.strftime('%p').lower()}"


def _parse_event_start(raw: str) -> datetime | None:
    value = (raw or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


async def execute_calendar_action(
    action_json: dict,
    db: AsyncSession,
    user_id,
) -> str:
    action_type = str(action_json.get("type") or "").strip().lower()

    try:
        if action_type == "calendar_create":
            title = str(action_json.get("title") or "Untitled Event").strip()
            start_dt = _parse_naive_datetime(str(action_json.get("start") or ""))
            end_dt = _parse_naive_datetime(str(action_json.get("end") or ""))
            description = str(action_json.get("description") or "")
            location = str(action_json.get("location") or "")

            if end_dt <= start_dt:
                return "Could not create event: end time must be after start time."

            await native_service.create_event(
                db=db,
                user_id=user_id,
                title=title,
                start=start_dt.isoformat(),
                end=end_dt.isoformat(),
                description=description,
                location=location,
            )
            return f"Created event '{title}' on {_format_datetime(start_dt)} ✅"

        if action_type == "calendar_list":
            days = int(action_json.get("days") or 7)
            days = max(1, min(30, days))
            events = await native_service.list_events(db=db, user_id=user_id, days=days)
            if not events:
                return "No upcoming calendar events found."

            lines = ["Here is your upcoming schedule:"]
            for item in events[:10]:
                title = str(item.get("title") or "Untitled")
                event_id = str(item.get("id") or "")
                start_dt = _parse_event_start(str(item.get("start") or ""))
                when = _format_datetime(start_dt) if start_dt else "Unknown time"
                if event_id:
                    lines.append(f"- {when} · {title} (ID: {event_id})")
                else:
                    lines.append(f"- {when} · {title}")
            return "\n".join(lines)

        if action_type == "calendar_delete":
            event_id = str(action_json.get("event_id") or "").strip()
            if not event_id:
                return "Could not remove event: missing event_id."

            deleted = await native_service.delete_event(db=db, user_id=user_id, event_id=event_id)
            if not deleted:
                return "Could not remove event: event was not found."
            return "Removed event ✅"

        return "That calendar action is not supported yet."
    except Exception as exc:
        logger.warning(
            "chat_calendar_action_failed",
            user_id=str(user_id),
            action_type=action_type,
            error=str(exc),
        )
        return "I could not complete that calendar action right now."
