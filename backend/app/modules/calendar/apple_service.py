from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from .models import AppleCredential, CachedEvent

def connect_apple(db: Session, user_id: int, apple_id: str, app_password: str) -> dict:
    try:
        import caldav
        client = caldav.DAVClient(url="https://caldav.icloud.com",
                                  username=apple_id, password=app_password)
        client.principal().calendars()
    except Exception as e:
        raise Exception(f"Could not connect to iCloud: {str(e)}")
    cred = db.query(AppleCredential).filter_by(user_id=user_id).first()
    if not cred:
        cred = AppleCredential(user_id=user_id)
        db.add(cred)
    cred.apple_id_encrypted = apple_id
    cred.app_password_encrypted = app_password
    db.commit()
    return {"status": "connected"}

def fetch_events(db: Session, user_id: int, days: int = 7) -> List[dict]:
    try:
        import caldav
        cred = db.query(AppleCredential).filter_by(user_id=user_id).first()
        if not cred:
            return []
        client = caldav.DAVClient(url="https://caldav.icloud.com",
                                  username=cred.apple_id_encrypted,
                                  password=cred.app_password_encrypted)
        principal = client.principal()
        calendars = principal.calendars()
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        events = []
        for calendar in calendars:
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
        _cache_events(db, user_id, "apple", events)
        return events
    except Exception:
        return []

def is_connected(db: Session, user_id: int) -> bool:
    cred = db.query(AppleCredential).filter_by(user_id=user_id).first()
    return bool(cred and cred.apple_id_encrypted)

def disconnect(db: Session, user_id: int):
    db.query(AppleCredential).filter_by(user_id=user_id).delete()
    db.commit()

def _cache_events(db: Session, user_id: int, source: str, events: List[dict]):
    db.query(CachedEvent).filter_by(user_id=user_id, source=source).delete()
    for e in events:
        db.add(CachedEvent(user_id=user_id, source=source, event_id=e.get("id"),
                           title=e.get("title")))
    db.commit()
