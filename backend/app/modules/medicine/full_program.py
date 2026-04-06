"""
WILLIAM OS — Medicine Reminder Full Program (CLI)
End-to-end command-line client for Medicine Reminder APIs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


class APIClientError(Exception):
    """Raised when API response is invalid or unsuccessful."""


class MedicineCLIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

    async def register_or_login(self, email: str, username: str, password: str) -> str:
        await self._register(email, username, password)
        return await self.login(email, password)

    async def login(self, email: str, password: str) -> str:
        payload = await self._request(
            "POST",
            "/api/v1/auth/login",
            json_body={
                "email": email,
                "password": password,
                "device_name": "Medicine CLI",
                "device_type": "cli",
            },
        )
        token = payload["data"]["access_token"]
        self.token = token
        return token

    async def create_medicine(
        self,
        name: str,
        dosage: str,
        reminder_times: list[str],
        medicine_type: str = "supplement",
        with_food: bool = False,
        remaining_count: int | None = 30,
    ) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/medicine",
            json_body={
                "name": name,
                "dosage": dosage,
                "medicine_type": medicine_type,
                "times_per_day": max(1, len(reminder_times)),
                "reminder_times": reminder_times,
                "with_food": with_food,
                "remaining_count": remaining_count,
                "refill_reminder_days": 7,
            },
            requires_auth=True,
        )
        return payload["data"]

    async def log_dose(
        self,
        medicine_id: str,
        scheduled_time: str,
        taken: bool,
        skipped: bool,
        skip_reason: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "scheduled_time": scheduled_time,
            "log_date": datetime.now(UTC).date().isoformat(),
        }
        payload = await self._request(
            "POST",
            f"/api/v1/medicine/{medicine_id}/log",
            json_body={"taken": taken, "skipped": skipped, "skip_reason": skip_reason},
            params=params,
            requires_auth=True,
        )
        return payload["data"]

    async def list_medicines(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/medicine", requires_auth=True)
        return payload["data"]

    async def get_upcoming(self, within_minutes: int = 30) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/api/v1/medicine/upcoming",
            params={"within_minutes": str(within_minutes)},
            requires_auth=True,
        )
        return payload["data"]

    async def get_adherence(self, days: int = 30) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            "/api/v1/medicine/adherence",
            params={"days": str(days)},
            requires_auth=True,
        )
        return payload["data"]

    async def run_demo(self, email: str, username: str, password: str) -> dict[str, Any]:
        await self.register_or_login(email, username, password)

        upcoming_slot = (datetime.now(UTC) + timedelta(minutes=4)).strftime("%H:%M")
        evening_slot = (datetime.now(UTC) + timedelta(minutes=8)).strftime("%H:%M")

        created = await self.create_medicine(
            name="Omega 3",
            dosage="1000mg",
            reminder_times=[upcoming_slot, evening_slot],
            medicine_type="supplement",
            with_food=True,
            remaining_count=20,
        )

        taken_log = await self.log_dose(
            medicine_id=created["id"],
            scheduled_time=upcoming_slot,
            taken=True,
            skipped=False,
        )
        skipped_log = await self.log_dose(
            medicine_id=created["id"],
            scheduled_time=evening_slot,
            taken=False,
            skipped=True,
            skip_reason="Away from home",
        )

        medicines = await self.list_medicines()
        upcoming = await self.get_upcoming(within_minutes=15)
        adherence = await self.get_adherence(days=30)

        return {
            "created": created,
            "taken_log": taken_log,
            "skipped_log": skipped_log,
            "medicines": medicines,
            "upcoming": upcoming,
            "adherence": adherence,
        }

    async def _register(self, email: str, username: str, password: str) -> None:
        payload = await self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Medicine CLI User",
            },
            tolerate_error=True,
        )
        if payload.get("ok"):
            return
        message = (payload.get("error") or "").lower()
        if "already" in message or "registered" in message:
            return
        raise APIClientError(payload.get("error") or "Registration failed")

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
                raise APIClientError("Missing auth token")
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                json=json_body,
                params=params,
                headers=headers,
            )

        payload = response.json()
        if tolerate_error:
            return payload

        if response.status_code >= 400:
            raise APIClientError(
                f"{method} {path} failed ({response.status_code}): {payload.get('error') or payload}"
            )
        if not payload.get("ok", False):
            raise APIClientError(payload.get("error") or "Unknown API error")
        return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WILLIAM OS Medicine full CLI")
    parser.add_argument(
        "--base-url", default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument(
        "--email", default=os.getenv("WILLIAM_CLI_EMAIL", "medicine.cli@william.os")
    )
    parser.add_argument(
        "--username", default=os.getenv("WILLIAM_CLI_USERNAME", "medicine_cli_user")
    )
    parser.add_argument("--password", default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"))

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")

    create = sub.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--dosage", required=True)
    create.add_argument("--reminder-times", required=True)
    create.add_argument("--medicine-type", default="supplement")
    create.add_argument("--with-food", action="store_true", default=False)

    list_cmd = sub.add_parser("list")
    list_cmd.set_defaults(_unused=True)

    log = sub.add_parser("log")
    log.add_argument("--medicine-id", required=True)
    log.add_argument("--scheduled-time", required=True)
    log.add_argument("--taken", action="store_true", default=False)
    log.add_argument("--skipped", action="store_true", default=False)
    log.add_argument("--skip-reason", default=None)

    upcoming = sub.add_parser("upcoming")
    upcoming.add_argument("--within-minutes", type=int, default=30)

    adherence = sub.add_parser("adherence")
    adherence.add_argument("--days", type=int, default=30)

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = MedicineCLIClient(base_url=args.base_url)

    email = args.email
    username = args.username
    if args.command == "demo" and email == "medicine.cli@william.os":
        suffix = secrets.token_hex(4)
        email = f"medicine.cli+{suffix}@william.os"
        username = f"medicine_cli_{suffix}"

    await client.register_or_login(email=email, username=username, password=args.password)

    if args.command == "demo":
        result = await client.run_demo(email=email, username=username, password=args.password)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "create":
        reminder_times = [
            value.strip() for value in args.reminder_times.split(",") if value.strip()
        ]
        result = await client.create_medicine(
            name=args.name,
            dosage=args.dosage,
            reminder_times=reminder_times,
            medicine_type=args.medicine_type,
            with_food=args.with_food,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "list":
        result = await client.list_medicines()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "log":
        taken = args.taken
        skipped = args.skipped
        if not taken and not skipped:
            taken = True

        result = await client.log_dose(
            medicine_id=args.medicine_id,
            scheduled_time=args.scheduled_time,
            taken=taken,
            skipped=skipped,
            skip_reason=args.skip_reason,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "upcoming":
        result = await client.get_upcoming(within_minutes=args.within_minutes)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "adherence":
        result = await client.get_adherence(days=args.days)
        print(json.dumps(result, indent=2))
        return 0

    raise APIClientError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return asyncio.run(run_cli(args))
    except APIClientError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
