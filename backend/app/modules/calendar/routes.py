import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id

from . import apple_service, google_service, native_service

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar"])


class CreateEventRequest(BaseModel):
    title: str
    start: str
    end: str
    description: str | None = ""
    location: str | None = ""


class AppleConnectRequest(BaseModel):
    apple_id: str
    app_password: str


class NativeEventCreateRequest(BaseModel):
    title: str
    start: str
    end: str
    description: str | None = ""
    location: str | None = ""


class NativeEventUpdateRequest(BaseModel):
    title: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None
    location: str | None = None


# ── Google ──────────────────────────────────────────────────────


@router.get("/google/auth-url")
async def google_auth_url(user_id: uuid.UUID = Depends(get_current_user_id)):
    url = google_service.get_auth_url(user_id)
    return {"auth_url": url}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...), state: str = Query(...), db: AsyncSession = Depends(get_db)
):
    try:
        await google_service.exchange_code(code, db, state)
        return RedirectResponse(url="https://williamos.duckdns.org/settings?calendar=connected")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/google/events")
async def google_events(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    events = await google_service.fetch_events(db, user_id, days)
    return {"events": events, "count": len(events)}


@router.post("/google/events")
async def google_create_event(
    payload: CreateEventRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    result = await google_service.create_event(
        db,
        user_id,
        payload.title,
        payload.start,
        payload.end,
        payload.description,
        payload.location,
    )
    return result


@router.delete("/google/events/{event_id}")
async def google_delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return await google_service.delete_event(db, user_id, event_id)


@router.get("/google/status")
async def google_status(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    return {"connected": await google_service.is_connected(db, user_id)}


@router.delete("/google/disconnect")
async def google_disconnect(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    await google_service.disconnect(db, user_id)
    return {"status": "disconnected"}


# ── Apple ──────────────────────────────────────────────────────


@router.post("/apple/connect")
async def apple_connect(
    payload: AppleConnectRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        return await apple_service.connect_apple(
            db, user_id, payload.apple_id, payload.app_password
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/apple/events")
async def apple_events(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    events = await apple_service.fetch_events(db, user_id, days)
    return {"events": events, "count": len(events)}


@router.get("/apple/status")
async def apple_status(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    return {"connected": await apple_service.is_connected(db, user_id)}


@router.delete("/apple/disconnect")
async def apple_disconnect(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    await apple_service.disconnect(db, user_id)
    return {"status": "disconnected"}


# ── Native ─────────────────────────────────────────────────────


@router.get("/native/events")
async def native_events(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    events = await native_service.list_events(db=db, user_id=user_id, days=days)
    return {"events": events, "count": len(events)}


@router.post("/native/events")
async def native_create_event(
    payload: NativeEventCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        created = await native_service.create_event(
            db=db,
            user_id=user_id,
            title=payload.title,
            start=payload.start,
            end=payload.end,
            description=payload.description,
            location=payload.location,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid event payload: {exc}") from exc
    return {"event": created, "status": "created"}


@router.patch("/native/events/{event_id}")
async def native_update_event(
    event_id: str,
    payload: NativeEventUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        updated = await native_service.update_event(
            db=db,
            user_id=user_id,
            event_id=event_id,
            title=payload.title,
            start=payload.start,
            end=payload.end,
            description=payload.description,
            location=payload.location,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid event payload: {exc}") from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="Native event not found")
    return {"event": updated, "status": "updated"}


@router.delete("/native/events/{event_id}")
async def native_delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    deleted = await native_service.delete_event(db=db, user_id=user_id, event_id=event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Native event not found")
    return {"status": "deleted", "event_id": event_id}


@router.get("/events")
async def list_events(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    events = await native_service.list_events(db=db, user_id=user_id, days=days)
    return {"events": events, "count": len(events)}


@router.post("/events")
async def create_event(
    payload: NativeEventCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        created = await native_service.create_event(
            db=db,
            user_id=user_id,
            title=payload.title,
            start=payload.start,
            end=payload.end,
            description=payload.description,
            location=payload.location,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid event payload: {exc}") from exc
    return {"event": created, "status": "created"}


@router.patch("/events/{event_id}")
async def patch_event(
    event_id: str,
    payload: NativeEventUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        updated = await native_service.update_event(
            db=db,
            user_id=user_id,
            event_id=event_id,
            title=payload.title,
            start=payload.start,
            end=payload.end,
            description=payload.description,
            location=payload.location,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid event payload: {exc}") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"event": updated, "status": "updated"}


@router.delete("/events/{event_id}")
async def remove_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    deleted = await native_service.delete_event(db=db, user_id=user_id, event_id=event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted", "event_id": event_id}


# ── Unified ─────────────────────────────────────────────────────


@router.get("/today")
async def today_events(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    native = await native_service.list_today_events(db=db, user_id=user_id)
    return {"events": native}


@router.get("/upcoming")
async def upcoming_events(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    g = await google_service.fetch_events(db, user_id, days)
    a = await apple_service.fetch_events(db, user_id, days)
    native_events = await native_service.list_events(db=db, user_id=user_id, days=days)

    all_events = sorted(g + a + native_events, key=lambda x: x.get("start", ""))
    return {"events": all_events, "count": len(all_events)}


@router.post("/sync/google-to-william")
async def sync_google_to_william(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    payload = await google_service.sync_to_william_schedule(db, user_id)
    return payload


@router.post("/sync/william-to-google")
async def sync_william_to_google(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    payload = await google_service.push_william_to_google(db, user_id)
    return payload


@router.get("/sync/conflicts")
async def sync_conflicts(
    db: AsyncSession = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
):
    payload = await google_service.detect_conflicts(db, user_id)
    return {"conflicts": payload, "count": len(payload)}
