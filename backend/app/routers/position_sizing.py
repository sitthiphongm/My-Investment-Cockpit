"""Position Sizing API router."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.position_sizing_service import PositionSizeInput, PositionSizingService

router = APIRouter(prefix="/api/rebalancing", tags=["rebalancing"])


class PositionSizeRequest(BaseModel):
    portfolio_value: Decimal = Field(gt=0, description="Total portfolio value in USD")
    max_risk_per_trade: Decimal = Field(gt=0, le=Decimal("0.5"), description="Max risk per trade as decimal (e.g., 0.02 for 2%)")
    entry_price: Decimal = Field(gt=0, description="Planned entry price per share")
    stop_loss_price: Decimal = Field(gt=0, description="Stop loss price per share")
    confidence_score: int | None = Field(None, ge=1, le=10, description="Confidence score 1-10")
    target_allocation: Decimal | None = Field(None, ge=0, le=100, description="Max allocation percentage")


class PositionSizeResponse(BaseModel):
    suggested_shares: int
    capital_required: Decimal
    portfolio_allocation_pct: Decimal
    expected_downside: Decimal
    risk_per_share: Decimal
    max_position_value: Decimal
    warnings: list[str]


@router.post("/position-size", response_model=PositionSizeResponse)
async def calculate_position_size(request: PositionSizeRequest):
    """Calculate recommended position size based on risk parameters.

    Formula:
    - max_position_value = portfolio_value × max_risk_per_trade
    - risk_per_share = entry_price - stop_loss_price
    - suggested_shares = max_position_value / risk_per_share
    """
    if request.stop_loss_price >= request.entry_price:
        raise HTTPException(
            status_code=400,
            detail="Stop loss price must be below entry price",
        )

    service = PositionSizingService()
    params = PositionSizeInput(
        portfolio_value=request.portfolio_value,
        max_risk_per_trade=request.max_risk_per_trade,
        entry_price=request.entry_price,
        stop_loss_price=request.stop_loss_price,
        confidence_score=request.confidence_score,
        target_allocation=request.target_allocation,
    )

    try:
        result = service.calculate(params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PositionSizeResponse(
        suggested_shares=result.suggested_shares,
        capital_required=result.capital_required,
        portfolio_allocation_pct=result.portfolio_allocation_pct,
        expected_downside=result.expected_downside,
        risk_per_share=result.risk_per_share,
        max_position_value=result.max_position_value,
        warnings=result.warnings,
    )
