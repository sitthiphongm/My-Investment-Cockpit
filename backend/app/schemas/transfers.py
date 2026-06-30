"""Pydantic schemas for money transfers."""

import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import Currency, TransferType


class TransferCreate(BaseModel):
    """Schema for creating a new money transfer."""

    date: dt.date
    broker: str = Field(min_length=1, max_length=100)
    transfer_type: TransferType
    amount: Decimal = Field(ge=Decimal("0.01"), le=Decimal("999999999.99"))

    # FX fields
    original_currency: Optional[Currency] = Currency.USD
    original_amount: Optional[Decimal] = Field(None, gt=Decimal("0"))
    fx_rate: Optional[Decimal] = Field(None, gt=Decimal("0"))
    fx_fee: Optional[Decimal] = Field(None, ge=Decimal("0"))
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today():
            raise ValueError("Date cannot be in the future")
        return v

    @field_validator("broker")
    @classmethod
    def broker_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Broker name cannot be blank")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def amount_max_decimals(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount must have at most 2 decimal places")
        return v

    @model_validator(mode="after")
    def validate_fx_fields(self) -> "TransferCreate":
        """When original_currency is not USD, fx_rate and original_amount are required."""
        if self.original_currency is not None and self.original_currency != Currency.USD:
            if self.fx_rate is None:
                raise ValueError(
                    "fx_rate is required when original_currency is not USD"
                )
            if self.original_amount is None:
                raise ValueError(
                    "original_amount is required when original_currency is not USD"
                )
        return self


class TransferUpdate(BaseModel):
    """Schema for editing an existing money transfer."""

    date: Optional[dt.date] = None
    broker: Optional[str] = Field(None, min_length=1, max_length=100)
    transfer_type: Optional[TransferType] = None
    amount: Optional[Decimal] = Field(None, ge=Decimal("0.01"), le=Decimal("999999999.99"))

    # FX fields (all optional for partial updates)
    original_currency: Optional[Currency] = None
    original_amount: Optional[Decimal] = Field(None, gt=Decimal("0"))
    fx_rate: Optional[Decimal] = Field(None, gt=Decimal("0"))
    fx_fee: Optional[Decimal] = Field(None, ge=Decimal("0"))
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("date")
    @classmethod
    def date_not_future(cls, v: Optional[dt.date]) -> Optional[dt.date]:
        if v is not None and v > dt.date.today():
            raise ValueError("Date cannot be in the future")
        return v

    @field_validator("broker")
    @classmethod
    def broker_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Broker name cannot be blank")
            return v.strip()
        return v

    @field_validator("amount")
    @classmethod
    def amount_max_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("Amount must have at most 2 decimal places")
        return v


class TransferResponse(BaseModel):
    """Schema for transfer response."""

    id: str
    date: dt.date
    broker: str
    transfer_type: TransferType
    amount: Decimal

    # FX fields
    original_currency: Optional[str] = None
    original_amount: Optional[Decimal] = None
    fx_rate: Optional[Decimal] = None
    converted_usd_amount: Optional[Decimal] = None
    fx_fee: Optional[Decimal] = None
    note: Optional[str] = None

    created_at: dt.datetime
    updated_at: Optional[dt.datetime] = None

    model_config = {"from_attributes": True}


class TransferFilters(BaseModel):
    """Schema for transfer list query filters."""

    broker: Optional[str] = None
    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
