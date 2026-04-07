from datetime import datetime, timedelta
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from .models import AppleCredential, CachedEvent


async def connect_apple(db: AsyncSession, user_id, apple_id: str, app_password: str) -> dict:
    try:
        import caldav
        client = caldav.DAVClient(url="https://caldav.icloud.com",
                                  username=apple_id, password=app_password)
        client.principal().calendars()
    except Exception as e:
        raise Exception(f"Could not connect to iCloud: {str(e)}")
    result = await db.execute(select(AppleCredential).where(AppleCredential.user_id == str(user_id)))
    cred = result.scalar_one_or_none()
    if not cred:
        cred = AppleCredential(user_id=str(user_id))
        db.add(cred)
    cred.apple_id_encrypted = apple_id
    cred.app_password_encrypted = app_password
    await db.commit()
    return {"status": "connected"}


async def fetch_events(db: AsyncSession, user_id, days: int = 7) -> List[dict]:
    try:
        import caldav
        result = await db.execute(select(AppleCredential).where(AppleCredential.user_id == str(user_id)))
        cred = result.scalar_one_or_none()
        if not cred:
            return []
        client = caldav.DAVClient(url="https://caldav.icloud.com",
                                  username=cred.apple_id_encrypted,
                                  password=cred.app_password_encrypted)
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        events = []
        for calendar in client.principal().calendars():
            try:
                for event in calendar.date_search(start=now, end=end, expand=True):
                    comp = event.vobject_instance.vevent
                    title = str(comp.summary.value) if hasattr(comp, "summary") else "No title"
                    start = comp.dtstart.value if hasattr(comp, "dtstart") else None
                    end_t = comp.dtend.value if hasattr(comp, "dtend") else None
                    uid = str(comp.uid.value) if hasattr(comp, "uid") else ""
                    if isinstance(start, datetime) and start.tzinfo:
                        start = start.replace(tzinfo=None)
                    if isinstance(end_t, datetime) and end_t.tzinfo:
                        end_t = end_t.replace(tzinfo=None)
                    events.append({"id": uid, "title": title,
                                   "start": start.isoformat() if start else "",
                                   "end": end_t.isoformat() if end_t else "",
                                   "source": "apple"})
            except Exception:
                continue
        await _cache_events(db, user_id, events)
        return events
    except Exception:
        return []


async def is_connected(db: AsyncSession, user_id) -> bool:
    result = await db.execute(select(AppleCredential).where(AppleCredential.user_id == str(user_id)))
    cred = result.scalar_one_or_none()
    return bool(cred and cred.apple_id_encrypted)


async def disconnect(db: AsyncSession, user_id):
    await db.execute(delete(AppleCredential).where(AppleCredential.user_id == str(user_id)))
    await db.commit()


async def _cache_events(db: AsyncSession, user_id, events):
    await db.execute(delete(CachedEvent).where(CachedEvent.user_id == str(user_id), CachedEvent.source == "apple"))
    for e in events:
        db.add(CachedEvent(user_id=str(user_id), source="apple",
                           event_id=e.get("id"), title=e.get("title")))
    await db.commit()
