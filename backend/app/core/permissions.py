"""
WILLIAM OS - Permission scope helpers and middleware enforcement.
"""

from __future__ import annotations

from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_token

MODULE_SCOPE_BY_PATH = {
    "schedule": "scheduler",
    "briefing": "briefing",
    "feed": "feed",
    "agents": "agents",
    "rules": "rules",
    "gamification": "gamification",
    "habits": "habits",
    "journal": "journal",
    "medicine": "medicine",
    "messaging": "messaging",
    "voice": "voice",
    "study": "study",
    "fitness": "fitness",
    "trading": "trading",
    "sleep": "sleep",
    "decisions": "decisions",
    "email": "email",
    "intelligence": "intelligence",
    "memory": "memory",
    "export": "export",
}

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def default_scopes_for_role(role: str) -> list[str]:
    normalized = role.strip().lower()
    if normalized == "owner":
        return ["admin:*"]

    modules = [
        "habits",
        "journal",
        "medicine",
        "study",
        "fitness",
        "trading",
        "sleep",
        "decisions",
        "scheduler",
        "briefing",
        "feed",
        "email",
        "messaging",
        "intelligence",
        "memory",
        "voice",
        "rules",
        "gamification",
        "export",
        "agents",
    ]

    if normalized == "family":
        scopes = [f"read:{module}" for module in modules]
        scopes.extend(
            [
                "write:habits",
                "write:journal",
                "write:medicine",
                "write:study",
                "write:fitness",
                "write:sleep",
                "write:decisions",
                "write:messaging",
                "write:rules",
            ]
        )
        return scopes

    return [f"read:{module}" for module in modules]


def resolve_required_scope(path: str, method: str) -> str | None:
    if not path.startswith("/api/v1/"):
        return None

    tail = path.removeprefix("/api/v1/")
    root = tail.split("/", 1)[0]
    module = MODULE_SCOPE_BY_PATH.get(root)
    if module is None:
        return None

    action = "write" if method.upper() in WRITE_METHODS else "read"
    return f"{action}:{module}"


def has_scope(scopes: list[str], required: str) -> bool:
    scope_set = set(scopes)
    if "admin:*" in scope_set:
        return True
    if required in scope_set:
        return True

    action, _, module = required.partition(":")
    return f"{action}:*" in scope_set or f"*:{module}" in scope_set


class ScopeEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforce JWT scope claims on API endpoints."""

    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/v1/"):
            return await call_next(request)
        if path.startswith("/api/v1/auth"):
            return await call_next(request)

        required_scope = resolve_required_scope(path=path, method=request.method)
        if required_scope is None:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except Exception:
            return await call_next(request)

        role = str(payload.get("role", "")).lower()
        scope_claim = payload.get("scopes") or []
        scopes = scope_claim if isinstance(scope_claim, list) else []

        if role == "owner" or has_scope(scopes, required_scope):
            return await call_next(request)

        return ORJSONResponse(
            status_code=403,
            content={
                "ok": False,
                "data": None,
                "error": "Insufficient scope",
                "meta": {"required_scope": required_scope},
            },
        )
