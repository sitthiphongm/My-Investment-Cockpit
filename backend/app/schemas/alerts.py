"""Pydantic schemas for price alerts."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import AlertType


class AlertCreate(BaseModel):
    """Schema for creating a price alert."""

    stock_symbol: str = Field(min_length=1, max_length=20)
    alert_type: AlertType
    target_price: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    note: Optional[str] = Field(None, max_length=500)

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


class AlertResponse(BaseModel):
    """Schema for price alert response."""

    id: str
    stock_symbol: str
    alert_type: AlertType
    target_price: Decimal
    note: Optional[str] = None
    triggered: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Schema for alert list response."""

    alerts: list[AlertResponse]
