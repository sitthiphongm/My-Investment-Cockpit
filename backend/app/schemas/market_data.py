"""Pydantic schemas for market data from Yahoo Finance."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class TickerInfo(BaseModel):
    """Market data for a single stock ticker fetched from yfinance."""

    symbol: str
    long_name: Optional[str] = None
    current_price: Optional[Decimal] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    previous_close: Optional[Decimal] = None
    day_high: Optional[Decimal] = None
    day_low: Optional[Decimal] = None
    fifty_two_week_low: Optional[Decimal] = None
    fifty_two_week_high: Optional[Decimal] = None
    market_cap: Optional[int] = None
    trailing_pe: Optional[Decimal] = None
    forward_pe: Optional[Decimal] = None
    average_volume: Optional[int] = None
    beta: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = None
    last_refresh: Optional[datetime] = None
    is_stale: bool = False

    model_config = {"from_attributes": True}


class TrendingStock(BaseModel):
    """A single trending stock entry."""

    symbol: str
    company_name: Optional[str] = None
    current_price: Optional[Decimal] = None
    day_change_percent: Optional[Decimal] = None
    volume: Optional[int] = None
    market_cap: Optional[int] = None
    sector: Optional[str] = None
    pe_trailing: Optional[Decimal] = None
    reason: Optional[str] = None


class TrendingData(BaseModel):
    """Trending market data including gainers, losers, and most active."""

    gainers: list[TrendingStock] = []
    losers: list[TrendingStock] = []
    most_active: list[TrendingStock] = []
    last_refresh: Optional[datetime] = None
    is_stale: bool = False
