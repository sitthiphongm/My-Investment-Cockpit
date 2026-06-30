"""Pydantic schemas for stock screener."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ScreenerFilterCreate(BaseModel):
    """Schema for executing a screener search query."""

    pe_min: Optional[Decimal] = None
    pe_max: Optional[Decimal] = None
    dividend_yield_min: Optional[Decimal] = None
    dividend_yield_max: Optional[Decimal] = None
    market_cap_min: Optional[int] = None
    market_cap_max: Optional[int] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    beta_min: Optional[Decimal] = None
    beta_max: Optional[Decimal] = None
    price_to_book_min: Optional[Decimal] = None
    price_to_book_max: Optional[Decimal] = None
    peg_ratio_min: Optional[Decimal] = None
    peg_ratio_max: Optional[Decimal] = None
    price_to_sales_min: Optional[Decimal] = None
    price_to_sales_max: Optional[Decimal] = None
    revenue_growth_min: Optional[Decimal] = None
    revenue_growth_max: Optional[Decimal] = None
    short_percent_min: Optional[Decimal] = None
    short_percent_max: Optional[Decimal] = None


class ScreenerPresetCreate(BaseModel):
    """Schema for saving a screener preset."""

    name: str = Field(min_length=1, max_length=100)
    filter_criteria: ScreenerFilterCreate

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Preset name cannot be blank")
        return v.strip()


class ScreenerPresetResponse(BaseModel):
    """Schema for screener preset response."""

    id: str
    name: str
    filter_criteria: ScreenerFilterCreate
    created_at: datetime

    model_config = {"from_attributes": True}


class ScreenerResultEntry(BaseModel):
    """Schema for a single stock in screener results."""

    stock_symbol: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[Decimal] = None
    pe_trailing: Optional[Decimal] = None
    pe_forward: Optional[Decimal] = None
    peg_ratio: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    market_cap: Optional[int] = None
    beta: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = None
    price_to_sales: Optional[Decimal] = None
    revenue_growth: Optional[Decimal] = None
    short_percent_of_float: Optional[Decimal] = None


class ScreenerSearchResponse(BaseModel):
    """Schema for screener search response."""

    results: list[ScreenerResultEntry]
    total_matches: int


class ScreenerPresetListResponse(BaseModel):
    """Schema for screener preset list response."""

    presets: list[ScreenerPresetResponse]
