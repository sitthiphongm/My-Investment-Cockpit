"""Portfolio service - Business logic for portfolio summary calculations."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_sentiment import StockSentiment
from app.models.transaction import Transaction
from app.schemas.enums import ActionType, SentimentType
from app.schemas.market_data import TickerInfo
from app.schemas.portfolio import (
    PortfolioPositionResponse,
    PortfolioSummaryResponse,
)


TWO_PLACES = Decimal("0.01")


class PortfolioService:
    """Service for computing portfolio summary, allocations, and managing sentiment.

    Key formulas:
    - avg_cost = Σ(qty_i × price_i) / Σ(qty_i) for Buy + Snapshot entries
    - allocation = (position_total_cost / Σ all_positions_total_cost) × 100
    - unrealized_pl = (current_price × quantity) - (avg_cost × quantity)
    - roi_percent = (unrealized_pl / total_cost) × 100
    - Holdings = Σ(buy qty) + Σ(snapshot qty) - Σ(sell qty)
    """

    def __init__(self, db: AsyncSession, market_data_service=None):
        self.db = db
        self.market_data_service = market_data_service

    async def get_summary(
        self, user_id: uuid.UUID, market_data: Optional[dict[str, TickerInfo]] = None
    ) -> PortfolioSummaryResponse:
        """Get the full portfolio summary with market data.

        Steps:
        1. Query all transactions grouped by symbol
        2. Calculate holdings (buy + snapshot - sell) per symbol
        3. Exclude zero-quantity positions
        4. Calculate avg_cost per symbol (from buys + snapshots)
        5. Fetch market data for each held symbol (via market_data_service or market_data param)
        6. Calculate market_value, unrealized_pl, roi_percent
        7. Calculate allocation percentages
        8. Fetch sentiment per symbol
        9. Build totals row

        Args:
            user_id: The authenticated user's ID.
            market_data: Optional pre-fetched dict mapping symbol -> TickerInfo.
                         If not provided and market_data_service is set, will fetch.

        Returns:
            PortfolioSummaryResponse with all positions and aggregate totals.
        """
        # Get positions with holdings > 0
        positions_data = await self._get_positions_with_holdings(user_id)

        if not positions_data:
            return PortfolioSummaryResponse(
                positions=[],
                total_cost=Decimal("0.00"),
                total_market_value=Decimal("0.00"),
                total_unrealized_pl=Decimal("0.00"),
                overall_roi_percent=Decimal("0.00"),
                market_data_complete=True,
            )

        # Calculate avg_cost for each position
        symbols = list(positions_data.keys())
        avg_costs: dict[str, Decimal] = {}
        for symbol in symbols:
            avg_costs[symbol] = await self.calculate_avg_cost(user_id, symbol)

        # Calculate total_cost per position and grand total
        position_total_costs: dict[str, Decimal] = {}
        for symbol, holdings_qty in positions_data.items():
            total_cost = (avg_costs[symbol] * Decimal(holdings_qty)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            position_total_costs[symbol] = total_cost

        grand_total_cost = sum(position_total_costs.values(), Decimal("0"))

        # Calculate allocations
        allocations = self._calculate_allocations(position_total_costs, grand_total_cost)

        # Fetch market data for all symbols
        resolved_market_data: dict[str, TickerInfo] = {}
        if market_data is not None:
            resolved_market_data = market_data
        elif self.market_data_service is not None:
            for symbol in symbols:
                resolved_market_data[symbol] = (
                    await self.market_data_service.get_ticker_info(symbol)
                )

        # Fetch sentiments
        sentiments = await self._get_sentiments(user_id, symbols)

        # Build position responses
        positions: list[PortfolioPositionResponse] = []
        total_market_value = Decimal("0")
        market_data_complete = True

        for symbol in symbols:
            qty = positions_data[symbol]
            avg_cost = avg_costs[symbol]
            total_cost = position_total_costs[symbol]
            allocation = allocations.get(symbol, Decimal("0"))
            ticker = resolved_market_data.get(symbol)
            sentiment = sentiments.get(symbol)

            # Market-data-dependent calculations
            current_price = ticker.current_price if ticker else None
            market_value: Optional[Decimal] = None
            unrealized_pl: Optional[Decimal] = None
            roi_percent: Optional[Decimal] = None

            if current_price is not None:
                market_value = (current_price * Decimal(qty)).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
                unrealized_pl = (market_value - total_cost).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
                if total_cost != Decimal("0"):
                    roi_percent = (
                        (unrealized_pl / total_cost) * Decimal("100")
                    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                else:
                    roi_percent = Decimal("0.00")
                total_market_value += market_value
            else:
                market_data_complete = False

            position = PortfolioPositionResponse(
                stock_symbol=symbol,
                quantity=qty,
                avg_cost=avg_cost,
                total_cost=total_cost,
                market_value=market_value,
                unrealized_pl=unrealized_pl,
                roi_percent=roi_percent,
                allocation_percent=allocation,
                sentiment=sentiment,
                # Market data fields
                company_name=ticker.long_name if ticker else None,
                sector=ticker.sector if ticker else None,
                industry=ticker.industry if ticker else None,
                current_price=current_price,
                previous_close=ticker.previous_close if ticker else None,
                day_high=ticker.day_high if ticker else None,
                day_low=ticker.day_low if ticker else None,
                fifty_two_week_low=ticker.fifty_two_week_low if ticker else None,
                fifty_two_week_high=ticker.fifty_two_week_high if ticker else None,
                market_cap=ticker.market_cap if ticker else None,
                pe_trailing=ticker.trailing_pe if ticker else None,
                pe_forward=ticker.forward_pe if ticker else None,
                average_volume=ticker.average_volume if ticker else None,
                beta=ticker.beta if ticker else None,
                dividend_yield=ticker.dividend_yield if ticker else None,
                price_to_book=ticker.price_to_book if ticker else None,
                last_refresh=ticker.last_refresh if ticker else None,
            )
            positions.append(position)

        # Calculate totals
        total_unrealized_pl: Optional[Decimal] = None
        overall_roi_percent: Optional[Decimal] = None

        if market_data_complete:
            total_market_value_rounded = total_market_value.quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            total_unrealized_pl = (total_market_value - grand_total_cost).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if grand_total_cost != Decimal("0"):
                overall_roi_percent = (
                    (total_unrealized_pl / grand_total_cost) * Decimal("100")
                ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            else:
                overall_roi_percent = Decimal("0.00")

        return PortfolioSummaryResponse(
            positions=positions,
            total_cost=grand_total_cost.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            total_market_value=total_market_value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            if market_data_complete
            else None,
            total_unrealized_pl=total_unrealized_pl,
            overall_roi_percent=overall_roi_percent,
            market_data_complete=market_data_complete,
        )

    async def calculate_avg_cost(self, user_id: uuid.UUID, symbol: str) -> Decimal:
        """Calculate weighted average cost for a symbol.

        avg_cost = Σ(quantity_i × price_per_share_i) / Σ(quantity_i)
        where i ∈ {Buy + Snapshot entries for this symbol}

        Returns Decimal("0") if no buy/snapshot entries exist.
        """
        symbol = symbol.upper()

        stmt = select(
            func.sum(Transaction.quantity * Transaction.price_per_share).label("total_cost"),
            func.sum(Transaction.quantity).label("total_qty"),
        ).where(
            Transaction.user_id == user_id,
            Transaction.stock_symbol == symbol,
            Transaction.action.in_(["Buy", "Snapshot"]),
        )

        result = await self.db.execute(stmt)
        row = result.one()

        total_cost = row.total_cost
        total_qty = row.total_qty

        if total_qty is None or total_qty == 0:
            return Decimal("0.00")

        avg_cost = (Decimal(str(total_cost)) / Decimal(str(total_qty))).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        return avg_cost

    async def calculate_allocation(self, user_id: uuid.UUID) -> dict[str, Decimal]:
        """Calculate allocation percentages for all held positions.

        allocation = (position_total_cost / Σ all_positions_total_cost) × 100

        Returns a dict mapping symbol -> allocation percentage.
        """
        positions_data = await self._get_positions_with_holdings(user_id)

        if not positions_data:
            return {}

        # Calculate total_cost per position
        position_total_costs: dict[str, Decimal] = {}
        for symbol, qty in positions_data.items():
            avg_cost = await self.calculate_avg_cost(user_id, symbol)
            total_cost = (avg_cost * Decimal(qty)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            position_total_costs[symbol] = total_cost

        grand_total = sum(position_total_costs.values(), Decimal("0"))
        return self._calculate_allocations(position_total_costs, grand_total)

    async def set_sentiment(
        self, user_id: uuid.UUID, symbol: str, sentiment: str
    ) -> None:
        """Set or update sentiment (Bear/Bull) for a stock.

        Uses upsert logic: update if exists, insert if new.

        Args:
            user_id: The authenticated user's ID.
            symbol: Stock ticker symbol (will be uppercased).
            sentiment: Must be 'Bear' or 'Bull'.

        Raises:
            HTTPException 400 if sentiment is not Bear/Bull.
        """
        symbol = symbol.upper()

        # Validate sentiment value
        if sentiment not in ("Bear", "Bull"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sentiment value: {sentiment}. Must be 'Bear' or 'Bull'.",
            )

        # Check if sentiment record exists
        stmt = select(StockSentiment).where(
            StockSentiment.user_id == user_id,
            StockSentiment.stock_symbol == symbol,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.sentiment = sentiment
        else:
            new_sentiment = StockSentiment(
                id=uuid.uuid4(),
                user_id=user_id,
                stock_symbol=symbol,
                sentiment=sentiment,
            )
            self.db.add(new_sentiment)

        await self.db.flush()

    async def get_sentiment(
        self, user_id: uuid.UUID, symbol: str
    ) -> Optional[SentimentType]:
        """Get the sentiment for a stock, or None if not set."""
        symbol = symbol.upper()
        stmt = select(StockSentiment.sentiment).where(
            StockSentiment.user_id == user_id,
            StockSentiment.stock_symbol == symbol,
        )
        result = await self.db.execute(stmt)
        sentiment_value = result.scalar_one_or_none()
        if sentiment_value is None:
            return None
        return SentimentType(sentiment_value)

    async def get_held_symbols(self, user_id: uuid.UUID) -> list[str]:
        """Get all symbols currently held by the user (quantity > 0).

        Returns:
            List of stock symbols with positive holdings.
        """
        positions = await self._get_positions_with_holdings(user_id)
        return list(positions.keys())

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    async def _get_positions_with_holdings(
        self, user_id: uuid.UUID
    ) -> dict[str, Decimal]:
        """Get all symbols with positive holdings for a user.

        Holdings = Σ(buy qty) + Σ(snapshot qty) - Σ(sell qty)
        Excludes symbols with zero quantity.
        Supports fractional shares.

        Returns dict mapping symbol -> held quantity (Decimal).
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
        return {row.stock_symbol: Decimal(str(row.holdings)) for row in rows}

    async def _get_sentiments(
        self, user_id: uuid.UUID, symbols: list[str]
    ) -> dict[str, Optional[SentimentType]]:
        """Get sentiments for multiple symbols in a single query."""
        if not symbols:
            return {}

        stmt = select(
            StockSentiment.stock_symbol,
            StockSentiment.sentiment,
        ).where(
            StockSentiment.user_id == user_id,
            StockSentiment.stock_symbol.in_(symbols),
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        sentiments: dict[str, Optional[SentimentType]] = {s: None for s in symbols}
        for row in rows:
            sentiments[row.stock_symbol] = SentimentType(row.sentiment)

        return sentiments

    @staticmethod
    def _calculate_allocations(
        position_total_costs: dict[str, Decimal], grand_total: Decimal
    ) -> dict[str, Decimal]:
        """Calculate allocation percentages from total costs.

        allocation = (position_cost / grand_total) × 100
        """
        if grand_total == Decimal("0"):
            # Avoid division by zero - distribute equally if all costs are 0
            count = len(position_total_costs)
            if count == 0:
                return {}
            equal_alloc = (Decimal("100") / Decimal(count)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            return {symbol: equal_alloc for symbol in position_total_costs}

        allocations: dict[str, Decimal] = {}
        for symbol, cost in position_total_costs.items():
            allocation = ((cost / grand_total) * Decimal("100")).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            allocations[symbol] = allocation

        return allocations
