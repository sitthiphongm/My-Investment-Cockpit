"""Pydantic schemas for FX rate caching and manual entry."""

import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FXRateCreate(BaseModel):
    """Schema for creating/storing a manual or cached FX rate entry."""

    currency_pair: str = Field(
        ...,
        min_length=7,
        max_length=7,
        description="Currency pair in format 'XXX/YYY', e.g. 'THB/USD'",
    )
    date: dt.date = Field(..., description="Date the rate applies to")
    rate: Decimal = Field(
        ...,
        gt=Decimal("0"),
        le=Decimal("999999.999999"),
        description="Exchange rate value (must be positive)",
    )
    provider: Optional[str] = Field(
        None,
        max_length=50,
        description="Provider name (e.g. 'manual', 'unirate', 'alpha_vantage')",
    )

    @field_validator("currency_pair")
    @classmethod
    def validate_currency_pair(cls, v: str) -> str:
        """Validate currency pair format: exactly 'XXX/YYY' with uppercase letters."""
        if len(v) != 7 or v[3] != "/":
            raise ValueError("Currency pair must be in format 'XXX/YYY' (e.g. 'THB/USD')")
        base = v[:3]
        quote = v[4:]
        if not base.isalpha() or not quote.isalpha():
            raise ValueError("Currency codes must be alphabetic")
        if base == quote:
            raise ValueError("Base and quote currencies must be different")
        return v.upper()

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today():
            raise ValueError("Date cannot be in the future")
        return v

    @field_validator("rate")
    @classmethod
    def rate_max_decimals(cls, v: Decimal) -> Decimal:
        """Ensure rate has at most 6 decimal places."""
        if v.as_tuple().exponent < -6:
            raise ValueError("Rate must have at most 6 decimal places")
        return v


class FXRateQuery(BaseModel):
    """Schema for querying cached FX rates."""

    currency_pair: str = Field(
        ...,
        min_length=7,
        max_length=7,
        description="Currency pair in format 'XXX/YYY'",
    )
    date: dt.date = Field(..., description="Date to look up the rate for")

    @field_validator("currency_pair")
    @classmethod
    def validate_currency_pair(cls, v: str) -> str:
        if len(v) != 7 or v[3] != "/":
            raise ValueError("Currency pair must be in format 'XXX/YYY' (e.g. 'THB/USD')")
        base = v[:3]
        quote = v[4:]
        if not base.isalpha() or not quote.isalpha():
            raise ValueError("Currency codes must be alphabetic")
        return v.upper()


class FXRateResponse(BaseModel):
    """Schema for FX rate response."""

    id: str
    currency_pair: str
    date: dt.date
    rate: Decimal
    provider: Optional[str] = None
    source_timestamp: Optional[dt.datetime] = None
    fetch_timestamp: Optional[dt.datetime] = None
    is_manual: bool = False
    is_stale: bool = False
    created_at: dt.datetime

    model_config = {"from_attributes": True}
