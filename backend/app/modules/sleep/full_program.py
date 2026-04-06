"""
WILLIAM OS - Sleep Optimizer Full Program (CLI)
End-to-end command-line client for Sleep optimizer APIs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx


class APIClientError(Exception):
    """Raised when API response is invalid or unsuccessful."""


class SleepCLIClient:
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
                "device_name": "Sleep CLI",
                "device_type": "cli",
            },
        )
        token = payload["data"]["access_token"]
        self.token = token
        return token

    async def log_sleep(
        self,
        sleep_date: str,
        bedtime: str,
        wake_time: str,
        sleep_quality: float,
        interruptions: int = 0,
    ) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/sleep/log",
            json_body={
                "sleep_date": sleep_date,
                "bedtime": bedtime,
                "wake_time": wake_time,
                "sleep_quality": sleep_quality,
                "interruptions": interruptions,
                "source": "cli",
            },
            requires_auth=True,
        )
        return payload["data"]

    async def get_history(self, days: int = 30) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/api/v1/sleep/history",
            params={"days": str(days)},
            requires_auth=True,
        )
        return payload["data"]

    async def get_stats(self) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            "/api/v1/sleep/stats",
            requires_auth=True,
        )
        return payload["data"]

    async def get_debt(self) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            "/api/v1/sleep/debt",
            requires_auth=True,
        )
        return payload["data"]

    async def generate_recommendation(self, target_date: str | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if target_date:
            params["target_date"] = target_date

        payload = await self._request(
            "POST",
            "/api/v1/sleep/recommendation/generate",
            params=params,
            requires_auth=True,
        )
        return payload["data"]

    async def analyze(self, days: int = 90) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/sleep/analyze",
            params={"days": str(days)},
            requires_auth=True,
        )
        return payload["data"]

    async def run_demo(self, email: str, username: str, password: str) -> dict[str, Any]:
        token = await self.register_or_login(email, username, password)

        wake_dt = datetime.now(UTC).replace(hour=6, minute=30, second=0, microsecond=0)
        bed_dt = (wake_dt - timedelta(hours=7, minutes=30)).replace(second=0, microsecond=0)

        logged = await self.log_sleep(
            sleep_date=date.today().isoformat(),
            bedtime=bed_dt.isoformat(),
            wake_time=wake_dt.isoformat(),
            sleep_quality=7.8,
            interruptions=1,
        )

        history = await self.get_history(days=30)
        stats = await self.get_stats()
        debt = await self.get_debt()
        recommendation = await self.generate_recommendation(target_date=date.today().isoformat())
        analysis = await self.analyze(days=90)

        return {
            "token_preview": f"{token[:20]}...",
            "logged": logged,
            "history": history,
            "stats": stats,
            "debt": debt,
            "recommendation": recommendation,
            "analysis": analysis,
        }

    async def _register(self, email: str, username: str, password: str) -> None:
        payload = await self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Sleep CLI User",
            },
            tolerate_error=True,
        )

        if payload.get("ok"):
            return

        error_message = (payload.get("error") or "").lower()
        if "already" in error_message or "registered" in error_message:
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
            detail = payload.get("error") or payload
            raise APIClientError(f"{method} {path} failed ({response.status_code}): {detail}")
        if not payload.get("ok", False):
            raise APIClientError(payload.get("error") or "Unknown API error")
        return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WILLIAM OS Sleep full CLI")
    parser.add_argument(
        "--base-url", default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--email", default=os.getenv("WILLIAM_CLI_EMAIL", "sleep.cli@william.os"))
    parser.add_argument("--username", default=os.getenv("WILLIAM_CLI_USERNAME", "sleep_cli_user"))
    parser.add_argument("--password", default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"))

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")

    log_cmd = sub.add_parser("log")
    log_cmd.add_argument("--sleep-date", required=True)
    log_cmd.add_argument("--bedtime", required=True)
    log_cmd.add_argument("--wake-time", required=True)
    log_cmd.add_argument("--quality", type=float, required=True)
    log_cmd.add_argument("--interruptions", type=int, default=0)

    history = sub.add_parser("history")
    history.add_argument("--days", type=int, default=30)

    sub.add_parser("stats")
    sub.add_parser("debt")

    recommendation = sub.add_parser("recommend")
    recommendation.add_argument("--target-date", default=None)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--days", type=int, default=90)

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = SleepCLIClient(base_url=args.base_url)

    email = args.email
    username = args.username
    if args.command == "demo" and email == "sleep.cli@william.os":
        suffix = secrets.token_hex(4)
        email = f"sleep.cli+{suffix}@william.os"
        username = f"sleep_cli_{suffix}"

    await client.register_or_login(email=email, username=username, password=args.password)

    if args.command == "demo":
        result = await client.run_demo(email=email, username=username, password=args.password)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "log":
        result = await client.log_sleep(
            sleep_date=args.sleep_date,
            bedtime=args.bedtime,
            wake_time=args.wake_time,
            sleep_quality=args.quality,
            interruptions=args.interruptions,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "history":
        result = await client.get_history(days=args.days)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "stats":
        result = await client.get_stats()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "debt":
        result = await client.get_debt()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "recommend":
        result = await client.generate_recommendation(target_date=args.target_date)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "analyze":
        result = await client.analyze(days=args.days)
        print(json.dumps(result, indent=2))
        return 0

    raise APIClientError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return asyncio.run(run_cli(args))
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
