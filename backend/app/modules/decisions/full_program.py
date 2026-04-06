"""
WILLIAM OS - Decision Assistant Full Program (CLI)
End-to-end command-line client for Decision assistant APIs.
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


class DecisionsCLIClient:
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
                "device_name": "Decisions CLI",
                "device_type": "cli",
            },
        )
        token = payload["data"]["access_token"]
        self.token = token
        return token

    async def create_decision(
        self,
        title: str,
        description: str,
        decision_type: str,
        options: list[dict[str, Any]],
        criteria: list[dict[str, Any]],
        deadline: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "decision_type": decision_type,
            "options": options,
            "criteria": criteria,
        }
        if deadline:
            body["deadline"] = deadline

        payload = await self._request(
            "POST",
            "/api/v1/decisions",
            json_body=body,
            requires_auth=True,
        )
        return payload["data"]

    async def list_decisions(self) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/api/v1/decisions",
            requires_auth=True,
        )
        return payload["data"]

    async def analyze_decision(self, decision_id: str) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/api/v1/decisions/{decision_id}/analyze",
            requires_auth=True,
        )
        return payload["data"]

    async def choose_option(self, decision_id: str, chosen_option: str) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/api/v1/decisions/{decision_id}/choose",
            json_body={"chosen_option": chosen_option, "reasoning": "CLI decision"},
            requires_auth=True,
        )
        return payload["data"]

    async def log_outcome(self, decision_id: str, outcome: str, rating: int) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/api/v1/decisions/{decision_id}/outcome",
            json_body={"outcome": outcome, "outcome_rating": rating},
            requires_auth=True,
        )
        return payload["data"]

    async def get_stats(self) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            "/api/v1/decisions/stats",
            requires_auth=True,
        )
        return payload["data"]

    async def run_demo(self, email: str, username: str, password: str) -> dict[str, Any]:
        token = await self.register_or_login(email, username, password)

        decision = await self.create_decision(
            title="Choose next learning sprint",
            description="Select what to focus on for the next 4 weeks.",
            decision_type="career",
            deadline=(date.today()).isoformat(),
            options=[
                {"name": "Advanced system design", "cost": "medium"},
                {"name": "Quant trading basics", "cost": "high"},
                {"name": "MLOps project", "cost": "medium"},
            ],
            criteria=[
                {"name": "career_impact", "weight": 0.5},
                {"name": "enjoyment", "weight": 0.3},
                {"name": "time_to_complete", "weight": 0.2},
            ],
        )

        analysis = await self.analyze_decision(decision["id"])
        chosen = await self.choose_option(
            decision["id"],
            analysis.get("recommendation") or "Advanced system design",
        )
        outcome = await self.log_outcome(
            decision_id=decision["id"],
            outcome="High clarity and sustained motivation in week 1.",
            rating=4,
        )

        decisions = await self.list_decisions()
        stats = await self.get_stats()

        return {
            "token_preview": f"{token[:20]}...",
            "decision": decision,
            "analysis": analysis,
            "chosen": chosen,
            "outcome": outcome,
            "decisions": decisions,
            "stats": stats,
        }

    async def _register(self, email: str, username: str, password: str) -> None:
        payload = await self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Decisions CLI User",
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
            raise APIClientError(
                f"{method} {path} failed ({response.status_code}): {detail}"
            )
        if not payload.get("ok", False):
            raise APIClientError(payload.get("error") or "Unknown API error")
        return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WILLIAM OS Decisions full CLI")
    parser.add_argument(
        "--base-url", default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument(
        "--email", default=os.getenv("WILLIAM_CLI_EMAIL", "decisions.cli@william.os")
    )
    parser.add_argument(
        "--username", default=os.getenv("WILLIAM_CLI_USERNAME", "decisions_cli_user")
    )
    parser.add_argument("--password", default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"))

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")

    create = sub.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--decision-type", required=True)
    create.add_argument("--deadline", default=None)

    sub.add_parser("list")

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--decision-id", required=True)

    choose = sub.add_parser("choose")
    choose.add_argument("--decision-id", required=True)
    choose.add_argument("--chosen-option", required=True)

    outcome = sub.add_parser("outcome")
    outcome.add_argument("--decision-id", required=True)
    outcome.add_argument("--outcome", required=True)
    outcome.add_argument("--rating", type=int, required=True)

    sub.add_parser("stats")

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = DecisionsCLIClient(base_url=args.base_url)

    email = args.email
    username = args.username
    if args.command == "demo" and email == "decisions.cli@william.os":
        suffix = secrets.token_hex(4)
        email = f"decisions.cli+{suffix}@william.os"
        username = f"decisions_cli_{suffix}"

    await client.register_or_login(email=email, username=username, password=args.password)

    if args.command == "demo":
        result = await client.run_demo(email=email, username=username, password=args.password)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "create":
        default_options = [
            {"name": "Option A", "score": 0},
            {"name": "Option B", "score": 0},
        ]
        default_criteria = [
            {"name": "impact", "weight": 0.6},
            {"name": "effort", "weight": 0.4},
        ]
        result = await client.create_decision(
            title=args.title,
            description=args.description,
            decision_type=args.decision_type,
            deadline=args.deadline,
            options=default_options,
            criteria=default_criteria,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "list":
        result = await client.list_decisions()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "analyze":
        result = await client.analyze_decision(args.decision_id)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "choose":
        result = await client.choose_option(args.decision_id, args.chosen_option)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "outcome":
        result = await client.log_outcome(args.decision_id, args.outcome, args.rating)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "stats":
        result = await client.get_stats()
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
