"""Pydantic schemas for dividend tracking."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DividendCreate(BaseModel):
    """Schema for recording a dividend payment."""

    date: date
    stock_symbol: str = Field(min_length=1, max_length=20)
    amount_per_share: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    shares_held: int = Field(gt=0, le=99_999_999)
    total_amount: Decimal = Field(gt=0, le=Decimal("999999999.99"))

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date cannot be in the future")
        return v

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

    @field_validator("total_amount")
    @classmethod
    def amount_max_decimals(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount must have at most 2 decimal places")
        return v


class DividendResponse(BaseModel):
    """Schema for dividend record response."""

    id: str
    date: date
    stock_symbol: str
    amount_per_share: Decimal
    shares_held: int
    total_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class DividendSummaryEntry(BaseModel):
    """Schema for dividend summary by stock or period."""

    stock_symbol: Optional[str] = None
    period: Optional[str] = None  # e.g., "2024-01" or "2024"
    total_dividends: Decimal
    record_count: int


class DividendSummaryResponse(BaseModel):
    """Schema for dividend summary response."""

    entries: list[DividendSummaryEntry]
    total_all_dividends: Decimal


class DividendProjectionResponse(BaseModel):
    """Schema for projected annual dividend income."""

    projections: list["DividendProjectionEntry"]
    total_projected_annual: Decimal


class DividendProjectionEntry(BaseModel):
    """Schema for per-stock dividend projection."""

    stock_symbol: str
    current_shares: int
    last_dividend_per_share: Decimal
    projected_annual: Decimal
    yield_on_cost: Optional[Decimal] = None


class DividendFilters(BaseModel):
    """Schema for dividend query filters."""

    stock_symbol: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    group_by: Optional[str] = None  # "stock", "monthly", "yearly"

    @field_validator("stock_symbol")
    @classmethod
    def symbol_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v
