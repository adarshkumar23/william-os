"""OpenClaw skill: WILLIAM OS gateway command router."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _build_headers() -> dict[str, str]:
    token = os.getenv("WILLIAM_GATEWAY_BEARER_TOKEN", "").strip()
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _api_base_url() -> str:
    return os.getenv("WILLIAM_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    timeout = int(os.getenv("WILLIAM_GATEWAY_TIMEOUT_SECONDS", "20"))
    url = f"{_api_base_url()}{path}"

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=_build_headers(),
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"http_error:{exc.code}", "data": details}
    except Exception as exc:  # pylint: disable=broad-except
        return {"ok": False, "error": str(exc), "data": None}


def _format_schedule(payload: dict[str, Any]) -> str:
    data = payload.get("data") or {}
    blocks = data.get("blocks") or []
    plan_date = data.get("plan_date", "today")

    lines = [f"Schedule for {plan_date}:"]
    if not blocks:
        lines.append("- No blocks found.")
        return "\n".join(lines)

    for block in blocks[:8]:
        start = str(block.get("start_time", "--:--"))[:5]
        title = str(block.get("title", "Untitled"))
        lines.append(f"- {start} {title}")

    return "\n".join(lines)


def _format_habits(payload: dict[str, Any]) -> str:
    habits = payload.get("data") or []
    if not habits:
        return "No active habits found."

    lines = ["Active habits:"]
    for habit in habits[:10]:
        name = str(habit.get("name", "Habit"))
        streak = habit.get("current_streak", 0)
        lines.append(f"- {name} (streak: {streak})")
    return "\n".join(lines)


def _format_sleep(payload: dict[str, Any]) -> str:
    stats = payload.get("data") or {}
    return (
        "Sleep stats:\n"
        f"- Avg quality (30d): {stats.get('avg_quality_30d', 'n/a')}\n"
        f"- Avg duration: {stats.get('avg_duration', 'n/a')} min\n"
        f"- Consistency: {stats.get('consistency_score', 'n/a')}"
    )


def _format_briefing(payload: dict[str, Any]) -> str:
    data = payload.get("data") or {}
    priorities = data.get("top_priorities") or []
    schedule = data.get("schedule_summary") or {}

    lines = ["Morning briefing:"]
    lines.append(f"- Plan date: {schedule.get('plan_date', 'n/a')}")
    lines.append(f"- Blocks: {schedule.get('total_blocks', 0)}")
    if priorities:
        lines.append(f"- Priorities: {', '.join(map(str, priorities[:5]))}")
    return "\n".join(lines)


def _format_voice(payload: dict[str, Any]) -> str:
    data = payload.get("data") or {}
    response_text = data.get("response_text") or data.get("response")
    if response_text:
        return str(response_text)
    return json.dumps(data, indent=2, ensure_ascii=True)


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error", "unknown error")
    return f"Command failed: {error}"


def handle_message(
    text: str,
    channel: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Route an incoming chat message to WILLIAM OS and return plain text response."""

    _ = metadata
    command = text.strip()
    if not command:
        return "Empty message received."

    lower = command.lower()

    if lower == "/today":
        payload = _request("GET", "/schedule/today")
        return _error_message(payload) if not payload.get("ok") else _format_schedule(payload)

    if lower == "/habits":
        query = urllib.parse.urlencode({"active_only": "true", "limit": 20, "offset": 0})
        payload = _request("GET", f"/habits?{query}")
        return _error_message(payload) if not payload.get("ok") else _format_habits(payload)

    if lower == "/sleep":
        payload = _request("GET", "/sleep/stats")
        return _error_message(payload) if not payload.get("ok") else _format_sleep(payload)

    if lower == "/briefing":
        payload = _request("GET", "/email/briefing")
        return _error_message(payload) if not payload.get("ok") else _format_briefing(payload)

    if lower.startswith("/journal "):
        raw = command[9:].strip()
        if "|" not in raw:
            return "Usage: /journal <passphrase>|<text>"

        passphrase, content = (chunk.strip() for chunk in raw.split("|", maxsplit=1))
        if len(passphrase) < 8 or not content:
            return "Usage: /journal <passphrase>|<text> (passphrase min length: 8)"

        payload = _request(
            "POST",
            "/journal",
            {"content": content, "passphrase": passphrase, "tags": [channel]},
        )
        if not payload.get("ok"):
            return _error_message(payload)

        entry = payload.get("data") or {}
        return f"Journal entry saved for {entry.get('entry_date', 'today')}."

    if lower.startswith("/checkin "):
        habit_id = command[9:].strip()
        if not habit_id:
            return "Usage: /checkin <habit_id>"

        payload = _request(
            "POST",
            f"/habits/{habit_id}/check-in",
            {"completed": True, "skipped": False},
        )
        if not payload.get("ok"):
            return _error_message(payload)
        return "Habit check-in saved."

    payload = _request("POST", "/voice/command", {"text": command})
    return _error_message(payload) if not payload.get("ok") else _format_voice(payload)
