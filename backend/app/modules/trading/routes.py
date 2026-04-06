"""
WILLIAM OS — Trading Routes
Trading dashboard endpoints for watchlist, trades, portfolio, and analysis.
"""

from __future__ import annotations

import uuid
from datetime import date

import structlog
from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.trading.schemas import TradeLogCreate, WatchlistCreate
from app.modules.trading.service import TradingService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/trading", tags=["Trading Dashboard"])


@router.post("/watchlist", status_code=201)
async def add_to_watchlist(
    data: WatchlistCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    item = await service.add_to_watchlist(user_id=user_id, data=data)
    return success(item.model_dump(mode="json"))


@router.get("/watchlist")
async def list_watchlist(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    rows = await service.list_watchlist(user_id=user_id)
    return success([item.model_dump(mode="json") for item in rows])


@router.delete("/watchlist/{watchlist_id}")
async def remove_from_watchlist(
    watchlist_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    await service.remove_from_watchlist(user_id=user_id, watchlist_id=watchlist_id)
    return success({"deleted": True})


@router.post("/trades", status_code=201)
async def log_trade(
    data: TradeLogCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    trade = await service.log_trade(user_id=user_id, data=data)
    return success(trade.model_dump(mode="json"))


@router.get("/trades")
async def list_trades(
    symbol: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    action: str | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    rows = await service.list_trades(
        user_id=user_id,
        symbol=symbol,
        date_from=date_from,
        date_to=date_to,
        action=action,
    )
    return success([item.model_dump(mode="json") for item in rows])


@router.get("/portfolio")
async def get_portfolio(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    summary = await service.calculate_portfolio(user_id=user_id)
    return success(summary.model_dump(mode="json"))


@router.get("/portfolio/history")
async def get_portfolio_history(
    days: int = Query(default=30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    history = await service.get_portfolio_history(user_id=user_id, days=days)
    return success([item.model_dump(mode="json") for item in history])


@router.post("/analyze")
async def analyze_trades(
    days: int = Query(default=90, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    analysis = await service.analyze_trades(user_id=user_id, days=days)
    return success(analysis.model_dump(mode="json"))


@router.get("/alerts")
async def check_price_alerts(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TradingService(db)
    alerts = await service.check_price_alerts(user_id=user_id)
    return success([item.model_dump(mode="json") for item in alerts])
