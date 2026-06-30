"""Pydantic schemas for trading transactions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import ActionType


class TransactionCreate(BaseModel):
    """Schema for creating a new buy/sell transaction."""

    date: date
    stock_symbol: str = Field(min_length=1, max_length=20)
    action: ActionType
    quantity: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    price_per_share: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    brokerage_fee: Decimal = Field(ge=0)
    vat: Decimal = Field(ge=0)
    broker: str = Field(min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=1000)

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

    @field_validator("broker")
    @classmethod
    def broker_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Broker name cannot be blank")
        return v.strip()


class TransactionUpdate(BaseModel):
    """Schema for editing an existing transaction.
    
    All fields are optional - only provided fields will be updated.
    """

    date: Optional[str] = None  # Accept as string, convert in service layer
    stock_symbol: Optional[str] = None
    action: Optional[ActionType] = None
    quantity: Optional[Decimal] = None
    price_per_share: Optional[Decimal] = None
    brokerage_fee: Optional[Decimal] = None
    vat: Optional[Decimal] = None
    broker: Optional[str] = None
    note: Optional[str] = None

    @field_validator("stock_symbol")
    @classmethod
    def symbol_uppercase(cls, v: Optional[str]) -> Optional[str]:
        import re
        if v is not None:
            v = v.upper()
            if not re.match(r"^[A-Z0-9.]+$", v):
                raise ValueError("Stock symbol must contain only uppercase letters, digits, and dots")
        return v

    @field_validator("broker")
    @classmethod
    def broker_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Broker name cannot be blank")
            return v.strip()
        return v


class SnapshotEntry(BaseModel):
    """Schema for a single snapshot import entry."""

    stock_symbol: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    price_per_share: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    broker: str = Field(min_length=1, max_length=100)

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

    @field_validator("broker")
    @classmethod
    def broker_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Broker name cannot be blank")
        return v.strip()


class SnapshotCreate(BaseModel):
    """Schema for bulk snapshot import request."""

    entries: list[SnapshotEntry] = Field(min_length=1)


class TransactionResponse(BaseModel):
    """Schema for transaction response."""

    id: str
    date: date
    stock_symbol: str
    action: ActionType
    quantity: Decimal
    price_per_share: Decimal
    gross_value: Decimal
    brokerage_fee: Decimal
    vat: Decimal
    net_capital_flow: Decimal
    broker: str
    note: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TransactionFilters(BaseModel):
    """Schema for transaction list query filters."""

    date_from: Optional[date] = None
    date_to: Optional[date] = None
    stock_symbol: Optional[str] = None
    broker: Optional[str] = None
    action: Optional[ActionType] = None
    tag: Optional[str] = None

    @field_validator("stock_symbol")
    @classmethod
    def symbol_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v
