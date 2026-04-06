"""
WILLIAM OS — Auth Schemas
Request/response models for authentication endpoints.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    timezone: str = "Asia/Kolkata"

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    device_name: str = "Unknown Device"
    device_type: str = "web"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str
    role: str
    timezone: str
    wake_time: str
    sleep_time: str
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    timezone: str | None = None
    wake_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    sleep_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    preferences: dict | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
