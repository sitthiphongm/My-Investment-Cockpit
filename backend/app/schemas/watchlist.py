"""Pydantic schemas for watchlist."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WatchlistItemCreate(BaseModel):
    """Schema for adding a stock to the watchlist."""

    stock_symbol: str = Field(min_length=1, max_length=20)
    interested_at_price: Optional[Decimal] = Field(None, gt=0, le=Decimal("99999999.99"))
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("stock_symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        import re

        v = v.upper()
        if not re.match(r"^[A-Z0-9.]+$", v):
            raise ValueError(
                "Stock symbol must contain only uppercase letters, digits, and dots"
            )
        return v


class WatchlistItemUpdate(BaseModel):
    """Schema for updating a watchlist item."""

    interested_at_price: Optional[Decimal] = Field(None, gt=0, le=Decimal("99999999.99"))
    notes: Optional[str] = Field(None, max_length=500)


class WatchlistItemResponse(BaseModel):
    """Schema for watchlist item response."""

    id: str
    stock_symbol: str
    interested_at_price: Optional[Decimal] = None
    notes: Optional[str] = None
    at_target: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Market data fields (per Requirement 19.3)
    company_name: Optional[str] = None
    current_price: Optional[Decimal] = None
    day_change_percent: Optional[Decimal] = None
    fifty_two_week_low: Optional[Decimal] = None
    fifty_two_week_high: Optional[Decimal] = None
    pe_trailing: Optional[Decimal] = None
    sector: Optional[str] = None

    model_config = {"from_attributes": True}


class WatchlistResponse(BaseModel):
    """Schema for watchlist list response."""

    items: list[WatchlistItemResponse]
