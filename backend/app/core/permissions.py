"""WILLIAM OS - Scope enforcement middleware (C2 fix: reject unauth instead of bypass)."""

from __future__ import annotations

from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_token_safe

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

# Paths that are allowed to skip scope enforcement even on /api/v1/ (auth flows, health).
PUBLIC_PATH_PREFIXES = ("/api/v1/auth",)


def default_scopes_for_role(role: str) -> list[str]:
    n = role.strip().lower()
    if n == "owner":
        return ["admin:*"]
    modules = list(MODULE_SCOPE_BY_PATH.values())
    if n == "family":
        scopes = [f"read:{m}" for m in modules]
        scopes.extend(
            [
                f"write:{m}"
                for m in [
                    "habits",
                    "journal",
                    "medicine",
                    "study",
                    "fitness",
                    "sleep",
                    "decisions",
                    "messaging",
                    "rules",
                ]
            ]
        )
        return scopes
    return [f"read:{m}" for m in modules]


def resolve_required_scope(path: str, method: str) -> str | None:
    if not path.startswith("/api/v1/"):
        return None
    root = path.removeprefix("/api/v1/").split("/", 1)[0]
    module = MODULE_SCOPE_BY_PATH.get(root)
    if module is None:
        return None
    action = "write" if method.upper() in WRITE_METHODS else "read"
    return f"{action}:{module}"


def has_scope(scopes: list[str], required: str) -> bool:
    s = set(scopes)
    if "admin:*" in s or required in s:
        return True
    action, _, module = required.partition(":")
    return f"{action}:*" in s or f"*:{module}" in s


def _reject(status: int, error: str, meta: dict | None = None) -> ORJSONResponse:
    body: dict = {"ok": False, "data": None, "error": error}
    if meta:
        body["meta"] = meta
    return ORJSONResponse(status_code=status, content=body)


class ScopeEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforce JWT scope claims on API endpoints. Reject unauthenticated requests to scoped paths."""

    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/v1/"):
            return await call_next(request)
        if any(path.startswith(p) for p in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        required = resolve_required_scope(path=path, method=request.method)
        if required is None:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return _reject(401, "Authorization required", {"required_scope": required})

        token = auth[7:]
        # wos- prefixed tokens are API keys — let the route's get_current_user_id verify them,
        # but still check: we do not have scope info in API keys, so we grant read access only.
        if token.startswith("wos-"):
            if request.method.upper() in WRITE_METHODS:
                return _reject(403, "API keys have read-only scope", {"required_scope": required})
            return await call_next(request)

        payload = decode_token_safe(token)
        if payload is None:
            return _reject(401, "Invalid or expired token", {"required_scope": required})

        role = str(payload.get("role", "")).lower()
        scope_claim = payload.get("scopes") or []
        scopes = scope_claim if isinstance(scope_claim, list) else []

        if role == "owner" or has_scope(scopes, required):
            return await call_next(request)

        return _reject(403, "Insufficient scope", {"required_scope": required})
