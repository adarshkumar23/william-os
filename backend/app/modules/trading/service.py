"""
WILLIAM OS — Trading Service
Watchlist management, trade logging, portfolio snapshots, and analysis.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from time import perf_counter

import httpx
import structlog
from app.core.config import get_settings
from app.core.metrics import observe_ai_call
from app.modules.trading.models import PortfolioSnapshot, PriceAlert, TradeLog, Watchlist
from app.modules.trading.schemas import (
    PortfolioSnapshotResponse,
    PortfolioSummary,
    PriceAlertResponse,
    TradeAnalysis,
    TradeLogCreate,
    TradeLogResponse,
    WatchlistCreate,
    WatchlistResponse,
)
from app.shared.types import NotFoundError
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class TradingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def add_to_watchlist(
        self, user_id: uuid.UUID, data: WatchlistCreate
    ) -> WatchlistResponse:
        symbol = data.symbol.upper().strip()
        exchange = data.exchange.upper().strip()
        result = await self.db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .where(Watchlist.symbol == symbol)
            .where(Watchlist.exchange == exchange)
            .where(Watchlist.is_active.is_(True))
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return WatchlistResponse.model_validate(existing)

        item = Watchlist(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            asset_type=data.asset_type,
            alert_price_above=data.alert_price_above,
            alert_price_below=data.alert_price_below,
            notes=data.notes,
            is_active=True,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return WatchlistResponse.model_validate(item)

    async def remove_from_watchlist(self, user_id: uuid.UUID, watchlist_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Watchlist).where(
                and_(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundError("Watchlist", str(watchlist_id))
        item.is_active = False
        await self.db.flush()

    async def list_watchlist(self, user_id: uuid.UUID) -> list[WatchlistResponse]:
        result = await self.db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .where(Watchlist.is_active.is_(True))
            .order_by(Watchlist.created_at.desc())
        )
        return [WatchlistResponse.model_validate(row) for row in result.scalars().all()]

    async def log_trade(self, user_id: uuid.UUID, data: TradeLogCreate) -> TradeLogResponse:
        total_value = round((data.quantity * data.price) + data.fees, 4)
        trade = TradeLog(
            user_id=user_id,
            symbol=data.symbol.upper().strip(),
            exchange=data.exchange.upper().strip(),
            action=data.action.lower().strip(),
            quantity=data.quantity,
            price=data.price,
            total_value=total_value,
            fees=data.fees,
            trade_date=data.trade_date,
            trade_time=data.trade_time,
            strategy=data.strategy,
            notes=data.notes,
            tags=data.tags,
        )
        self.db.add(trade)
        await self.db.flush()
        await self.db.refresh(trade)
        return TradeLogResponse.model_validate(trade)

    async def list_trades(
        self,
        user_id: uuid.UUID,
        symbol: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TradeLogResponse]:
        query = select(TradeLog).where(TradeLog.user_id == user_id)
        if symbol:
            query = query.where(TradeLog.symbol == symbol.upper().strip())
        if date_from:
            query = query.where(TradeLog.trade_date >= date_from)
        if date_to:
            query = query.where(TradeLog.trade_date <= date_to)
        if action:
            query = query.where(TradeLog.action == action.lower().strip())

        query = query.order_by(TradeLog.trade_date.desc(), TradeLog.created_at.desc())
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return [TradeLogResponse.model_validate(row) for row in result.scalars().all()]

    async def calculate_portfolio(self, user_id: uuid.UUID) -> PortfolioSummary:
        trades = await self.list_trades(user_id=user_id)
        holdings, total_invested, current_value = self._build_holdings(trades)
        total_pnl = round(current_value - total_invested, 4)

        previous_snapshot_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(desc(PortfolioSnapshot.snapshot_date), desc(PortfolioSnapshot.created_at))
            .limit(1)
        )
        previous_snapshot = previous_snapshot_result.scalar_one_or_none()
        daily_pnl = round(
            current_value
            - (previous_snapshot.current_value if previous_snapshot else current_value),
            4,
        )

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            snapshot_date=date.today(),
            total_invested=total_invested,
            current_value=current_value,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            holdings=holdings,
            currency="INR",
        )
        self.db.add(snapshot)
        await self.db.flush()

        top_gainers, top_losers = self._top_movers(holdings)
        total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0.0

        return PortfolioSummary(
            total_invested=total_invested,
            current_value=current_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            daily_pnl=daily_pnl,
            holdings_count=len(holdings),
            top_gainers=top_gainers,
            top_losers=top_losers,
        )

    async def get_portfolio_history(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> list[PortfolioSnapshotResponse]:
        cutoff = date.today() - timedelta(days=max(1, days) - 1)
        result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .where(PortfolioSnapshot.snapshot_date >= cutoff)
            .order_by(PortfolioSnapshot.snapshot_date.asc(), PortfolioSnapshot.created_at.asc())
        )
        rows = result.scalars().all()
        return [PortfolioSnapshotResponse.model_validate(row) for row in rows]

    async def analyze_trades(self, user_id: uuid.UUID, days: int = 90) -> TradeAnalysis:
        cutoff = date.today() - timedelta(days=max(1, days) - 1)
        result = await self.db.execute(
            select(TradeLog)
            .where(TradeLog.user_id == user_id)
            .where(TradeLog.trade_date >= cutoff)
            .order_by(TradeLog.trade_date.asc(), TradeLog.created_at.asc())
        )
        trades = result.scalars().all()

        if not trades:
            return TradeAnalysis(
                total_trades=0,
                win_rate=0.0,
                avg_return=0.0,
                best_trade=None,
                worst_trade=None,
                most_traded_symbol=None,
                strategy_performance={},
                ai_insights="No trades available for analysis.",
            )

        returns = self._estimate_trade_returns(trades)
        positive = [item for item in returns if item["return_pct"] > 0]
        win_rate = round((len(positive) / len(returns)) * 100, 2) if returns else 0.0
        avg_return = (
            round(sum(item["return_pct"] for item in returns) / len(returns), 2) if returns else 0.0
        )

        by_symbol: dict[str, int] = defaultdict(int)
        strategy_performance: dict[str, dict] = defaultdict(lambda: {"count": 0, "notional": 0.0})
        for trade in trades:
            by_symbol[trade.symbol] += 1
            strategy_key = (trade.strategy or "unlabeled").strip() or "unlabeled"
            strategy_performance[strategy_key]["count"] += 1
            strategy_performance[strategy_key]["notional"] += float(trade.total_value)

        best_trade = max(returns, key=lambda x: x["return_pct"]) if returns else None
        worst_trade = min(returns, key=lambda x: x["return_pct"]) if returns else None
        most_traded_symbol = max(by_symbol.items(), key=lambda x: x[1])[0] if by_symbol else None

        ai_insights = await self._generate_ai_insights(
            {
                "total_trades": len(trades),
                "win_rate": win_rate,
                "avg_return": avg_return,
                "best_trade": best_trade,
                "worst_trade": worst_trade,
                "most_traded_symbol": most_traded_symbol,
                "strategy_performance": strategy_performance,
            }
        )

        return TradeAnalysis(
            total_trades=len(trades),
            win_rate=win_rate,
            avg_return=avg_return,
            best_trade=best_trade,
            worst_trade=worst_trade,
            most_traded_symbol=most_traded_symbol,
            strategy_performance=dict(strategy_performance),
            ai_insights=ai_insights,
        )

    async def check_price_alerts(self, user_id: uuid.UUID) -> list[PriceAlertResponse]:
        watchlist = await self.list_watchlist(user_id=user_id)
        if not watchlist:
            return []

        latest_prices = await self._latest_price_map(user_id=user_id)
        triggered: list[PriceAlert] = []

        for item in watchlist:
            current_price = latest_prices.get(item.symbol)
            if current_price is None:
                continue

            if item.alert_price_above is not None and current_price >= item.alert_price_above:
                alert = PriceAlert(
                    user_id=user_id,
                    watchlist_id=item.id,
                    alert_type="above",
                    target_price=item.alert_price_above,
                    triggered=True,
                    triggered_at=datetime.now(UTC),
                    notification_sent=False,
                )
                self.db.add(alert)
                triggered.append(alert)

            if item.alert_price_below is not None and current_price <= item.alert_price_below:
                alert = PriceAlert(
                    user_id=user_id,
                    watchlist_id=item.id,
                    alert_type="below",
                    target_price=item.alert_price_below,
                    triggered=True,
                    triggered_at=datetime.now(UTC),
                    notification_sent=False,
                )
                self.db.add(alert)
                triggered.append(alert)

        await self.db.flush()
        return [PriceAlertResponse.model_validate(item) for item in triggered]

    @staticmethod
    def _build_holdings(trades: list[TradeLogResponse]) -> tuple[dict, float, float]:
        positions: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "symbol": "",
                "quantity": 0.0,
                "cost_basis": 0.0,
                "last_price": 0.0,
            }
        )

        for trade in sorted(trades, key=lambda x: (x.trade_date, x.created_at)):
            key = trade.symbol
            pos = positions[key]
            pos["symbol"] = key
            pos["last_price"] = float(trade.price)
            action = (trade.action or "").lower()

            if action == "buy":
                pos["quantity"] += float(trade.quantity)
                pos["cost_basis"] += float(trade.quantity * trade.price + trade.fees)
            elif action == "sell":
                if pos["quantity"] > 0:
                    sold_qty = min(float(trade.quantity), pos["quantity"])
                    avg_cost = pos["cost_basis"] / pos["quantity"] if pos["quantity"] else 0.0
                    pos["quantity"] -= sold_qty
                    pos["cost_basis"] -= avg_cost * sold_qty
                    if pos["quantity"] <= 0:
                        pos["quantity"] = 0.0
                        pos["cost_basis"] = 0.0
            else:
                # hold: keep position but allow latest mark price update.
                pass

        normalized: dict[str, dict] = {}
        total_invested = 0.0
        current_value = 0.0

        for symbol, pos in positions.items():
            qty = float(pos["quantity"])
            if qty <= 0:
                continue
            invested = float(pos["cost_basis"])
            last_price = float(pos["last_price"])
            value = qty * last_price
            pnl = value - invested
            pnl_pct = (pnl / invested) * 100 if invested > 0 else 0.0
            avg_price = invested / qty if qty > 0 else 0.0

            normalized[symbol] = {
                "symbol": symbol,
                "quantity": round(qty, 6),
                "avg_price": round(avg_price, 4),
                "current_price": round(last_price, 4),
                "invested_value": round(invested, 4),
                "current_value": round(value, 4),
                "pnl": round(pnl, 4),
                "pnl_pct": round(pnl_pct, 2),
            }

            total_invested += invested
            current_value += value

        return normalized, round(total_invested, 4), round(current_value, 4)

    @staticmethod
    def _top_movers(holdings: dict) -> tuple[list[dict], list[dict]]:
        rows = list(holdings.values())
        gainers = sorted(rows, key=lambda x: x.get("pnl_pct", 0.0), reverse=True)[:3]
        losers = sorted(rows, key=lambda x: x.get("pnl_pct", 0.0))[:3]
        return gainers, losers

    @staticmethod
    def _estimate_trade_returns(trades: list[TradeLog]) -> list[dict]:
        avg_buy: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
        analyzed: list[dict] = []

        for trade in trades:
            action = (trade.action or "").lower()
            symbol = trade.symbol
            qty = float(trade.quantity)
            price = float(trade.price)

            if action == "buy":
                prev_qty, prev_cost = avg_buy[symbol]
                new_qty = prev_qty + qty
                new_cost = prev_cost + (qty * price)
                avg_buy[symbol] = (new_qty, new_cost)
                analyzed.append(
                    {
                        "trade_id": str(trade.id),
                        "symbol": symbol,
                        "action": action,
                        "return_pct": 0.0,
                        "trade_date": str(trade.trade_date),
                    }
                )
                continue

            if action == "sell":
                prev_qty, prev_cost = avg_buy[symbol]
                avg_price = (prev_cost / prev_qty) if prev_qty > 0 else price
                return_pct = ((price - avg_price) / avg_price) * 100 if avg_price > 0 else 0.0
                analyzed.append(
                    {
                        "trade_id": str(trade.id),
                        "symbol": symbol,
                        "action": action,
                        "return_pct": round(return_pct, 2),
                        "trade_date": str(trade.trade_date),
                    }
                )
                continue

            analyzed.append(
                {
                    "trade_id": str(trade.id),
                    "symbol": symbol,
                    "action": action,
                    "return_pct": 0.0,
                    "trade_date": str(trade.trade_date),
                }
            )

        return analyzed

    async def _generate_ai_insights(self, payload: dict) -> str:
        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return "AI insights unavailable (missing OpenRouter key)."

        prompt = (
            "You are a trading analytics assistant. Analyze this trade summary and provide concise "
            "risk-aware insights with 3 actionable recommendations:\n"
            f"{json.dumps(payload, default=str)}"
        )
        body = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": "You provide practical portfolio analysis."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 400,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()

            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)

            return (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "No analysis generated.")
            )
        except Exception as exc:
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            logger.warning("trading_ai_analysis_failed", error=str(exc))
            return "AI analysis temporarily unavailable."

    async def _latest_price_map(self, user_id: uuid.UUID) -> dict[str, float]:
        result = await self.db.execute(
            select(TradeLog)
            .where(TradeLog.user_id == user_id)
            .order_by(TradeLog.trade_date.desc(), TradeLog.created_at.desc())
        )
        prices: dict[str, float] = {}
        for row in result.scalars().all():
            prices.setdefault(row.symbol, float(row.price))
        return prices
