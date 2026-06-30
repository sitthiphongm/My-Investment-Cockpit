"""Pydantic schemas for portfolio summary."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from .enums import SentimentType


class PortfolioPositionResponse(BaseModel):
    """Schema for a single portfolio position response."""

    stock_symbol: str
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    market_value: Optional[Decimal] = None
    unrealized_pl: Optional[Decimal] = None
    roi_percent: Optional[Decimal] = None
    allocation_percent: Decimal
    sentiment: Optional[SentimentType] = None

    # Market data fields (from Yahoo Finance)
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[Decimal] = None
    previous_close: Optional[Decimal] = None
    day_high: Optional[Decimal] = None
    day_low: Optional[Decimal] = None
    fifty_two_week_low: Optional[Decimal] = None
    fifty_two_week_high: Optional[Decimal] = None
    market_cap: Optional[int] = None
    pe_trailing: Optional[Decimal] = None
    pe_forward: Optional[Decimal] = None
    average_volume: Optional[int] = None
    beta: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = None
    last_refresh: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PortfolioSummaryResponse(BaseModel):
    """Schema for the full portfolio summary response."""

    positions: list[PortfolioPositionResponse]
    total_cost: Decimal
    total_market_value: Optional[Decimal] = None
    total_unrealized_pl: Optional[Decimal] = None
    overall_roi_percent: Optional[Decimal] = None
    market_data_complete: bool = False


class SentimentUpdate(BaseModel):
    """Schema for updating sentiment on a position."""

    sentiment: SentimentType


class SectorHeatmapEntry(BaseModel):
    """Schema for a single sector in the heatmap response."""

    sector: str
    total_cost: Decimal
    total_market_value: Optional[Decimal] = None
    roi_percent: Optional[Decimal] = None
    allocation_percent: Decimal
    position_count: int


class SectorHeatmapResponse(BaseModel):
    """Schema for sector heatmap response."""

    sectors: list[SectorHeatmapEntry]
