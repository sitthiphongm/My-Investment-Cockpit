"""Dashboard service - Business logic for dashboard overview calculations."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.schemas.dashboard import BrokerCapital, DashboardResponse
from app.schemas.market_data import TickerInfo
from app.services.portfolio_service import PortfolioService


TWO_PLACES = Decimal("0.01")


class DashboardService:
    """Service for computing dashboard overview data.

    Aggregates data from transfers and portfolio positions to provide:
    - Total Invested / Withdrawn / Net Invested
    - Total Market Value / Overall P/L / Overall ROI
    - Capital per broker breakdown
    - Position and broker counts

    Handles edge cases:
    - No data: all monetary values = 0.00, counts = 0
    - Incomplete market data: market value and P/L = None (not available)
    """

    def __init__(self, db: AsyncSession, market_data_service=None):
        self.db = db
        self.market_data_service = market_data_service

    async def get_overview(
        self, user_id: uuid.UUID, market_data: Optional[dict[str, TickerInfo]] = None
    ) -> DashboardResponse:
        """Get the full dashboard overview for a user.

        Steps:
        1. Query all transfers grouped by broker and type to calculate:
           - Total Invested (sum of "In" transfers)
           - Total Withdrawn (sum of "Out" transfers)
           - Net Invested (In - Out)
           - Capital per broker (net "In" - "Out" per broker)
           - Distinct broker count
        2. Query held positions (quantity > 0) for:
           - Total positions count
           - Total Cost (Σ avg_cost × qty)
           - Total Market Value (Σ qty × current_price) if market data available
        3. Calculate Overall P/L and ROI from market value and total cost

        Args:
            user_id: The authenticated user's ID.
            market_data: Optional pre-fetched dict mapping symbol -> TickerInfo.

        Returns:
            DashboardResponse with all dashboard aggregations.
        """
        # Step 1: Transfer aggregations
        transfer_data = await self._get_transfer_aggregations(user_id)
        total_invested = transfer_data["total_invested"]
        total_withdrawn = transfer_data["total_withdrawn"]
        net_invested = total_invested - total_withdrawn
        capital_per_broker = transfer_data["capital_per_broker"]
        total_brokers = transfer_data["total_brokers"]

        # Step 2: Portfolio positions
        positions_data = await self._get_positions_with_holdings(user_id)
        total_positions = len(positions_data)

        if total_positions == 0:
            # No positions held - return with transfer data only
            return DashboardResponse(
                total_invested=total_invested.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                total_withdrawn=total_withdrawn.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                net_invested=net_invested.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                total_market_value=Decimal("0.00"),
                overall_pl=Decimal("0.00"),
                overall_roi_percent=Decimal("0.00"),
                total_positions=0,
                total_brokers=total_brokers,
                capital_per_broker=capital_per_broker,
                market_data_complete=True,
            )

        # Calculate avg_cost and total_cost per position
        symbols = list(positions_data.keys())
        total_cost = Decimal("0")
        portfolio_service = PortfolioService(self.db)
        for symbol, qty in positions_data.items():
            avg_cost = await portfolio_service.calculate_avg_cost(user_id, symbol)
            position_cost = (avg_cost * Decimal(qty)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            total_cost += position_cost

        # Step 3: Market data for total market value
        resolved_market_data: dict[str, TickerInfo] = {}
        if market_data is not None:
            resolved_market_data = market_data
        elif self.market_data_service is not None:
            for symbol in symbols:
                resolved_market_data[symbol] = (
                    await self.market_data_service.get_ticker_info(symbol)
                )

        # Calculate total market value
        total_market_value = Decimal("0")
        market_data_complete = True

        for symbol, qty in positions_data.items():
            ticker = resolved_market_data.get(symbol)
            current_price = ticker.current_price if ticker else None

            if current_price is not None:
                position_mv = (current_price * Decimal(qty)).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
                total_market_value += position_mv
            else:
                market_data_complete = False

        # Calculate Overall P/L and ROI
        overall_pl: Optional[Decimal] = None
        overall_roi_percent: Optional[Decimal] = None
        final_market_value: Optional[Decimal] = None

        if market_data_complete:
            final_market_value = total_market_value.quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            overall_pl = (total_market_value - total_cost).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if total_cost != Decimal("0"):
                overall_roi_percent = (
                    (overall_pl / total_cost) * Decimal("100")
                ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            else:
                overall_roi_percent = Decimal("0.00")

        return DashboardResponse(
            total_invested=total_invested.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            total_withdrawn=total_withdrawn.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            net_invested=net_invested.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            total_market_value=final_market_value,
            overall_pl=overall_pl,
            overall_roi_percent=overall_roi_percent,
            total_positions=total_positions,
            total_brokers=total_brokers,
            capital_per_broker=capital_per_broker,
            market_data_complete=market_data_complete,
        )

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    async def _get_transfer_aggregations(
        self, user_id: uuid.UUID
    ) -> dict:
        """Query transfer data to calculate totals and per-broker breakdown.

        Returns a dict with:
        - total_invested: sum of all "In" amounts
        - total_withdrawn: sum of all "Out" amounts
        - capital_per_broker: list of BrokerCapital objects
        - total_brokers: distinct broker count
        """
        # Query aggregated amounts per broker and type
        stmt = (
            select(
                Transfer.broker,
                Transfer.transfer_type,
                func.sum(Transfer.amount).label("total_amount"),
            )
            .where(Transfer.user_id == user_id)
            .group_by(Transfer.broker, Transfer.transfer_type)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Build per-broker totals
        broker_totals: dict[str, dict[str, Decimal]] = {}
        total_invested = Decimal("0")
        total_withdrawn = Decimal("0")

        for row in rows:
            broker = row.broker
            transfer_type = row.transfer_type
            amount = Decimal(str(row.total_amount))

            if broker not in broker_totals:
                broker_totals[broker] = {"in": Decimal("0"), "out": Decimal("0")}

            if transfer_type == "In":
                broker_totals[broker]["in"] += amount
                total_invested += amount
            elif transfer_type == "Out":
                broker_totals[broker]["out"] += amount
                total_withdrawn += amount

        # Build capital_per_broker response
        capital_per_broker: list[BrokerCapital] = []
        for broker, totals in broker_totals.items():
            net = totals["in"] - totals["out"]
            capital_per_broker.append(
                BrokerCapital(
                    broker=broker,
                    total_in=totals["in"].quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                    total_out=totals["out"].quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                    net_capital=net.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                )
            )

        total_brokers = len(broker_totals)

        return {
            "total_invested": total_invested,
            "total_withdrawn": total_withdrawn,
            "capital_per_broker": capital_per_broker,
            "total_brokers": total_brokers,
        }

    async def _get_positions_with_holdings(
        self, user_id: uuid.UUID
    ) -> dict[str, int]:
        """Get all symbols with positive holdings for a user.

        Holdings = Σ(buy qty) + Σ(snapshot qty) - Σ(sell qty)
        Excludes symbols with zero quantity.

        Returns dict mapping symbol -> held quantity.
        """
        stmt = (
            select(
                Transaction.stock_symbol,
                func.sum(
                    case(
                        (
                            Transaction.action.in_(["Buy", "Snapshot"]),
                            Transaction.quantity,
                        ),
                        else_=-Transaction.quantity,
                    )
                ).label("holdings"),
            )
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.stock_symbol)
            .having(
                func.sum(
                    case(
                        (
                            Transaction.action.in_(["Buy", "Snapshot"]),
                            Transaction.quantity,
                        ),
                        else_=-Transaction.quantity,
                    )
                )
                > 0
            )
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return {row.stock_symbol: int(row.holdings) for row in rows}

