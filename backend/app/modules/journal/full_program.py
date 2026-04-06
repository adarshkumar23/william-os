"""
WILLIAM OS — Journal Vault Full Program (CLI)
End-to-end command-line client for Journal Vault APIs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
from typing import Any

import httpx


class APIClientError(Exception):
    """Raised when API response is invalid or unsuccessful."""


class JournalCLIClient:
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
                "device_name": "Journal CLI",
                "device_type": "cli",
            },
        )
        token = payload["data"]["access_token"]
        self.token = token
        return token

    async def create_entry(
        self,
        content: str,
        passphrase: str,
        mood: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "content": content,
            "passphrase": passphrase,
            "tags": tags or [],
        }
        if mood:
            body["mood"] = mood

        payload = await self._request(
            "POST",
            "/api/v1/journal",
            json_body=body,
            requires_auth=True,
        )
        return payload["data"]

    async def list_entries(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/journal", requires_auth=True)
        return payload["data"]

    async def read_entry(self, entry_id: str, passphrase: str) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/api/v1/journal/{entry_id}/read",
            json_body={"passphrase": passphrase},
            requires_auth=True,
        )
        return payload["data"]

    async def generate_summary(self, entry_id: str, passphrase: str) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/api/v1/journal/{entry_id}/summary",
            json_body={"passphrase": passphrase},
            requires_auth=True,
        )
        return payload["data"]

    async def delete_entry(self, entry_id: str) -> dict[str, Any]:
        payload = await self._request(
            "DELETE",
            f"/api/v1/journal/{entry_id}",
            requires_auth=True,
        )
        return payload["data"]

    async def run_demo(
        self, email: str, username: str, password: str, passphrase: str
    ) -> dict[str, Any]:
        await self.register_or_login(email, username, password)

        created = await self.create_entry(
            content=(
                "Today I executed deep work blocks and felt in control. "
                "Need to improve sleep timing tonight."
            ),
            passphrase=passphrase,
            mood="good",
            tags=["focus", "reflection"],
        )

        listed = await self.list_entries()
        read_ok = await self.read_entry(created["id"], passphrase)

        wrong_passphrase_error = None
        try:
            await self.read_entry(created["id"], "wrong-passphrase")
        except Exception as exc:
            wrong_passphrase_error = str(exc)

        summarized = await self.generate_summary(created["id"], passphrase)

        return {
            "created": created,
            "listed": listed,
            "read_ok": read_ok,
            "wrong_passphrase_error": wrong_passphrase_error,
            "summary": summarized.get("summary"),
        }

    async def _register(self, email: str, username: str, password: str) -> None:
        payload = await self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Journal CLI User",
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
    parser = argparse.ArgumentParser(description="WILLIAM OS Journal Vault full CLI")
    parser.add_argument(
        "--base-url", default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--email", default=os.getenv("WILLIAM_CLI_EMAIL", "journal.cli@william.os"))
    parser.add_argument("--username", default=os.getenv("WILLIAM_CLI_USERNAME", "journal_cli_user"))
    parser.add_argument("--password", default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"))
    parser.add_argument(
        "--passphrase", default=os.getenv("WILLIAM_JOURNAL_PASSPHRASE", "journal-pass-123")
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")

    create = sub.add_parser("create")
    create.add_argument("--content", required=True)
    create.add_argument("--mood", default=None)
    create.add_argument("--tags", default="")

    sub.add_parser("list")

    read = sub.add_parser("read")
    read.add_argument("--entry-id", required=True)

    summary = sub.add_parser("summary")
    summary.add_argument("--entry-id", required=True)

    delete = sub.add_parser("delete")
    delete.add_argument("--entry-id", required=True)

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = JournalCLIClient(base_url=args.base_url)

    email = args.email
    username = args.username
    if args.command == "demo" and email == "journal.cli@william.os":
        suffix = secrets.token_hex(4)
        email = f"journal.cli+{suffix}@william.os"
        username = f"journal_cli_{suffix}"

    await client.register_or_login(email=email, username=username, password=args.password)

    if args.command == "demo":
        result = await client.run_demo(email, username, args.password, args.passphrase)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "create":
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
        result = await client.create_entry(args.content, args.passphrase, args.mood, tags)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "list":
        result = await client.list_entries()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "read":
        result = await client.read_entry(args.entry_id, args.passphrase)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "summary":
        result = await client.generate_summary(args.entry_id, args.passphrase)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "delete":
        result = await client.delete_entry(args.entry_id)
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
