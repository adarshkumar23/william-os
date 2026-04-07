import os
import requests
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from .models import GoogleToken, CachedEvent

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
SCOPES = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


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
    resp = requests.post(TOKEN_URL, data={
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
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
    token.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
    await db.commit()
    return {"status": "connected"}


async def _get_access_token(db: AsyncSession, user_id) -> Optional[str]:
    result = await db.execute(select(GoogleToken).where(GoogleToken.user_id == str(user_id)))
    token = result.scalar_one_or_none()
    if not token or not token.access_token:
        return None
    if token.token_expiry and datetime.utcnow() > token.token_expiry:
        if not token.refresh_token:
            return None
        resp = requests.post(TOKEN_URL, data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": token.refresh_token,
            "grant_type": "refresh_token",
        })
        data = resp.json()
        if "access_token" in data:
            token.access_token = data["access_token"]
            token.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
            await db.commit()
    return token.access_token


async def fetch_events(db: AsyncSession, user_id, days: int = 7) -> List[dict]:
    try:
        access_token = await _get_access_token(db, user_id)
        if not access_token:
            return []
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        resp = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"timeMin": now.isoformat()+"Z", "timeMax": end.isoformat()+"Z",
                    "maxResults": 50, "singleEvents": True, "orderBy": "startTime"}
        )
        events = []
        for item in resp.json().get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            end_t = item["end"].get("dateTime", item["end"].get("date", ""))
            events.append({"id": item.get("id"), "title": item.get("summary", "No title"),
                           "start": start, "end": end_t, "location": item.get("location", ""),
                           "description": item.get("description", ""), "source": "google"})
        await _cache_events(db, user_id, events)
        return events
    except Exception:
        return []


async def create_event(db: AsyncSession, user_id, title, start, end, description="", location="") -> dict:
    access_token = await _get_access_token(db, user_id)
    if not access_token:
        raise Exception("Google Calendar not connected")
    resp = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"summary": title, "location": location, "description": description,
              "start": {"dateTime": start, "timeZone": "UTC"},
              "end": {"dateTime": end, "timeZone": "UTC"}}
    )
    data = resp.json()
    return {"id": data.get("id"), "title": title, "status": "created"}


async def delete_event(db: AsyncSession, user_id, event_id) -> dict:
    access_token = await _get_access_token(db, user_id)
    if not access_token:
        raise Exception("Google Calendar not connected")
    requests.delete(
        f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",
        headers={"Authorization": f"Bearer {access_token}"}
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
    await db.execute(delete(CachedEvent).where(
        CachedEvent.user_id == str(user_id), CachedEvent.source == "google"))
    for e in events:
        db.add(CachedEvent(user_id=str(user_id), source="google",
                           event_id=e.get("id"), title=e.get("title"),
                           location=e.get("location"), description=e.get("description")))
    await db.commit()
