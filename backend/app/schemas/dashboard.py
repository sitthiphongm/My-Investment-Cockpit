"""Pydantic schemas for dashboard."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class BrokerCapital(BaseModel):
    """Schema for capital breakdown per broker."""

    broker: str
    total_in: Decimal
    total_out: Decimal
    net_capital: Decimal


class DashboardResponse(BaseModel):
    """Schema for dashboard overview response."""

    total_invested: Decimal
    total_withdrawn: Decimal
    net_invested: Decimal
    total_market_value: Optional[Decimal] = None
    overall_pl: Optional[Decimal] = None
    overall_roi_percent: Optional[Decimal] = None
    total_positions: int
    total_brokers: int
    capital_per_broker: list[BrokerCapital]
    market_data_complete: bool
