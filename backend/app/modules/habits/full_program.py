"""
WILLIAM OS — Habits Full Program (CLI)
End-to-end command-line client for Habits module APIs.

Usage examples:
    python -m app.modules.habits.full_program demo
    python -m app.modules.habits.full_program create --name "Morning Run"
    python -m app.modules.habits.full_program list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
from datetime import date
from typing import Any

import httpx


class APIClientError(Exception):
    """Raised when API response is invalid or unsuccessful."""


class WilliamHabitsClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

    async def register_or_login(self, email: str, username: str, password: str) -> str:
        await self._register(email=email, username=username, password=password)
        return await self.login(email=email, password=password)

    async def login(self, email: str, password: str) -> str:
        response = await self._request(
            "POST",
            "/api/v1/auth/login",
            json_body={
                "email": email,
                "password": password,
                "device_name": "Habits CLI",
                "device_type": "cli",
            },
        )
        token = response["data"]["access_token"]
        self.token = token
        return token

    async def create_habit(
        self,
        name: str,
        preferred_time: str | None = None,
        category: str = "general",
        frequency: str = "daily",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "category": category,
            "frequency": frequency,
        }
        if preferred_time:
            payload["preferred_time"] = preferred_time

        response = await self._request(
            "POST",
            "/api/v1/habits",
            json_body=payload,
            requires_auth=True,
        )
        return response["data"]

    async def list_habits(self, active_only: bool = True) -> list[dict[str, Any]]:
        response = await self._request(
            "GET",
            "/api/v1/habits",
            params={"active_only": str(active_only).lower()},
            requires_auth=True,
        )
        return response["data"]

    async def check_in_habit(
        self,
        habit_id: str,
        completed: bool = True,
        skipped: bool = False,
        quality_score: float | None = None,
        notes: str | None = None,
        check_date: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "completed": completed,
            "skipped": skipped,
        }
        if quality_score is not None:
            payload["quality_score"] = quality_score
        if notes:
            payload["notes"] = notes
        if check_date:
            payload["check_date"] = check_date

        response = await self._request(
            "POST",
            f"/api/v1/habits/{habit_id}/check-in",
            json_body=payload,
            requires_auth=True,
        )
        return response["data"]

    async def get_daily_check_ins(self, target_date: str | None = None) -> list[dict[str, Any]]:
        date_value = target_date or date.today().isoformat()
        response = await self._request(
            "GET",
            f"/api/v1/habits/check-ins/{date_value}",
            requires_auth=True,
        )
        return response["data"]

    async def detect_procrastination(
        self,
        target_date: str | None = None,
        threshold_minutes: int = 90,
        missed_habit_threshold: int = 2,
    ) -> dict[str, Any] | None:
        payload = {
            "target_date": target_date or date.today().isoformat(),
            "threshold_minutes": threshold_minutes,
            "missed_habit_threshold": missed_habit_threshold,
        }
        response = await self._request(
            "POST",
            "/api/v1/habits/procrastination/detect",
            json_body=payload,
            requires_auth=True,
        )
        return response["data"]

    async def run_demo(self, email: str, username: str, password: str) -> dict[str, Any]:
        token = await self.register_or_login(email=email, username=username, password=password)

        morning = await self.create_habit(
            name="Morning Reading",
            preferred_time="07:00:00",
            category="study",
            frequency="daily",
        )
        workout = await self.create_habit(
            name="Evening Workout",
            preferred_time="18:00:00",
            category="fitness",
            frequency="daily",
        )

        check_in_morning = await self.check_in_habit(
            habit_id=morning["id"],
            completed=True,
            skipped=False,
            quality_score=5,
            notes="Completed 45 minutes.",
        )

        check_in_evening = await self.check_in_habit(
            habit_id=workout["id"],
            completed=False,
            skipped=True,
            notes="Skipped due to travel.",
        )

        habits = await self.list_habits(active_only=True)
        today_check_ins = await self.get_daily_check_ins()
        procrastination_signal = await self.detect_procrastination(
            threshold_minutes=60,
            missed_habit_threshold=1,
        )

        return {
            "token_preview": f"{token[:20]}...",
            "created_habits": [morning, workout],
            "check_ins": [check_in_morning, check_in_evening],
            "habits": habits,
            "today_check_ins": today_check_ins,
            "procrastination_signal": procrastination_signal,
        }

    async def _register(self, email: str, username: str, password: str) -> None:
        response = await self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Habits CLI User",
            },
            tolerate_error=True,
        )

        if response.get("ok"):
            return

        error_message = (response.get("error") or "").lower()
        if "already" in error_message or "registered" in error_message:
            return

        raise APIClientError(response.get("error") or "Register failed")

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        requires_auth: bool = False,
        tolerate_error: bool = False,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if requires_auth:
            if not self.token:
                raise APIClientError("Missing access token. Login first.")
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                json=json_body,
                params=params,
                headers=headers,
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise APIClientError(f"Non-JSON response from {path}: {response.text}") from exc

        if tolerate_error:
            return payload

        if response.status_code >= 400:
            error_detail = payload.get("error") or payload
            raise APIClientError(f"{method} {path} failed ({response.status_code}): {error_detail}")

        if not isinstance(payload, dict) or "ok" not in payload:
            raise APIClientError(f"Unexpected envelope from {path}: {payload}")

        if not payload.get("ok", False):
            raise APIClientError(f"API error from {path}: {payload.get('error')}")

        return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WILLIAM OS Habits full CLI program",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("WILLIAM_CLI_EMAIL", "habits.cli@william.os"),
        help="Auth email for CLI actions",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("WILLIAM_CLI_USERNAME", "habits_cli_user"),
        help="Username used for register/demo",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"),
        help="Auth password",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("demo", help="Run full end-to-end habits flow")

    create_parser = subparsers.add_parser("create", help="Create a habit")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--preferred-time", default=None)
    create_parser.add_argument("--category", default="general")
    create_parser.add_argument("--frequency", default="daily")

    list_parser = subparsers.add_parser("list", help="List habits")
    list_parser.add_argument("--active-only", action="store_true", default=False)

    check_in_parser = subparsers.add_parser("check-in", help="Check in a habit")
    check_in_parser.add_argument("--habit-id", required=True)
    check_in_parser.add_argument("--completed", action="store_true", default=False)
    check_in_parser.add_argument("--skipped", action="store_true", default=False)
    check_in_parser.add_argument("--quality-score", type=float, default=None)
    check_in_parser.add_argument("--notes", default=None)
    check_in_parser.add_argument("--check-date", default=None)

    daily_parser = subparsers.add_parser("daily", help="Get daily check-ins")
    daily_parser.add_argument("--target-date", default=None)

    detect_parser = subparsers.add_parser("detect", help="Detect procrastination")
    detect_parser.add_argument("--target-date", default=None)
    detect_parser.add_argument("--threshold-minutes", type=int, default=90)
    detect_parser.add_argument("--missed-habit-threshold", type=int, default=2)

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = WilliamHabitsClient(base_url=args.base_url)

    email = args.email
    username = args.username
    password = args.password

    if args.command == "demo":
        if email == "habits.cli@william.os" and username == "habits_cli_user":
            suffix = secrets.token_hex(4)
            email = f"habits.cli+{suffix}@william.os"
            username = f"habits_cli_{suffix}"

        result = await client.run_demo(email=email, username=username, password=password)
        print(json.dumps(result, indent=2))
        return 0

    await client.register_or_login(email=email, username=username, password=password)

    if args.command == "create":
        habit = await client.create_habit(
            name=args.name,
            preferred_time=args.preferred_time,
            category=args.category,
            frequency=args.frequency,
        )
        print(json.dumps(habit, indent=2))
        return 0

    if args.command == "list":
        habits = await client.list_habits(active_only=args.active_only)
        print(json.dumps(habits, indent=2))
        return 0

    if args.command == "check-in":
        completed = args.completed
        skipped = args.skipped
        if not completed and not skipped:
            completed = True

        result = await client.check_in_habit(
            habit_id=args.habit_id,
            completed=completed,
            skipped=skipped,
            quality_score=args.quality_score,
            notes=args.notes,
            check_date=args.check_date,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "daily":
        check_ins = await client.get_daily_check_ins(target_date=args.target_date)
        print(json.dumps(check_ins, indent=2))
        return 0

    if args.command == "detect":
        result = await client.detect_procrastination(
            target_date=args.target_date,
            threshold_minutes=args.threshold_minutes,
            missed_habit_threshold=args.missed_habit_threshold,
        )
        print(json.dumps(result, indent=2))
        return 0

    raise APIClientError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parsed = parse_args(argv or sys.argv[1:])
    try:
        return asyncio.run(run_cli(parsed))
    except APIClientError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
