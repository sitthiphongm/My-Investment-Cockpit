"""Tag service - Business logic for stock tags and categories."""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_tag_assignment import StockTagAssignment
from app.models.tag import Tag
from app.models.transaction import Transaction
from app.schemas.tags import (
    StocksByTagResponse,
    StockTagsUpdate,
    TagCreate,
    TagPerformanceItem,
    TagPerformanceResponse,
)

TWO_PLACES = Decimal("0.01")


class TagService:
    """Service for managing custom stock tags and categories.

    Provides CRUD operations for tags, assignment of tags to stock symbols,
    and aggregated performance metrics per tag. All operations are scoped
    to a specific user_id for data isolation.

    Tag names are unique per user (case-insensitive).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tag(self, user_id: uuid.UUID, data: TagCreate) -> Tag:
        """Create a new custom tag for the user.

        Args:
            user_id: The authenticated user's ID.
            data: Tag creation data with name (1-50 chars).

        Returns:
            The newly created Tag record.

        Raises:
            HTTPException(409): If a tag with the same name (case-insensitive) already exists.
        """
        # Check for case-insensitive duplicate
        existing = await self._get_tag_by_name(user_id, data.name)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Tag '{data.name}' already exists (case-insensitive match)",
            )

        tag = Tag(
            id=uuid.uuid4(),
            user_id=user_id,
            name=data.name.strip(),
            created_at=datetime.utcnow(),
        )
        self.db.add(tag)
        await self.db.flush()
        await self.db.refresh(tag)
        return tag

    async def list_tags(self, user_id: uuid.UUID) -> list[Tag]:
        """List all tags for the user, sorted by name ascending.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            List of Tag records.
        """
        stmt = (
            select(Tag)
            .where(Tag.user_id == user_id)
            .order_by(Tag.name.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_tag(self, user_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        """Delete a tag and remove all its stock assignments.

        The cascade on the foreign key should handle deleting StockTagAssignment
        records automatically (ondelete="CASCADE" on tag_id FK). We also explicitly
        delete assignments to be safe with SQLite test DBs that may not support cascades.

        Args:
            user_id: The authenticated user's ID.
            tag_id: The tag ID to delete.

        Raises:
            HTTPException(404): If the tag does not exist or does not belong to the user.
        """
        tag = await self._get_tag_or_404(user_id, tag_id)

        # Explicitly remove stock assignments (for SQLite compat in tests)
        await self.db.execute(
            delete(StockTagAssignment).where(
                StockTagAssignment.tag_id == tag_id,
                StockTagAssignment.user_id == user_id,
            )
        )

        await self.db.delete(tag)
        await self.db.flush()

    async def assign_tags_to_stock(
        self, user_id: uuid.UUID, stock_symbol: str, data: StockTagsUpdate
    ) -> list[str]:
        """Assign tags to a stock symbol, replacing any existing assignments.

        This performs a full replacement: removes all existing tag assignments
        for the given stock symbol and creates new ones based on the provided tag_ids.

        Args:
            user_id: The authenticated user's ID.
            stock_symbol: The stock ticker symbol (will be uppercased).
            data: Contains the list of tag_ids to assign.

        Returns:
            List of assigned tag names.

        Raises:
            HTTPException(400): If any tag_id does not exist or does not belong to the user.
        """
        stock_symbol = stock_symbol.upper()

        # Validate all tag_ids belong to the user
        valid_tags: list[Tag] = []
        for tag_id_str in data.tag_ids:
            try:
                tag_uuid = uuid.UUID(tag_id_str)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tag ID format: {tag_id_str}",
                )
            tag = await self._get_tag_by_id(user_id, tag_uuid)
            if tag is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tag with ID '{tag_id_str}' not found",
                )
            valid_tags.append(tag)

        # Remove existing assignments for this stock
        await self.db.execute(
            delete(StockTagAssignment).where(
                StockTagAssignment.user_id == user_id,
                StockTagAssignment.stock_symbol == stock_symbol,
            )
        )

        # Create new assignments
        for tag in valid_tags:
            assignment = StockTagAssignment(
                id=uuid.uuid4(),
                user_id=user_id,
                stock_symbol=stock_symbol,
                tag_id=tag.id,
            )
            self.db.add(assignment)

        await self.db.flush()
        return [tag.name for tag in valid_tags]

    async def get_stocks_by_tag(
        self, user_id: uuid.UUID, tag_id: uuid.UUID
    ) -> StocksByTagResponse:
        """Get all stock symbols associated with a specific tag.

        Args:
            user_id: The authenticated user's ID.
            tag_id: The tag ID to look up.

        Returns:
            StocksByTagResponse with tag info and list of stock symbols.

        Raises:
            HTTPException(404): If the tag does not exist or does not belong to the user.
        """
        tag = await self._get_tag_or_404(user_id, tag_id)

        stmt = (
            select(StockTagAssignment.stock_symbol)
            .where(
                StockTagAssignment.user_id == user_id,
                StockTagAssignment.tag_id == tag_id,
            )
            .order_by(StockTagAssignment.stock_symbol.asc())
        )
        result = await self.db.execute(stmt)
        symbols = [row[0] for row in result.all()]

        return StocksByTagResponse(
            tag_id=str(tag.id),
            tag_name=tag.name,
            stocks=symbols,
        )

    async def get_tag_performance(
        self,
        user_id: uuid.UUID,
        market_data: Optional[dict] = None,
    ) -> TagPerformanceResponse:
        """Get aggregated performance metrics per tag.

        For each tag, calculates:
        - total_cost: sum of (avg_cost × quantity) for all stocks with this tag
        - total_market_value: sum of (current_price × quantity) for all stocks with this tag
        - unrealized_pl: total_market_value - total_cost
        - roi_percent: (unrealized_pl / total_cost) × 100
        - stock_count: number of stocks with this tag

        Args:
            user_id: The authenticated user's ID.
            market_data: Optional dict mapping symbol -> TickerInfo with current prices.

        Returns:
            TagPerformanceResponse with performance metrics for each tag.
        """
        # Get all tags for the user
        tags = await self.list_tags(user_id)
        if not tags:
            return TagPerformanceResponse(tags=[])

        # Get all stock-tag assignments for the user
        stmt = select(StockTagAssignment).where(
            StockTagAssignment.user_id == user_id
        )
        result = await self.db.execute(stmt)
        assignments = list(result.scalars().all())

        # Build tag_id -> list of symbols
        tag_stocks: dict[uuid.UUID, list[str]] = {}
        for assignment in assignments:
            if assignment.tag_id not in tag_stocks:
                tag_stocks[assignment.tag_id] = []
            tag_stocks[assignment.tag_id].append(assignment.stock_symbol)

        # Get holdings for all assigned symbols
        all_symbols = list(set(s for symbols in tag_stocks.values() for s in symbols))
        holdings = await self._get_holdings_for_symbols(user_id, all_symbols)
        avg_costs = await self._get_avg_costs_for_symbols(user_id, all_symbols)

        # Build performance items
        items: list[TagPerformanceItem] = []
        for tag in tags:
            symbols = tag_stocks.get(tag.id, [])
            # Only include symbols with positive holdings
            active_symbols = [s for s in symbols if holdings.get(s, 0) > 0]

            total_cost = Decimal("0")
            total_market_value: Optional[Decimal] = Decimal("0")
            has_market_data = True

            for symbol in active_symbols:
                qty = holdings.get(symbol, 0)
                avg_cost = avg_costs.get(symbol, Decimal("0"))
                cost = (avg_cost * Decimal(qty)).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
                total_cost += cost

                # Get current price from market data
                current_price: Optional[Decimal] = None
                if market_data and symbol in market_data:
                    ticker_info = market_data[symbol]
                    current_price = ticker_info.current_price

                if current_price is not None:
                    mv = (current_price * Decimal(qty)).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    )
                    total_market_value += mv
                else:
                    has_market_data = False

            if not has_market_data:
                total_market_value = None

            unrealized_pl: Optional[Decimal] = None
            roi_percent: Optional[Decimal] = None

            if total_market_value is not None:
                total_market_value = total_market_value.quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
                unrealized_pl = (total_market_value - total_cost).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
                if total_cost > Decimal("0"):
                    roi_percent = (
                        (unrealized_pl / total_cost) * Decimal("100")
                    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                else:
                    roi_percent = Decimal("0.00")

            items.append(
                TagPerformanceItem(
                    tag_id=str(tag.id),
                    tag_name=tag.name,
                    total_cost=total_cost.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                    total_market_value=total_market_value,
                    unrealized_pl=unrealized_pl,
                    roi_percent=roi_percent,
                    stock_count=len(active_symbols),
                )
            )

        return TagPerformanceResponse(tags=items)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _get_tag_by_name(
        self, user_id: uuid.UUID, name: str
    ) -> Optional[Tag]:
        """Find a tag by name (case-insensitive) for the given user."""
        stmt = select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == name.strip().lower(),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_tag_by_id(
        self, user_id: uuid.UUID, tag_id: uuid.UUID
    ) -> Optional[Tag]:
        """Find a tag by ID for the given user."""
        stmt = select(Tag).where(
            Tag.id == tag_id,
            Tag.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_tag_or_404(
        self, user_id: uuid.UUID, tag_id: uuid.UUID
    ) -> Tag:
        """Fetch a tag by ID, ensuring it belongs to the given user.

        Raises:
            HTTPException(404): If the tag is not found.
        """
        tag = await self._get_tag_by_id(user_id, tag_id)
        if tag is None:
            raise HTTPException(
                status_code=404,
                detail="Tag not found",
            )
        return tag

    async def _get_holdings_for_symbols(
        self, user_id: uuid.UUID, symbols: list[str]
    ) -> dict[str, int]:
        """Get holdings (buy + snapshot - sell) for a list of symbols."""
        if not symbols:
            return {}

        from sqlalchemy import case as sql_case

        stmt = (
            select(
                Transaction.stock_symbol,
                func.sum(
                    sql_case(
                        (
                            Transaction.action.in_(["Buy", "Snapshot"]),
                            Transaction.quantity,
                        ),
                        else_=-Transaction.quantity,
                    )
                ).label("holdings"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.stock_symbol.in_(symbols),
            )
            .group_by(Transaction.stock_symbol)
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return {row.stock_symbol: max(0, int(row.holdings)) for row in rows}

    async def _get_avg_costs_for_symbols(
        self, user_id: uuid.UUID, symbols: list[str]
    ) -> dict[str, Decimal]:
        """Get average cost for a list of symbols."""
        if not symbols:
            return {}

        avg_costs: dict[str, Decimal] = {}
        for symbol in symbols:
            stmt = select(
                func.sum(Transaction.quantity * Transaction.price_per_share).label(
                    "total_cost"
                ),
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
                avg_costs[symbol] = Decimal("0.00")
            else:
                avg_costs[symbol] = (
                    Decimal(str(total_cost)) / Decimal(str(total_qty))
                ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        return avg_costs
