"""
WILLIAM OS — Email Intelligence Full Program (CLI)
End-to-end command-line client for Email Intelligence APIs.
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


class EmailCLIClient:
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
                "device_name": "Email CLI",
                "device_type": "cli",
            },
        )
        token = payload["data"]["access_token"]
        self.token = token
        return token

    async def connect_account(
        self, provider: str, email_address: str, oauth_token: str
    ) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/email/connect",
            params={"oauth_token": oauth_token},
            json_body={"provider": provider, "email_address": email_address},
            requires_auth=True,
        )
        return payload["data"]

    async def list_accounts(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/email/accounts", requires_auth=True)
        return payload["data"]

    async def sync_emails(self) -> dict[str, Any]:
        payload = await self._request("POST", "/api/v1/email/sync", requires_auth=True)
        return payload["data"]

    async def get_summary(self) -> dict[str, Any] | None:
        payload = await self._request("GET", "/api/v1/email/summary", requires_auth=True)
        return payload["data"]

    async def get_briefing(self) -> dict[str, Any]:
        payload = await self._request("GET", "/api/v1/email/briefing", requires_auth=True)
        return payload["data"]

    async def disconnect_account(self, account_id: str) -> dict[str, Any]:
        payload = await self._request(
            "DELETE",
            f"/api/v1/email/accounts/{account_id}",
            requires_auth=True,
        )
        return payload["data"]

    async def run_demo(
        self, email: str, username: str, password: str, oauth_token: str
    ) -> dict[str, Any]:
        await self.register_or_login(email=email, username=username, password=password)

        connected = await self.connect_account(
            provider="gmail",
            email_address="inbox@example.com",
            oauth_token=oauth_token,
        )
        accounts = await self.list_accounts()
        synced = await self.sync_emails()
        summary = await self.get_summary()
        briefing = await self.get_briefing()

        return {
            "connected": connected,
            "accounts": accounts,
            "synced": synced,
            "summary": summary,
            "briefing": briefing,
        }

    async def _register(self, email: str, username: str, password: str) -> None:
        payload = await self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Email CLI User",
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
    parser = argparse.ArgumentParser(description="WILLIAM OS Email Intelligence full CLI")
    parser.add_argument(
        "--base-url", default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--email", default=os.getenv("WILLIAM_CLI_EMAIL", "email.cli@william.os"))
    parser.add_argument("--username", default=os.getenv("WILLIAM_CLI_USERNAME", "email_cli_user"))
    parser.add_argument("--password", default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"))
    parser.add_argument(
        "--oauth-token", default=os.getenv("WILLIAM_OAUTH_TOKEN", "oauth-token-demo")
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")

    connect = sub.add_parser("connect")
    connect.add_argument("--provider", default="gmail")
    connect.add_argument("--email-address", required=True)

    sub.add_parser("accounts")
    sub.add_parser("sync")
    sub.add_parser("summary")
    sub.add_parser("briefing")

    disconnect = sub.add_parser("disconnect")
    disconnect.add_argument("--account-id", required=True)

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = EmailCLIClient(base_url=args.base_url)

    email = args.email
    username = args.username
    if args.command == "demo" and email == "email.cli@william.os":
        suffix = secrets.token_hex(4)
        email = f"email.cli+{suffix}@william.os"
        username = f"email_cli_{suffix}"

    await client.register_or_login(email=email, username=username, password=args.password)

    if args.command == "demo":
        result = await client.run_demo(
            email=email,
            username=username,
            password=args.password,
            oauth_token=args.oauth_token,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "connect":
        result = await client.connect_account(
            provider=args.provider,
            email_address=args.email_address,
            oauth_token=args.oauth_token,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "accounts":
        result = await client.list_accounts()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "sync":
        result = await client.sync_emails()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "summary":
        result = await client.get_summary()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "briefing":
        result = await client.get_briefing()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "disconnect":
        result = await client.disconnect_account(args.account_id)
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
