"""Scenario Simulator API router."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.scenario_service import ScenarioInput, ScenarioSimulatorService

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


class SimulatedBuy(BaseModel):
    symbol: str
    quantity: int
    price: Decimal


class SimulatedSell(BaseModel):
    symbol: str
    quantity: int
    price: Decimal


class SimulationRequest(BaseModel):
    price_changes: dict[str, Decimal] | None = None
    simulated_buys: list[SimulatedBuy] | None = None
    simulated_sells: list[SimulatedSell] | None = None
    cash_deposit: Decimal | None = None
    fx_rate_change: Decimal | None = None


class SimulationResponse(BaseModel):
    current_total_cost: Decimal
    current_market_value: Decimal
    simulated_market_value: Decimal
    current_pl: Decimal
    simulated_pl: Decimal
    current_position_count: int
    simulated_position_count: int
    impact_on_value: Decimal
    impact_on_pl: Decimal
    warnings: list[str] | None


@router.post("/run", response_model=SimulationResponse)
async def run_simulation(
    request: SimulationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Run a portfolio scenario simulation.

    Models price changes, buys/sells, cash deposits without modifying real data.
    """
    service = ScenarioSimulatorService(db)
    scenario = ScenarioInput(
        price_changes=request.price_changes,
        simulated_buys=[b.model_dump() for b in request.simulated_buys] if request.simulated_buys else None,
        simulated_sells=[s.model_dump() for s in request.simulated_sells] if request.simulated_sells else None,
        cash_deposit=request.cash_deposit,
        fx_rate_change=request.fx_rate_change,
    )
    result = await service.run_simulation(user_id, scenario)
    return SimulationResponse(
        current_total_cost=result.current_total_cost,
        current_market_value=result.current_market_value,
        simulated_market_value=result.simulated_market_value,
        current_pl=result.current_pl,
        simulated_pl=result.simulated_pl,
        current_position_count=result.current_position_count,
        simulated_position_count=result.simulated_position_count,
        impact_on_value=result.impact_on_value,
        impact_on_pl=result.impact_on_pl,
        warnings=result.warnings,
    )
