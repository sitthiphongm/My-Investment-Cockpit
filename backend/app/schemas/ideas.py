"""Pydantic schemas for investment ideas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import IdeaStatus, RiskLevel


class IdeaCreate(BaseModel):
    """Schema for creating an investment idea."""

    stock_symbol: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    thesis: Optional[str] = Field(None, max_length=5000)
    target_entry_price: Optional[Decimal] = Field(None, gt=0, le=Decimal("99999999.99"))
    risk_level: RiskLevel
    source_link: Optional[str] = Field(None, max_length=500)
    status: IdeaStatus = IdeaStatus.RESEARCHING

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

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be blank")
        return v.strip()


class IdeaUpdate(BaseModel):
    """Schema for updating an investment idea."""

    stock_symbol: Optional[str] = Field(None, min_length=1, max_length=20)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    thesis: Optional[str] = Field(None, max_length=5000)
    target_entry_price: Optional[Decimal] = Field(None, gt=0, le=Decimal("99999999.99"))
    risk_level: Optional[RiskLevel] = None
    source_link: Optional[str] = Field(None, max_length=500)
    status: Optional[IdeaStatus] = None
    linked_transaction_id: Optional[str] = None

    @field_validator("stock_symbol")
    @classmethod
    def symbol_uppercase(cls, v: Optional[str]) -> Optional[str]:
        import re

        if v is not None:
            v = v.upper()
            if not re.match(r"^[A-Z0-9.]+$", v):
                raise ValueError(
                    "Stock symbol must contain only uppercase letters, digits, and dots"
                )
            return v
        return v

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Title cannot be blank")
            return v.strip()
        return v


class IdeaResponse(BaseModel):
    """Schema for investment idea response."""

    id: str
    stock_symbol: str
    title: str
    thesis: Optional[str] = None
    target_entry_price: Optional[Decimal] = None
    risk_level: RiskLevel
    source_link: Optional[str] = None
    status: IdeaStatus
    linked_transaction_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Optional market data
    current_price: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class IdeaListResponse(BaseModel):
    """Schema for idea list response."""

    ideas: list[IdeaResponse]


class IdeaFilters(BaseModel):
    """Schema for idea query filters."""

    status: Optional[IdeaStatus] = None
    risk_level: Optional[RiskLevel] = None
    stock_symbol: Optional[str] = None

    @field_validator("stock_symbol")
    @classmethod
    def symbol_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v
