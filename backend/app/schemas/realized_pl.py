"""Pydantic schemas for realized P/L tracking."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from .enums import TermType


class RealizedPLResponse(BaseModel):
    """Schema for a single realized P/L record response."""

    id: str
    date: date
    stock_symbol: str
    sell_quantity: int
    sell_price: Decimal
    avg_cost_at_sale: Decimal
    realized_pl: Decimal
    hold_duration_days: int
    term_type: TermType
    transaction_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RealizedPLListResponse(BaseModel):
    """Schema for realized P/L list response."""

    records: list[RealizedPLResponse]


class RealizedPLSummaryEntry(BaseModel):
    """Schema for a realized P/L summary period entry."""

    period: str  # "2024-01" for monthly, "2024" for yearly, "all-time"
    total_realized_pl: Decimal
    total_short_term: Decimal
    total_long_term: Decimal
    record_count: int


class RealizedPLSummaryResponse(BaseModel):
    """Schema for realized P/L summary response."""

    entries: list[RealizedPLSummaryEntry]
    all_time_total: Decimal
    all_time_short_term: Decimal
    all_time_long_term: Decimal


class RealizedPLFilters(BaseModel):
    """Schema for realized P/L query filters."""

    stock_symbol: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    term_type: Optional[TermType] = None
    group_by: Optional[str] = None  # "monthly" or "yearly"
