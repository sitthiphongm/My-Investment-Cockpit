"""Pydantic schemas for portfolio rebalancing and risk metrics."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import TargetType


class TargetAllocationEntry(BaseModel):
    """Schema for a single target allocation entry."""

    target_key: str = Field(min_length=1, max_length=50)
    target_type: TargetType
    target_percentage: Decimal = Field(ge=Decimal("0.00"), le=Decimal("100.00"))


class TargetAllocationUpdate(BaseModel):
    """Schema for setting target allocations."""

    targets: list[TargetAllocationEntry] = Field(min_length=1)

    @field_validator("targets")
    @classmethod
    def targets_sum_to_100(cls, v: list[TargetAllocationEntry]) -> list[TargetAllocationEntry]:
        total = sum(entry.target_percentage for entry in v)
        if total != Decimal("100.00"):
            raise ValueError(
                f"Target allocations must sum to exactly 100%, got {total}%"
            )
        return v


class RebalancingPositionResponse(BaseModel):
    """Schema for a single position in rebalancing view."""

    target_key: str
    target_type: TargetType
    current_allocation: Decimal
    target_allocation: Decimal
    difference: Decimal
    is_overweight: bool
    is_underweight: bool
    suggested_action: Optional[str] = None


class RebalancingResponse(BaseModel):
    """Schema for rebalancing insights response."""

    positions: list[RebalancingPositionResponse]
    deviation_threshold: Decimal = Decimal("5.00")


class ConcentrationWarning(BaseModel):
    """Schema for a single concentration warning."""

    warning_type: str  # "sector" or "position"
    name: str  # sector name or stock symbol
    allocation_percent: Decimal
    threshold_percent: Decimal


class RiskMetricsResponse(BaseModel):
    """Schema for portfolio risk metrics response."""

    portfolio_beta: Optional[Decimal] = None
    max_drawdown_percent: Optional[Decimal] = None
    sector_concentration: list["SectorConcentrationEntry"]
    concentration_warnings: list[ConcentrationWarning]


class SectorConcentrationEntry(BaseModel):
    """Schema for sector concentration data."""

    sector: str
    allocation_percent: Decimal
    position_count: int
