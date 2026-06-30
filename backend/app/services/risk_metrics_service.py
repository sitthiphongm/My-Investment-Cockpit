"""Risk metrics service - Portfolio risk analysis and concentration warnings.

Provides:
- Portfolio beta (weighted average of position betas by allocation)
- Sector concentration (% of portfolio per sector)
- Position concentration (% of portfolio per stock)
- Concentration warnings (sector > 50%, position > 25%)
- Maximum drawdown (largest peak-to-trough decline from performance snapshots)
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance_snapshot import PerformanceSnapshot
from app.schemas.market_data import TickerInfo
from app.schemas.risk_metrics import (
    ConcentrationWarning,
    PositionConcentration,
    RiskMetricsResponse,
    SectorConcentration,
)

TWO_PLACES = Decimal("0.01")
SECTOR_CONCENTRATION_THRESHOLD = Decimal("50.00")
POSITION_CONCENTRATION_THRESHOLD = Decimal("25.00")


class RiskMetricsService:
    """Service for computing portfolio risk metrics.

    Key calculations:
    - portfolio_beta = Σ(allocation_weight_i × beta_i) for all positions with known beta
    - sector_concentration = % of Total Cost per sector (from yfinance data)
    - position_concentration = % of Total Cost per stock
    - max_drawdown = largest (peak - trough) / peak × 100 from performance snapshots

    Warnings are generated when:
    - Any single sector > 50% of total portfolio value
    - Any single stock > 25% of total portfolio value
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_risk_metrics(
        self,
        user_id: uuid.UUID,
        position_allocations: dict[str, Decimal],
        market_data: dict[str, TickerInfo],
    ) -> RiskMetricsResponse:
        """Compute all risk metrics for a portfolio.

        Args:
            user_id: The authenticated user's ID.
            position_allocations: Dict mapping stock symbol -> allocation % (by total cost).
            market_data: Dict mapping stock symbol -> TickerInfo with beta and sector fields.

        Returns:
            RiskMetricsResponse with portfolio beta, concentrations, warnings, and max drawdown.
        """
        # Calculate portfolio beta
        portfolio_beta = self._calculate_portfolio_beta(
            position_allocations, market_data
        )

        # Calculate sector concentration
        sector_concentrations = self._calculate_sector_concentration(
            position_allocations, market_data
        )

        # Calculate position concentration
        position_concentrations = self._calculate_position_concentration(
            position_allocations
        )

        # Generate concentration warnings
        warnings = self._generate_warnings(
            sector_concentrations, position_concentrations
        )

        # Calculate max drawdown from performance snapshots
        max_drawdown = await self._calculate_max_drawdown(user_id)

        return RiskMetricsResponse(
            portfolio_beta=portfolio_beta,
            sector_concentrations=sector_concentrations,
            position_concentrations=position_concentrations,
            max_drawdown_percent=max_drawdown,
            warnings=warnings,
        )

    def _calculate_portfolio_beta(
        self,
        position_allocations: dict[str, Decimal],
        market_data: dict[str, TickerInfo],
    ) -> Optional[Decimal]:
        """Calculate portfolio beta as weighted average of position betas.

        Formula: portfolio_beta = Σ(allocation_weight_i × beta_i)
        where allocation_weight_i = allocation_percent_i / 100

        Returns None if no positions have known beta values.
        """
        if not position_allocations:
            return None

        weighted_beta_sum = Decimal("0")
        total_weight_with_beta = Decimal("0")
        has_any_beta = False

        for symbol, allocation_pct in position_allocations.items():
            ticker = market_data.get(symbol)
            if ticker and ticker.beta is not None:
                weight = allocation_pct / Decimal("100")
                weighted_beta_sum += weight * ticker.beta
                total_weight_with_beta += weight
                has_any_beta = True

        if not has_any_beta:
            return None

        # Normalize by the weight of positions that have beta data
        if total_weight_with_beta > Decimal("0"):
            portfolio_beta = (
                weighted_beta_sum / total_weight_with_beta
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            return None

        return portfolio_beta

    def _calculate_sector_concentration(
        self,
        position_allocations: dict[str, Decimal],
        market_data: dict[str, TickerInfo],
    ) -> list[SectorConcentration]:
        """Calculate sector concentration from yfinance data.

        Groups positions by their sector (from TickerInfo) and sums allocation percentages.
        Positions without sector data are grouped under "Unknown".

        Returns list of SectorConcentration sorted by allocation descending.
        """
        sector_data: dict[str, dict] = {}

        for symbol, allocation_pct in position_allocations.items():
            ticker = market_data.get(symbol)
            sector = ticker.sector if ticker and ticker.sector else "Unknown"

            if sector not in sector_data:
                sector_data[sector] = {
                    "allocation_percent": Decimal("0"),
                    "position_count": 0,
                }

            sector_data[sector]["allocation_percent"] += allocation_pct
            sector_data[sector]["position_count"] += 1

        # Build response entries
        concentrations = [
            SectorConcentration(
                sector=sector,
                allocation_percent=data["allocation_percent"].quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                ),
                position_count=data["position_count"],
            )
            for sector, data in sector_data.items()
        ]

        # Sort by allocation descending
        concentrations.sort(key=lambda x: x.allocation_percent, reverse=True)
        return concentrations

    def _calculate_position_concentration(
        self,
        position_allocations: dict[str, Decimal],
    ) -> list[PositionConcentration]:
        """Calculate position concentration (each stock's % of portfolio).

        Returns list of PositionConcentration sorted by allocation descending.
        """
        concentrations = [
            PositionConcentration(
                stock_symbol=symbol,
                allocation_percent=allocation_pct.quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                ),
            )
            for symbol, allocation_pct in position_allocations.items()
        ]

        concentrations.sort(key=lambda x: x.allocation_percent, reverse=True)
        return concentrations

    def _generate_warnings(
        self,
        sector_concentrations: list[SectorConcentration],
        position_concentrations: list[PositionConcentration],
    ) -> list[ConcentrationWarning]:
        """Generate concentration warnings when thresholds are exceeded.

        Warnings:
        - Sector > 50% of portfolio → sector concentration warning
        - Single stock > 25% of portfolio → position concentration warning
        """
        warnings: list[ConcentrationWarning] = []

        # Check sector concentration (> 50%)
        for sector_entry in sector_concentrations:
            if sector_entry.allocation_percent > SECTOR_CONCENTRATION_THRESHOLD:
                warnings.append(
                    ConcentrationWarning(
                        warning_type="sector",
                        name=sector_entry.sector,
                        allocation_percent=sector_entry.allocation_percent,
                        threshold_percent=SECTOR_CONCENTRATION_THRESHOLD,
                    )
                )

        # Check position concentration (> 25%)
        for position_entry in position_concentrations:
            if position_entry.allocation_percent > POSITION_CONCENTRATION_THRESHOLD:
                warnings.append(
                    ConcentrationWarning(
                        warning_type="position",
                        name=position_entry.stock_symbol,
                        allocation_percent=position_entry.allocation_percent,
                        threshold_percent=POSITION_CONCENTRATION_THRESHOLD,
                    )
                )

        return warnings

    async def _calculate_max_drawdown(
        self, user_id: uuid.UUID
    ) -> Optional[Decimal]:
        """Calculate maximum drawdown from performance snapshots.

        Max drawdown = largest (peak - trough) / peak × 100
        where we track the running peak and compute the drawdown at each point.

        Returns None if fewer than 2 snapshots exist.
        """
        stmt = (
            select(PerformanceSnapshot.total_portfolio_value)
            .where(PerformanceSnapshot.user_id == user_id)
            .order_by(PerformanceSnapshot.date.asc(), PerformanceSnapshot.created_at.asc())
        )

        result = await self.db.execute(stmt)
        values = [row[0] for row in result.all()]

        if len(values) < 2:
            return None

        return self._compute_max_drawdown(values)

    @staticmethod
    def _compute_max_drawdown(values: list[Decimal]) -> Optional[Decimal]:
        """Compute max drawdown from a sequence of portfolio values.

        Iterates through values tracking the running peak and the maximum
        percentage decline from any peak to any subsequent trough.

        Formula: drawdown = (peak - current) / peak × 100

        Returns the largest drawdown percentage, or Decimal("0.00") if
        there is no decline.
        """
        if len(values) < 2:
            return None

        max_drawdown = Decimal("0")
        peak = values[0]

        for value in values[1:]:
            if value > peak:
                peak = value
            elif peak > Decimal("0"):
                drawdown = ((peak - value) / peak) * Decimal("100")
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        return max_drawdown.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
