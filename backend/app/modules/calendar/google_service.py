import os
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from .models import GoogleToken, CachedEvent

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

def get_auth_url() -> str:
    flow = Flow.from_client_config(
        {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                 "redirect_uris": [REDIRECT_URI],
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return auth_url

def exchange_code(code: str, db: Session, user_id: int) -> dict:
    flow = Flow.from_client_config(
        {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                 "redirect_uris": [REDIRECT_URI],
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(code=code)
    creds = flow.credentials
    token = db.query(GoogleToken).filter_by(user_id=user_id).first()
    if not token:
        token = GoogleToken(user_id=user_id)
        db.add(token)
    token.access_token = creds.token
    token.refresh_token = creds.refresh_token
    token.token_expiry = creds.expiry
    db.commit()
    return {"status": "connected"}

def _get_credentials(db: Session, user_id: int) -> Optional[Credentials]:
    token = db.query(GoogleToken).filter_by(user_id=user_id).first()
    if not token or not token.access_token:
        return None
    creds = Credentials(
        token=token.access_token, refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scopes=SCOPES)
    if token.token_expiry and datetime.utcnow() > token.token_expiry:
        creds.refresh(Request())
        token.access_token = creds.token
        token.token_expiry = creds.expiry
        db.commit()
    return creds

def fetch_events(db: Session, user_id: int, days: int = 7) -> List[dict]:
    try:
        creds = _get_credentials(db, user_id)
        if not creds:
            return []
        service = build("calendar", "v3", credentials=creds)
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        result = service.events().list(
            calendarId="primary", timeMin=now.isoformat()+"Z",
            timeMax=end.isoformat()+"Z", maxResults=50,
            singleEvents=True, orderBy="startTime").execute()
        events = []
        for item in result.get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            end_t = item["end"].get("dateTime", item["end"].get("date", ""))
            events.append({"id": item.get("id"), "title": item.get("summary", "No title"),
                           "start": start, "end": end_t, "location": item.get("location", ""),
                           "description": item.get("description", ""), "source": "google"})
        _cache_events(db, user_id, "google", events)
        return events
    except Exception:
        return []

def create_event(db: Session, user_id: int, title: str, start: str, end: str,
                 description: str = "", location: str = "") -> dict:
    creds = _get_credentials(db, user_id)
    if not creds:
        raise Exception("Google Calendar not connected")
    service = build("calendar", "v3", credentials=creds)
    event = {"summary": title, "location": location, "description": description,
             "start": {"dateTime": start, "timeZone": "UTC"},
             "end": {"dateTime": end, "timeZone": "UTC"}}
    created = service.events().insert(calendarId="primary", body=event).execute()
    return {"id": created.get("id"), "title": title, "status": "created"}

def delete_event(db: Session, user_id: int, event_id: str) -> dict:
    creds = _get_credentials(db, user_id)
    if not creds:
        raise Exception("Google Calendar not connected")
    service = build("calendar", "v3", credentials=creds)
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return {"status": "deleted"}

def is_connected(db: Session, user_id: int) -> bool:
    token = db.query(GoogleToken).filter_by(user_id=user_id).first()
    return bool(token and token.access_token)

def disconnect(db: Session, user_id: int):
    db.query(GoogleToken).filter_by(user_id=user_id).delete()
    db.commit()

def _cache_events(db: Session, user_id: int, source: str, events: List[dict]):
    db.query(CachedEvent).filter_by(user_id=user_id, source=source).delete()
    for e in events:
        db.add(CachedEvent(user_id=user_id, source=source, event_id=e.get("id"),
                           title=e.get("title"), location=e.get("location"),
                           description=e.get("description")))
    db.commit()
