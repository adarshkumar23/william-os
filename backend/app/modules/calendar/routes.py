import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from . import google_service, apple_service
from .models import CachedEvent

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar"])

class CreateEventRequest(BaseModel):
    title: str
    start: str
    end: str
    description: Optional[str] = ""
    location: Optional[str] = ""

class AppleConnectRequest(BaseModel):
    apple_id: str
    app_password: str

# ── Google ──────────────────────────────────────────────────────

@router.get("/google/auth-url")
def google_auth_url(user_id: uuid.UUID = Depends(get_current_user_id)):
    url = google_service.get_auth_url()
    return {"auth_url": url}

@router.get("/google/callback")
def google_callback(code: str = Query(...), db: AsyncSession = Depends(get_db),
                    user_id: uuid.UUID = Depends(get_current_user_id)):
    try:
        google_service.exchange_code(code, db, user_id)
        return RedirectResponse(url="https://williamos.duckdns.org/settings?calendar=connected")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/google/events")
def google_events(days: int = 7, db: AsyncSession = Depends(get_db),
                  user_id: uuid.UUID = Depends(get_current_user_id)):
    events = google_service.fetch_events(db, user_id, days)
    return {"events": events, "count": len(events)}

@router.post("/google/events")
def google_create_event(payload: CreateEventRequest, db: AsyncSession = Depends(get_db),
                        user_id: uuid.UUID = Depends(get_current_user_id)):
    result = google_service.create_event(db, user_id, payload.title,
                                         payload.start, payload.end,
                                         payload.description, payload.location)
    return result

@router.delete("/google/events/{event_id}")
def google_delete_event(event_id: str, db: AsyncSession = Depends(get_db),
                        user_id: uuid.UUID = Depends(get_current_user_id)):
    return google_service.delete_event(db, user_id, event_id)

@router.get("/google/status")
def google_status(db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)):
    return {"connected": google_service.is_connected(db, user_id)}

@router.delete("/google/disconnect")
def google_disconnect(db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)):
    google_service.disconnect(db, user_id)
    return {"status": "disconnected"}

# ── Apple ──────────────────────────────────────────────────────

@router.post("/apple/connect")
def apple_connect(payload: AppleConnectRequest, db: AsyncSession = Depends(get_db),
                  user_id: uuid.UUID = Depends(get_current_user_id)):
    try:
        return apple_service.connect_apple(db, user_id,
                                           payload.apple_id, payload.app_password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/apple/events")
def apple_events(days: int = 7, db: AsyncSession = Depends(get_db),
                 user_id: uuid.UUID = Depends(get_current_user_id)):
    events = apple_service.fetch_events(db, user_id, days)
    return {"events": events, "count": len(events)}

@router.get("/apple/status")
def apple_status(db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)):
    return {"connected": apple_service.is_connected(db, user_id)}

@router.delete("/apple/disconnect")
def apple_disconnect(db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)):
    apple_service.disconnect(db, user_id)
    return {"status": "disconnected"}

# ── Unified ─────────────────────────────────────────────────────

@router.get("/today")
def today_events(db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)):
    today = datetime.utcnow().date()
    events = db.query(CachedEvent).filter(
        CachedEvent.user_id == user_id,
        CachedEvent.start_time >= datetime.combine(today, datetime.min.time()),
        CachedEvent.start_time < datetime.combine(today, datetime.max.time())
    ).order_by(CachedEvent.start_time).all()
    return {"events": [{"id": e.id, "title": e.title, "start": str(e.start_time),
                        "end": str(e.end_time), "source": e.source,
                        "location": e.location} for e in events]}

@router.get("/upcoming")
def upcoming_events(days: int = 7, db: AsyncSession = Depends(get_db),
                    user_id: uuid.UUID = Depends(get_current_user_id)):
    g = google_service.fetch_events(db, user_id, days)
    a = apple_service.fetch_events(db, user_id, days)
    all_events = sorted(g + a, key=lambda x: x.get("start", ""))
    return {"events": all_events, "count": len(all_events)}
