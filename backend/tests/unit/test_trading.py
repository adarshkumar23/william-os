"""
WILLIAM OS — Trading Service Tests
Unit tests for watchlist, trade logging, portfolio calculation, and analysis.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.modules.trading.schemas import TradeLogCreate, WatchlistCreate
from app.modules.trading.service import TradingService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_watchlist_add_list_remove(db_session: AsyncSession, test_user):
    service = TradingService(db_session)

    created = await service.add_to_watchlist(
        user_id=test_user.id,
        data=WatchlistCreate(
            symbol="INFY",
            exchange="NSE",
            asset_type="equity",
            alert_price_above=1800,
        ),
    )

    rows = await service.list_watchlist(user_id=test_user.id)
    assert len(rows) == 1
    assert rows[0].symbol == "INFY"

    await service.remove_from_watchlist(user_id=test_user.id, watchlist_id=created.id)
    rows_after = await service.list_watchlist(user_id=test_user.id)
    assert rows_after == []


@pytest.mark.asyncio
async def test_log_buy_and_sell_trades(db_session: AsyncSession, test_user):
    service = TradingService(db_session)

    buy = await service.log_trade(
        user_id=test_user.id,
        data=TradeLogCreate(
            symbol="BTCUSDT",
            exchange="BINANCE",
            action="buy",
            quantity=0.5,
            price=60000,
            fees=20,
            trade_date=date.today(),
            strategy="swing",
            tags=["crypto"],
        ),
    )
    sell = await service.log_trade(
        user_id=test_user.id,
        data=TradeLogCreate(
            symbol="BTCUSDT",
            exchange="BINANCE",
            action="sell",
            quantity=0.2,
            price=62000,
            fees=10,
            trade_date=date.today(),
            strategy="swing",
            tags=["crypto"],
        ),
    )

    assert buy.total_value == pytest.approx(30020)
    assert sell.total_value == pytest.approx(12410)

    trades = await service.list_trades(user_id=test_user.id, symbol="BTCUSDT")
    assert len(trades) == 2


@pytest.mark.asyncio
async def test_portfolio_calculation(db_session: AsyncSession, test_user):
    service = TradingService(db_session)

    await service.log_trade(
        user_id=test_user.id,
        data=TradeLogCreate(
            symbol="TCS",
            exchange="NSE",
            action="buy",
            quantity=10,
            price=4000,
            fees=0,
            trade_date=date.today(),
            tags=[],
        ),
    )
    await service.log_trade(
        user_id=test_user.id,
        data=TradeLogCreate(
            symbol="TCS",
            exchange="NSE",
            action="sell",
            quantity=4,
            price=4200,
            fees=0,
            trade_date=date.today(),
            tags=[],
        ),
    )

    summary = await service.calculate_portfolio(user_id=test_user.id)

    assert summary.holdings_count == 1
    assert summary.total_invested > 0
    assert summary.current_value > 0


@pytest.mark.asyncio
async def test_trade_analysis_with_ai_mock(db_session: AsyncSession, test_user, monkeypatch):
    service = TradingService(db_session)

    await service.log_trade(
        user_id=test_user.id,
        data=TradeLogCreate(
            symbol="ETHUSDT",
            exchange="BINANCE",
            action="buy",
            quantity=2,
            price=3000,
            fees=0,
            trade_date=date.today(),
            strategy="momentum",
            tags=[],
        ),
    )
    await service.log_trade(
        user_id=test_user.id,
        data=TradeLogCreate(
            symbol="ETHUSDT",
            exchange="BINANCE",
            action="sell",
            quantity=1,
            price=3300,
            fees=0,
            trade_date=date.today(),
            strategy="momentum",
            tags=[],
        ),
    )

    async def _fake_ai(_payload: dict) -> str:
        return "Risk adjusted performance is improving."

    monkeypatch.setattr(service, "_generate_ai_insights", _fake_ai)

    analysis = await service.analyze_trades(user_id=test_user.id, days=90)

    assert analysis.total_trades == 2
    assert analysis.most_traded_symbol == "ETHUSDT"
    assert "improving" in analysis.ai_insights.lower()
