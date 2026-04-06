"""
WILLIAM OS — Trading Schemas
Request and response models for trading dashboard operations.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class WatchlistCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    exchange: str = Field(default="NSE", min_length=1, max_length=20)
    asset_type: str = Field(default="equity", min_length=1, max_length=20)
    alert_price_above: float | None = None
    alert_price_below: float | None = None
    notes: str | None = None


class WatchlistUpdate(BaseModel):
    alert_price_above: float | None = None
    alert_price_below: float | None = None
    notes: str | None = None
    is_active: bool | None = None


class WatchlistResponse(BaseModel):
    id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    asset_type: str
    alert_price_above: float | None
    alert_price_below: float | None
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TradeLogCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    exchange: str = Field(min_length=1, max_length=20)
    action: str = Field(min_length=1, max_length=10)
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0, ge=0)
    trade_date: date
    trade_time: time | None = None
    strategy: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class TradeLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    action: str
    quantity: float
    price: float
    total_value: float
    fees: float
    trade_date: date
    trade_time: time | None
    strategy: str | None
    notes: str | None
    tags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioSnapshotResponse(BaseModel):
    id: UUID
    user_id: UUID
    snapshot_date: date
    total_invested: float
    current_value: float
    total_pnl: float
    daily_pnl: float
    holdings: dict
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    total_invested: float
    current_value: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    holdings_count: int
    top_gainers: list[dict]
    top_losers: list[dict]


class TradeAnalysis(BaseModel):
    total_trades: int
    win_rate: float
    avg_return: float
    best_trade: dict | None
    worst_trade: dict | None
    most_traded_symbol: str | None
    strategy_performance: dict
    ai_insights: str


class PriceAlertResponse(BaseModel):
    id: UUID
    user_id: UUID
    watchlist_id: UUID
    alert_type: str
    target_price: float
    triggered: bool
    triggered_at: datetime | None
    notification_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}
