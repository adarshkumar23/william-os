"""
WILLIAM OS — Shared Types
API response envelope, custom exceptions, common schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel

T = TypeVar("T")


# ── API Response Envelope ────────────────────────────────────────

class APIResponse(BaseModel, Generic[T]):
    """Every API response uses this envelope."""
    ok: bool = True
    data: T | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None


def success(data: Any = None, meta: dict | None = None) -> dict:
    return {"ok": True, "data": data, "error": None, "meta": meta}


def error(message: str, meta: dict | None = None) -> dict:
    return {"ok": False, "data": None, "error": message, "meta": meta}


# ── Pagination ───────────────────────────────────────────────────

class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None


# ── Custom Exceptions ────────────────────────────────────────────

class WilliamError(Exception):
    """Base exception for WILLIAM OS."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(WilliamError):
    def __init__(self, resource: str, resource_id: str | UUID):
        super().__init__(f"{resource} '{resource_id}' not found", "NOT_FOUND")


class AuthenticationError(WilliamError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, "AUTH_FAILED")


class AuthorizationError(WilliamError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "FORBIDDEN")


class ValidationError(WilliamError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class RateLimitError(WilliamError):
    def __init__(self):
        super().__init__("Rate limit exceeded", "RATE_LIMITED")


class EncryptionError(WilliamError):
    def __init__(self, message: str = "Decryption failed — wrong passphrase?"):
        super().__init__(message, "ENCRYPTION_ERROR")


# ── Common Schemas ───────────────────────────────────────────────

class HealthCheck(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    timestamp: datetime
