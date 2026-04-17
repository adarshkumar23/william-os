"""Google OAuth helpers for calendar integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from google_auth_oauthlib.flow import Flow

from app.core.config import get_settings
from app.shared.types import AuthenticationError, ValidationError

settings = get_settings()


_GOOGLE_CLIENT_CONFIG = {
    "web": {
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "",
        "client_secret": "",
    }
}


def _scopes() -> list[str]:
    raw = settings.google_calendar_scopes.strip()
    return [scope.strip() for scope in raw.split(",") if scope.strip()]


def _new_flow(state: str | None = None) -> Flow:
    client_id = settings.google_client_id.strip()
    client_secret = settings.google_client_secret.get_secret_value().strip()
    if not client_id or not client_secret:
        raise ValidationError("Google Calendar OAuth is not configured")

    cfg = json.loads(json.dumps(_GOOGLE_CLIENT_CONFIG))
    cfg["web"]["client_id"] = client_id
    cfg["web"]["client_secret"] = client_secret

    flow = Flow.from_client_config(cfg, scopes=_scopes(), state=state)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def create_state_token(user_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "type": "google_calendar_oauth_state",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def parse_state_token(state: str) -> UUID:
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid Google OAuth state") from exc

    if payload.get("type") != "google_calendar_oauth_state":
        raise AuthenticationError("Invalid Google OAuth state type")
    return UUID(payload["sub"])


def authorization_url(user_id: UUID) -> str:
    state = create_state_token(user_id)
    flow = _new_flow(state=state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def exchange_code(code: str, state: str):
    flow = _new_flow(state=state)
    flow.fetch_token(code=code)
    return flow.credentials
