"""Pydantic schemas for performance history."""

import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SnapshotCreate(BaseModel):
    """Schema for recording a portfolio value snapshot."""

    date: dt.date
    total_portfolio_value: Decimal = Field(ge=Decimal("0.00"), le=Decimal("999999999.99"))
    total_cost: Decimal = Field(ge=Decimal("0.00"), le=Decimal("999999999.99"))

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today():
            raise ValueError("Date cannot be in the future")
        return v

    @field_validator("total_portfolio_value", "total_cost")
    @classmethod
    def amount_max_decimals(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Value must have at most 2 decimal places")
        return v


class SnapshotUpdate(BaseModel):
    """Schema for editing an existing performance snapshot."""

    date: Optional[dt.date] = None
    total_portfolio_value: Optional[Decimal] = Field(
        None, ge=Decimal("0.00"), le=Decimal("999999999.99")
    )
    total_cost: Optional[Decimal] = Field(
        None, ge=Decimal("0.00"), le=Decimal("999999999.99")
    )

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: Optional[dt.date]) -> Optional[dt.date]:
        if v is not None and v > dt.date.today():
            raise ValueError("Date cannot be in the future")
        return v

    @field_validator("total_portfolio_value", "total_cost")
    @classmethod
    def amount_max_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("Value must have at most 2 decimal places")
        return v


class PerformanceSnapshotResponse(BaseModel):
    """Schema for performance snapshot response."""

    id: str
    date: dt.date
    total_portfolio_value: Decimal
    total_cost: Decimal
    pl: Decimal
    period_return: Optional[Decimal] = None
    created_at: dt.datetime
    updated_at: Optional[dt.datetime] = None

    model_config = {"from_attributes": True}


class CumulativeReturnResponse(BaseModel):
    """Schema for cumulative return summary."""

    cumulative_return_percent: Optional[Decimal] = None
    earliest_value: Optional[Decimal] = None
    latest_value: Optional[Decimal] = None
    earliest_date: Optional[dt.date] = None
    latest_date: Optional[dt.date] = None


class PerformanceListResponse(BaseModel):
    """Schema for performance snapshot list with cumulative return."""

    snapshots: list[PerformanceSnapshotResponse]
    cumulative_return: CumulativeReturnResponse


class SnapshotFilters(BaseModel):
    """Schema for performance snapshot query filters."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    aggregation: Optional[str] = None  # "monthly" or "yearly"
