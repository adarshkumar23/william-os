"""WILLIAM OS - Calendar schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarEventResponse(BaseModel):
    id: str
    source: str
    title: str
    start_time: datetime
    end_time: datetime
    location: str | None = None
    description: str | None = None


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str


class ConnectionStatusResponse(BaseModel):
    connected: bool
    provider: str


class GoogleCreateEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_time: datetime
    end_time: datetime
    location: str | None = Field(default=None, max_length=500)
    description: str | None = None


class AppleConnectRequest(BaseModel):
    apple_id: str = Field(min_length=3, max_length=255)
    app_password: str = Field(min_length=3, max_length=255)
    caldav_url: str = Field(default="https://caldav.icloud.com", min_length=10, max_length=255)


class AppleCreateEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_time: datetime
    end_time: datetime
    location: str | None = Field(default=None, max_length=500)
    description: str | None = None


class CalendarTokenResponse(BaseModel):
    id: UUID
    user_id: UUID
    token_expiry: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
