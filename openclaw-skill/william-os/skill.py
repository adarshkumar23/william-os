"""OpenClaw skill: WILLIAM OS gateway command router (hardened)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

TIMEOUT = int(os.getenv("WILLIAM_GATEWAY_TIMEOUT_SECONDS", "20"))
MAX_RETRIES = int(os.getenv("WILLIAM_GATEWAY_MAX_RETRIES", "3"))
BASE_URL = os.getenv("WILLIAM_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
TOKEN = os.getenv("WILLIAM_GATEWAY_BEARER_TOKEN", "")

COMMANDS: dict[str, tuple[str, str]] = {
    "/today": ("GET", "/schedule/today"),
    "/habits": ("GET", "/habits?active_only=true&limit=20&offset=0"),
    "/sleep": ("GET", "/sleep/stats"),
    "/briefing": ("GET", "/briefing"),
    "/score": ("GET", "/intelligence/life-score"),
    "/burnout": ("GET", "/intelligence/burnout/score"),
    "/warnings": ("GET", "/intelligence/warnings"),
    "/study": ("GET", "/study/dashboard"),
    "/health": ("GET", "/health"),
}


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.request(
                    method,
                    f"{BASE_URL}{path}",
                    json=payload,
                    headers=_headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if attempt == retries - 1:
                return {
                    "ok": False,
                    "error": f"http_{exc.response.status_code}",
                    "data": None,
                }
            time.sleep(2**attempt)
        except Exception as exc:
            if attempt == retries - 1:
                return {"ok": False, "error": str(exc), "data": None}
            time.sleep(2**attempt)
    return {"ok": False, "error": "max_retries_exceeded", "data": None}


def _format(cmd: str, payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"

    data = payload.get("data")
    if cmd == "/today":
        blocks = (data or {}).get("blocks") or []
        if not blocks:
            return "No blocks scheduled today."
        lines = ["Today:"]
        for block in blocks[:10]:
            lines.append(
                f"- {str(block.get('start_time', '--:--'))[:5]} {block.get('title', 'Untitled')}"
            )
        return "\n".join(lines)

    if cmd == "/warnings":
        items = data or []
        if not items:
            return "No active warnings."
        lines = ["Warnings:"]
        for item in items[:5]:
            lines.append(
                f"- {item.get('warning_type', 'warning')}: {item.get('recommended_action', 'review')}"
            )
        return "\n".join(lines)

    return json.dumps(data, indent=2, ensure_ascii=True)[:1200]


def handle_message(
    text: str,
    channel: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> str:
    _ = metadata
    cmd = text.strip()
    if not cmd:
        return "Empty message."

    lower = cmd.lower().split()[0]
    if lower in COMMANDS:
        method, path = COMMANDS[lower]
        payload = _request(method, path)
        return _format(lower, payload)

    if lower == "/checkin" and len(cmd.split()) > 1:
        habit_id = cmd.split()[1]
        payload = _request(
            "POST",
            f"/habits/{habit_id}/check-in",
            {"completed": True, "skipped": False},
        )
        return "Habit checked in." if payload.get("ok") else f"Failed: {payload.get('error')}"

    if lower.startswith("/journal") and "|" in cmd:
        raw = cmd[8:].strip()
        passphrase, content = (part.strip() for part in raw.split("|", 1))
        payload = _request(
            "POST",
            "/journal",
            {"content": content, "passphrase": passphrase, "tags": [channel]},
        )
        return "Journal saved." if payload.get("ok") else f"Failed: {payload.get('error')}"

    payload = _request("POST", "/voice/command", {"text": cmd, "channel": channel})
    if payload.get("ok"):
        data = payload.get("data") or {}
        return str(data.get("response_text") or data.get("response") or "Done.")
    return f"William error: {payload.get('error', 'unknown')}"
