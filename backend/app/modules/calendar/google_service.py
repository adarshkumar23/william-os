from datetime import UTC, date as date_type, datetime, timedelta
import os
import uuid

import requests
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduler.models import (
    BlockCategory,
    BlockStatus,
    DailyPlan,
    PlanStatus,
    ScheduleBlock,
)

from .models import CachedEvent, GoogleToken

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
SCOPES = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _utcnow_naive() -> datetime:
    return _utcnow().replace(tzinfo=None)


def get_auth_url(user_id) -> str:
    params = (
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={user_id}"
    )
    return AUTH_URL + params


async def exchange_code(code: str, db: AsyncSession, user_id) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    data = resp.json()
    if "error" in data:
        raise Exception(data.get("error_description", data["error"]))
    result = await db.execute(select(GoogleToken).where(GoogleToken.user_id == str(user_id)))
    token = result.scalar_one_or_none()
    if not token:
        token = GoogleToken(user_id=str(user_id))
        db.add(token)
    token.access_token = data.get("access_token")
    token.refresh_token = data.get("refresh_token")
    token.token_expiry = _utcnow_naive() + timedelta(seconds=data.get("expires_in", 3600))
    await db.commit()
    return {"status": "connected"}


async def _get_access_token(db: AsyncSession, user_id) -> str | None:
    result = await db.execute(select(GoogleToken).where(GoogleToken.user_id == str(user_id)))
    token = result.scalar_one_or_none()
    if not token or not token.access_token:
        return None
    if token.token_expiry and _utcnow_naive() > token.token_expiry:
        if not token.refresh_token:
            return None
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        data = resp.json()
        if "access_token" in data:
            token.access_token = data["access_token"]
            token.token_expiry = _utcnow_naive() + timedelta(seconds=data.get("expires_in", 3600))
            await db.commit()
    return token.access_token


async def fetch_events(db: AsyncSession, user_id, days: int = 7) -> list[dict]:
    try:
        access_token = await _get_access_token(db, user_id)
        if not access_token:
            return []
        now = _utcnow()
        end = now + timedelta(days=days)
        resp = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "timeMin": now.isoformat().replace("+00:00", "Z"),
                "timeMax": end.isoformat().replace("+00:00", "Z"),
                "maxResults": 50,
                "singleEvents": True,
                "orderBy": "startTime",
            },
        )
        events = []
        for item in resp.json().get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            end_t = item["end"].get("dateTime", item["end"].get("date", ""))
            events.append(
                {
                    "id": item.get("id"),
                    "title": item.get("summary", "No title"),
                    "start": start,
                    "end": end_t,
                    "location": item.get("location", ""),
                    "description": item.get("description", ""),
                    "source": "google",
                }
            )
        await _cache_events(db, user_id, events)
        return events
    except Exception:
        return []


async def create_event(
    db: AsyncSession, user_id, title, start, end, description="", location=""
) -> dict:
    access_token = await _get_access_token(db, user_id)
    if not access_token:
        raise Exception("Google Calendar not connected")
    resp = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "summary": title,
            "location": location,
            "description": description,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        },
    )
    data = resp.json()
    return {"id": data.get("id"), "title": title, "status": "created"}


async def delete_event(db: AsyncSession, user_id, event_id) -> dict:
    access_token = await _get_access_token(db, user_id)
    if not access_token:
        raise Exception("Google Calendar not connected")
    requests.delete(
        f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return {"status": "deleted"}


async def is_connected(db: AsyncSession, user_id) -> bool:
    result = await db.execute(select(GoogleToken).where(GoogleToken.user_id == str(user_id)))
    token = result.scalar_one_or_none()
    return bool(token and token.access_token)


async def disconnect(db: AsyncSession, user_id):
    await db.execute(delete(GoogleToken).where(GoogleToken.user_id == str(user_id)))
    await db.commit()


async def _cache_events(db: AsyncSession, user_id, events):
    await db.execute(
        delete(CachedEvent).where(
            CachedEvent.user_id == str(user_id), CachedEvent.source == "google"
        )
    )
    for e in events:
        start_time = _parse_google_datetime(e.get("start", ""))
        end_time = _parse_google_datetime(e.get("end", ""))
        db.add(
            CachedEvent(
                user_id=str(user_id),
                source="google",
                event_id=e.get("id"),
                title=e.get("title"),
                start_time=start_time,
                end_time=end_time,
                location=e.get("location"),
                description=e.get("description"),
            )
        )
    await db.commit()


async def sync_to_william_schedule(db: AsyncSession, user_id) -> dict:
    events = await fetch_events(db, user_id, days=7)
    synced = 0
    added = 0
    updated = 0
    removed = 0

    event_map = {str(item.get("id")): item for item in events if item.get("id")}
    event_ids = set(event_map.keys())

    today = _utcnow().date()
    horizon = today + timedelta(days=7)
    existing_result = await db.execute(
        select(ScheduleBlock, DailyPlan)
        .join(DailyPlan, DailyPlan.id == ScheduleBlock.plan_id)
        .where(DailyPlan.user_id == user_id)
        .where(DailyPlan.plan_date >= today)
        .where(DailyPlan.plan_date <= horizon)
        .where(ScheduleBlock.linked_module == "google_calendar")
    )
    existing_rows = existing_result.all()
    existing_by_event_id: dict[str, tuple[ScheduleBlock, DailyPlan]] = {}
    for block, plan in existing_rows:
        event_id = _extract_google_event_id(block.notes)
        if event_id:
            existing_by_event_id[event_id] = (block, plan)

    for event_id, event in event_map.items():
        bounds = _event_bounds(event)
        if bounds is None:
            continue
        start_dt, end_dt = bounds
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=30)

        event_date = start_dt.date()
        plan = await _get_or_create_plan(db, user_id, event_date)

        existing_pair = existing_by_event_id.get(event_id)
        if existing_pair is None:
            block = ScheduleBlock(
                plan_id=plan.id,
                title=str(event.get("title") or "Google Event"),
                description=str(event.get("description") or ""),
                category=BlockCategory.PERSONAL,
                start_time=start_dt.time(),
                end_time=end_dt.time(),
                duration_minutes=max(15, int((end_dt - start_dt).total_seconds() / 60)),
                status=BlockStatus.PENDING,
                priority=2,
                is_fixed=True,
                is_ai_generated=False,
                tags=["external_calendar", "google"],
                linked_module="google_calendar",
                notes=f"google_event_id:{event_id}",
            )
            db.add(block)
            added += 1
            synced += 1
            continue

        block, existing_plan = existing_pair
        if existing_plan.plan_date != event_date:
            block.plan_id = plan.id

        changed = False
        title = str(event.get("title") or "Google Event")
        description = str(event.get("description") or "")
        if block.title != title:
            block.title = title
            changed = True
        if (block.description or "") != description:
            block.description = description
            changed = True
        if block.start_time != start_dt.time() or block.end_time != end_dt.time():
            block.start_time = start_dt.time()
            block.end_time = end_dt.time()
            block.duration_minutes = max(15, int((end_dt - start_dt).total_seconds() / 60))
            changed = True
        if changed:
            updated += 1
            synced += 1

    for event_id, (block, _) in existing_by_event_id.items():
        if event_id in event_ids:
            continue
        await db.delete(block)
        removed += 1
        synced += 1

    await db.flush()
    return {
        "synced": synced,
        "added": added,
        "updated": updated,
        "removed": removed,
    }


async def push_william_to_google(db: AsyncSession, user_id) -> dict:
    today = _utcnow().date()
    plan_result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.user_id == user_id)
        .where(DailyPlan.plan_date == today)
        .order_by(DailyPlan.created_at.desc())
        .limit(1)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        return {"pushed": 0}

    blocks_result = await db.execute(
        select(ScheduleBlock)
        .where(ScheduleBlock.plan_id == plan.id)
        .order_by(ScheduleBlock.start_time.asc())
    )
    blocks = list(blocks_result.scalars().all())

    pushed = 0
    for block in blocks:
        if block.linked_module == "google_calendar":
            continue
        if _extract_google_event_id(block.notes):
            continue

        start_dt = datetime.combine(today, block.start_time)
        end_dt = datetime.combine(today, block.end_time)
        result = await create_event(
            db,
            user_id,
            block.title,
            start_dt.isoformat() + "Z",
            end_dt.isoformat() + "Z",
            block.description or "",
            "",
        )
        event_id = result.get("id")
        if event_id:
            note = block.notes or ""
            prefix = f"google_event_id:{event_id}"
            block.notes = f"{note}\n{prefix}".strip()
            pushed += 1

    await db.flush()
    return {"pushed": pushed}


async def detect_conflicts(db: AsyncSession, user_id) -> list[dict]:
    events = await fetch_events(db, user_id, days=1)
    today = _utcnow().date()

    plan_result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.user_id == user_id)
        .where(DailyPlan.plan_date == today)
        .order_by(DailyPlan.created_at.desc())
        .limit(1)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        return []

    blocks_result = await db.execute(
        select(ScheduleBlock)
        .where(ScheduleBlock.plan_id == plan.id)
        .where(ScheduleBlock.linked_module != "google_calendar")
    )
    blocks = list(blocks_result.scalars().all())

    conflicts: list[dict] = []
    for event in events:
        bounds = _event_bounds(event)
        if bounds is None:
            continue
        event_start, event_end = bounds
        for block in blocks:
            block_start = datetime.combine(today, block.start_time)
            block_end = datetime.combine(today, block.end_time)
            overlap_start = max(block_start, event_start)
            overlap_end = min(block_end, event_end)
            overlap_minutes = int((overlap_end - overlap_start).total_seconds() / 60)
            if overlap_minutes <= 0:
                continue

            conflicts.append(
                {
                    "william_block": (
                        f"{block.title} ({block.start_time.strftime('%H:%M')}-"
                        f"{block.end_time.strftime('%H:%M')})"
                    ),
                    "google_event": (
                        f"{event.get('title', 'Google event')} "
                        f"({event_start.strftime('%H:%M')}-{event_end.strftime('%H:%M')})"
                    ),
                    "overlap_minutes": overlap_minutes,
                }
            )

    return conflicts


def _extract_google_event_id(notes: str | None) -> str | None:
    if not notes:
        return None
    for line in str(notes).splitlines():
        line = line.strip()
        if line.startswith("google_event_id:"):
            return line.split("google_event_id:", 1)[1].strip() or None
    return None


def _parse_google_datetime(value: str) -> datetime:
    if not value:
        return _utcnow_naive()
    value = str(value)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    except Exception:
        try:
            parsed_date = datetime.strptime(value, "%Y-%m-%d")
            return parsed_date
        except Exception:
            return _utcnow_naive()


def _event_bounds(event: dict) -> tuple[datetime, datetime] | None:
    raw_start = str(event.get("start") or "")
    raw_end = str(event.get("end") or "")
    if not raw_start:
        return None
    start = _parse_google_datetime(raw_start)
    end = _parse_google_datetime(raw_end) if raw_end else start + timedelta(hours=1)
    return start, end


async def _get_or_create_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_date: date_type,
) -> DailyPlan:
    result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.user_id == user_id)
        .where(DailyPlan.plan_date == plan_date)
        .order_by(DailyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan is not None:
        return plan

    plan = DailyPlan(
        user_id=user_id,
        plan_date=plan_date,
        status=PlanStatus.ACTIVE,
        generation_model="google-sync",
        context_snapshot={"source": "google_calendar"},
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan
