"""Portfolio API routes."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis

from app.database import get_db
from app.dependencies import get_current_user_id
from app.redis import get_redis
from app.schemas.portfolio import (
    PortfolioSummaryResponse,
    SectorHeatmapResponse,
    SectorHeatmapEntry,
    SentimentUpdate,
)
from app.schemas.rebalancing import (
    RebalancingResponse,
    TargetAllocationUpdate,
)
from app.schemas.risk_metrics import RiskMetricsResponse
from app.services.alert_service import AlertService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService
from app.services.rebalancing_service import RebalancingService
from app.services.risk_metrics_service import RiskMetricsService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get aggregated portfolio summary with market data.

    Returns all currently held positions with calculated fields (avg cost,
    allocation, unrealized P/L, ROI) and auto-fetched market data from
    Yahoo Finance.
    """
    portfolio_service = PortfolioService(db)
    market_data_service = MarketDataService(redis_client)

    # Get held symbols to fetch market data
    symbols = await portfolio_service.get_held_symbols(user_id)

    # Fetch market data for all held symbols
    market_data = None
    if symbols:
        market_data = {}
        for symbol in symbols:
            ticker_info = await market_data_service.get_ticker_info(symbol)
            market_data[symbol] = ticker_info

    # Build portfolio summary with market data
    summary = await portfolio_service.get_summary(user_id, market_data)
    return summary


@router.post("/refresh", response_model=PortfolioSummaryResponse)
async def refresh_portfolio(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Force refresh market data for all held positions and return updated summary.

    Invalidates the Redis cache for all held symbols and re-fetches
    current market data from Yahoo Finance. Also checks and triggers
    any price alerts that match the refreshed prices.
    """
    portfolio_service = PortfolioService(db)
    market_data_service = MarketDataService(redis_client)

    # Get all held symbols
    symbols = await portfolio_service.get_held_symbols(user_id)

    # Force refresh all market data
    market_data = None
    if symbols:
        market_data = await market_data_service.refresh_all(symbols)

        # Check and trigger price alerts based on refreshed market prices
        market_prices: dict[str, Optional[Decimal]] = {}
        for symbol, ticker_info in market_data.items():
            market_prices[symbol] = ticker_info.current_price
        alert_service = AlertService(db)
        await alert_service.check_and_trigger_alerts(market_prices)

    # Build updated portfolio summary
    summary = await portfolio_service.get_summary(user_id, market_data)
    return summary


@router.put("/rebalancing/targets", status_code=200)
async def set_target_allocations(
    data: TargetAllocationUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set target allocations for portfolio rebalancing.

    Replaces all existing target allocations with the provided set.
    All target percentages must sum to exactly 100%.

    Each target entry specifies:
    - target_key: Stock symbol or sector name
    - target_type: "Symbol" or "Sector"
    - target_percentage: Target allocation percentage (0-100)
    """
    rebalancing_service = RebalancingService(db)
    records = await rebalancing_service.set_target_allocations(user_id, data)
    return {
        "message": "Target allocations updated successfully",
        "targets": [
            {
                "target_key": r.target_key,
                "target_type": r.target_type,
                "target_percentage": str(r.target_percentage),
            }
            for r in records
        ],
    }


@router.get("/rebalancing", response_model=RebalancingResponse)
async def get_rebalancing_insights(
    deviation_threshold: Decimal = Query(
        default=Decimal("5.00"),
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        description="Deviation threshold in percentage points (default 5pp)",
    ),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get portfolio rebalancing insights.

    Compares current allocation against target allocations, highlights
    over/under-weight positions based on the deviation threshold, and
    suggests buy/sell actions to reach target allocations.

    Query params:
    - deviation_threshold: Percentage points to flag over/under-weight (default 5)
    """
    portfolio_service = PortfolioService(db)
    market_data_service = MarketDataService(redis_client)
    rebalancing_service = RebalancingService(db)

    # Get held symbols and their data
    symbols = await portfolio_service.get_held_symbols(user_id)

    # Fetch market data for all held symbols
    market_data = {}
    if symbols:
        for symbol in symbols:
            ticker_info = await market_data_service.get_ticker_info(symbol)
            market_data[symbol] = ticker_info

    # Get full portfolio summary to extract allocations
    summary = await portfolio_service.get_summary(user_id, market_data)

    # Build current allocations dict and price/quantity maps
    current_allocations: dict[str, Decimal] = {}
    current_prices: dict[str, Optional[Decimal]] = {}
    position_quantities: dict[str, int] = {}

    for pos in summary.positions:
        current_allocations[pos.stock_symbol] = pos.allocation_percent
        current_prices[pos.stock_symbol] = pos.current_price
        position_quantities[pos.stock_symbol] = pos.quantity

    # Calculate total portfolio value
    total_portfolio_value = summary.total_market_value

    # Get rebalancing insights
    result = await rebalancing_service.get_rebalancing_insights(
        user_id=user_id,
        current_allocations=current_allocations,
        current_prices=current_prices,
        position_quantities=position_quantities,
        total_portfolio_value=total_portfolio_value,
        deviation_threshold=deviation_threshold,
    )

    return result


@router.get("/risk-metrics", response_model=RiskMetricsResponse)
async def get_risk_metrics(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get portfolio risk metrics.

    Returns:
    - Portfolio beta: weighted average of position betas by allocation
    - Sector concentration: % of portfolio per sector from Yahoo Finance data
    - Position concentration: % of portfolio per stock
    - Concentration warnings: sector > 50%, single stock > 25%
    - Maximum drawdown: largest peak-to-trough decline from performance snapshots
    """
    portfolio_service = PortfolioService(db)
    market_data_service = MarketDataService(redis_client)
    risk_metrics_service = RiskMetricsService(db)

    # Get held symbols
    symbols = await portfolio_service.get_held_symbols(user_id)

    if not symbols:
        return RiskMetricsResponse(
            portfolio_beta=None,
            sector_concentrations=[],
            position_concentrations=[],
            max_drawdown_percent=None,
            warnings=[],
        )

    # Fetch market data for all held symbols
    market_data = {}
    for symbol in symbols:
        ticker_info = await market_data_service.get_ticker_info(symbol)
        market_data[symbol] = ticker_info

    # Get allocations (based on total cost)
    position_allocations = await portfolio_service.calculate_allocation(user_id)

    # Calculate risk metrics
    result = await risk_metrics_service.get_risk_metrics(
        user_id=user_id,
        position_allocations=position_allocations,
        market_data=market_data,
    )

    return result


@router.get("/sector-heatmap", response_model=SectorHeatmapResponse)
async def get_sector_heatmap(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get sector heatmap data aggregated from portfolio positions.

    Aggregates positions by sector (from Yahoo Finance data) and returns:
    - sector: Sector name from yfinance
    - total_cost: Sum of total costs for all positions in this sector
    - total_market_value: Sum of market values for all positions in this sector
    - roi_percent: (total_market_value - total_cost) / total_cost × 100
    - allocation_percent: sector total_cost / overall total_cost × 100
    - position_count: Number of stocks in this sector
    """
    portfolio_service = PortfolioService(db)
    market_data_service = MarketDataService(redis_client)

    # Get held symbols
    symbols = await portfolio_service.get_held_symbols(user_id)

    if not symbols:
        return SectorHeatmapResponse(sectors=[])

    # Fetch market data for all held symbols
    market_data: dict[str, object] = {}
    for symbol in symbols:
        ticker_info = await market_data_service.get_ticker_info(symbol)
        market_data[symbol] = ticker_info

    # Get positions with holdings and calculate avg costs and total costs
    positions_data = await portfolio_service._get_positions_with_holdings(user_id)

    if not positions_data:
        return SectorHeatmapResponse(sectors=[])

    # Calculate avg_cost and total_cost for each position
    position_total_costs: dict[str, Decimal] = {}
    position_market_values: dict[str, Optional[Decimal]] = {}

    for symbol, qty in positions_data.items():
        avg_cost = await portfolio_service.calculate_avg_cost(user_id, symbol)
        total_cost = (avg_cost * Decimal(qty)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        position_total_costs[symbol] = total_cost

        # Calculate market value if price available
        ticker = market_data.get(symbol)
        if ticker and ticker.current_price is not None:
            market_value = (ticker.current_price * Decimal(qty)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            position_market_values[symbol] = market_value
        else:
            position_market_values[symbol] = None

    grand_total_cost = sum(position_total_costs.values(), Decimal("0"))

    # Aggregate by sector
    sector_data: dict[str, dict] = {}

    for symbol in positions_data.keys():
        ticker = market_data.get(symbol)
        sector = ticker.sector if ticker and ticker.sector else "Unknown"

        if sector not in sector_data:
            sector_data[sector] = {
                "total_cost": Decimal("0"),
                "total_market_value": Decimal("0"),
                "has_market_data": True,
                "position_count": 0,
            }

        sector_data[sector]["total_cost"] += position_total_costs[symbol]
        sector_data[sector]["position_count"] += 1

        mv = position_market_values[symbol]
        if mv is not None:
            sector_data[sector]["total_market_value"] += mv
        else:
            sector_data[sector]["has_market_data"] = False

    # Build response entries
    sectors: list[SectorHeatmapEntry] = []

    for sector_name, data in sector_data.items():
        sector_total_cost = data["total_cost"].quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Calculate allocation_percent
        if grand_total_cost != Decimal("0"):
            allocation_percent = (
                (sector_total_cost / grand_total_cost) * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            allocation_percent = Decimal("0.00")

        # Calculate total_market_value and roi_percent
        total_market_value: Optional[Decimal] = None
        roi_percent: Optional[Decimal] = None

        if data["has_market_data"]:
            total_market_value = data["total_market_value"].quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if sector_total_cost != Decimal("0"):
                roi_percent = (
                    ((total_market_value - sector_total_cost) / sector_total_cost)
                    * Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                roi_percent = Decimal("0.00")

        sectors.append(
            SectorHeatmapEntry(
                sector=sector_name,
                total_cost=sector_total_cost,
                total_market_value=total_market_value,
                roi_percent=roi_percent,
                allocation_percent=allocation_percent,
                position_count=data["position_count"],
            )
        )

    # Sort by allocation descending
    sectors.sort(key=lambda x: x.allocation_percent, reverse=True)

    return SectorHeatmapResponse(sectors=sectors)


@router.put("/{symbol}/sentiment", status_code=204)
async def set_sentiment(
    symbol: str,
    data: SentimentUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set Bear/Bull sentiment for a portfolio position.

    The sentiment is a personal assessment of the stock's outlook.
    Only valid values are "Bear" or "Bull".
    """
    portfolio_service = PortfolioService(db)
    await portfolio_service.set_sentiment(user_id, symbol, data.sentiment)
