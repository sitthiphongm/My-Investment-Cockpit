"""Pydantic schemas for portfolio risk metrics."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SectorConcentration(BaseModel):
    """A single sector's concentration in the portfolio."""

    sector: str
    allocation_percent: Decimal
    position_count: int


class PositionConcentration(BaseModel):
    """A single position's concentration in the portfolio."""

    stock_symbol: str
    allocation_percent: Decimal


class ConcentrationWarning(BaseModel):
    """A warning when concentration exceeds thresholds."""

    warning_type: str  # "sector" or "position"
    name: str  # sector name or stock symbol
    allocation_percent: Decimal
    threshold_percent: Decimal


class RiskMetricsResponse(BaseModel):
    """Response schema for portfolio risk metrics."""

    portfolio_beta: Optional[Decimal] = None
    sector_concentrations: list[SectorConcentration] = []
    position_concentrations: list[PositionConcentration] = []
    max_drawdown_percent: Optional[Decimal] = None
    warnings: list[ConcentrationWarning] = []
