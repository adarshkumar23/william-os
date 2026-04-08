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
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    refresh_token: str | None = None


class UserProfile(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str
    display_name: str | None
    role: str
    timezone: str
    wake_time: str | None
    sleep_time: str
    sleep_goal: int | None
    focus_areas: list[str] = Field(default_factory=list)
    onboarding_completed: bool = False
    is_verified: bool
    totp_enabled: bool
    permission_scopes: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    timezone: str | None = None
    wake_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    sleep_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    preferences: dict | None = None


class OnboardingStatusResponse(BaseModel):
    onboarding_completed: bool


class OnboardingCompleteRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    wake_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    sleep_goal: int = Field(ge=5, le=12)
    focus_areas: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("focus_areas")
    @classmethod
    def normalize_focus_areas(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip().lower() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("At least one focus area is required")
        return sorted(list(dict.fromkeys(cleaned)))


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class TotpSetupResponse(BaseModel):
    otp_auth_url: str
    qr_code_data_url: str
    secret_preview: str


class TotpVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class SessionDeviceResponse(BaseModel):
    id: UUID
    device_name: str
    device_type: str
    device_fingerprint: str
    last_active: datetime | None
    is_active: bool
    created_at: datetime
    is_current: bool = False

    model_config = {"from_attributes": True}


class LoginHistoryResponse(BaseModel):
    id: UUID
    ip: str | None
    country: str | None
    device_fingerprint: str
    user_agent: str | None
    success: bool
    timestamp: datetime

    model_config = {"from_attributes": True}
