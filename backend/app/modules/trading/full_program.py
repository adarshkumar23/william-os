"""
WILLIAM OS - Trading Dashboard Full Program (CLI)
End-to-end command-line client for Trading dashboard APIs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
from datetime import UTC, date, datetime
from typing import Any

import httpx


class APIClientError(Exception):
    """Raised when API response is invalid or unsuccessful."""


class TradingCLIClient:
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
                "device_name": "Trading CLI",
                "device_type": "cli",
            },
        )
        token = payload["data"]["access_token"]
        self.token = token
        return token

    async def add_watchlist(
        self,
        symbol: str,
        exchange: str = "NSE",
        asset_type: str = "equity",
        alert_above: float | None = None,
        alert_below: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "symbol": symbol,
            "exchange": exchange,
            "asset_type": asset_type,
        }
        if alert_above is not None:
            body["alert_price_above"] = alert_above
        if alert_below is not None:
            body["alert_price_below"] = alert_below

        payload = await self._request(
            "POST",
            "/api/v1/trading/watchlist",
            json_body=body,
            requires_auth=True,
        )
        return payload["data"]

    async def list_watchlist(self) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/api/v1/trading/watchlist",
            requires_auth=True,
        )
        return payload["data"]

    async def log_trade(
        self,
        symbol: str,
        exchange: str,
        action: str,
        quantity: float,
        price: float,
        fees: float = 0.0,
    ) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/trading/trades",
            json_body={
                "symbol": symbol,
                "exchange": exchange,
                "action": action,
                "quantity": quantity,
                "price": price,
                "fees": fees,
                "trade_date": date.today().isoformat(),
                "trade_time": datetime.now(UTC).time().replace(microsecond=0).isoformat(),
                "strategy": "swing",
                "notes": "CLI logged trade",
                "tags": ["cli"],
            },
            requires_auth=True,
        )
        return payload["data"]

    async def list_trades(self) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/api/v1/trading/trades",
            requires_auth=True,
        )
        return payload["data"]

    async def get_portfolio(self) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            "/api/v1/trading/portfolio",
            requires_auth=True,
        )
        return payload["data"]

    async def analyze_trades(self, days: int = 90) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/trading/analyze",
            params={"days": str(days)},
            requires_auth=True,
        )
        return payload["data"]

    async def run_demo(self, email: str, username: str, password: str) -> dict[str, Any]:
        token = await self.register_or_login(email, username, password)

        watch_a = await self.add_watchlist("RELIANCE", alert_above=3100.0)
        watch_b = await self.add_watchlist("INFY", alert_below=1450.0)

        buy_trade = await self.log_trade(
            symbol="RELIANCE",
            exchange="NSE",
            action="buy",
            quantity=5,
            price=2985.0,
            fees=10.0,
        )
        sell_trade = await self.log_trade(
            symbol="RELIANCE",
            exchange="NSE",
            action="sell",
            quantity=2,
            price=3020.0,
            fees=8.0,
        )

        watchlist = await self.list_watchlist()
        trades = await self.list_trades()
        portfolio = await self.get_portfolio()
        analysis = await self.analyze_trades(days=90)

        return {
            "token_preview": f"{token[:20]}...",
            "watchlist": [watch_a, watch_b],
            "trades_logged": [buy_trade, sell_trade],
            "all_watchlist": watchlist,
            "all_trades": trades,
            "portfolio": portfolio,
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
                "full_name": "Trading CLI User",
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
    parser = argparse.ArgumentParser(description="WILLIAM OS Trading full CLI")
    parser.add_argument(
        "--base-url", default=os.getenv("WILLIAM_API_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--email", default=os.getenv("WILLIAM_CLI_EMAIL", "trading.cli@william.os"))
    parser.add_argument("--username", default=os.getenv("WILLIAM_CLI_USERNAME", "trading_cli_user"))
    parser.add_argument("--password", default=os.getenv("WILLIAM_CLI_PASSWORD", "StrongPass1"))

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")

    watchlist = sub.add_parser("watchlist-add")
    watchlist.add_argument("--symbol", required=True)
    watchlist.add_argument("--exchange", default="NSE")
    watchlist.add_argument("--asset-type", default="equity")
    watchlist.add_argument("--alert-above", type=float, default=None)
    watchlist.add_argument("--alert-below", type=float, default=None)

    sub.add_parser("watchlist-list")

    trade = sub.add_parser("trade-log")
    trade.add_argument("--symbol", required=True)
    trade.add_argument("--exchange", default="NSE")
    trade.add_argument("--action", choices=["buy", "sell", "hold"], required=True)
    trade.add_argument("--quantity", type=float, required=True)
    trade.add_argument("--price", type=float, required=True)
    trade.add_argument("--fees", type=float, default=0.0)

    sub.add_parser("trades")

    portfolio = sub.add_parser("portfolio")
    portfolio.set_defaults(_unused=True)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--days", type=int, default=90)

    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    client = TradingCLIClient(base_url=args.base_url)

    email = args.email
    username = args.username
    if args.command == "demo" and email == "trading.cli@william.os":
        suffix = secrets.token_hex(4)
        email = f"trading.cli+{suffix}@william.os"
        username = f"trading_cli_{suffix}"

    await client.register_or_login(email=email, username=username, password=args.password)

    if args.command == "demo":
        result = await client.run_demo(email=email, username=username, password=args.password)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "watchlist-add":
        result = await client.add_watchlist(
            symbol=args.symbol,
            exchange=args.exchange,
            asset_type=args.asset_type,
            alert_above=args.alert_above,
            alert_below=args.alert_below,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "watchlist-list":
        result = await client.list_watchlist()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "trade-log":
        result = await client.log_trade(
            symbol=args.symbol,
            exchange=args.exchange,
            action=args.action,
            quantity=args.quantity,
            price=args.price,
            fees=args.fees,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "trades":
        result = await client.list_trades()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "portfolio":
        result = await client.get_portfolio()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "analyze":
        result = await client.analyze_trades(days=args.days)
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
