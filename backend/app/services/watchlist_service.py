"""Watchlist service - Business logic for watchlist operations."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist_item import WatchlistItem
from app.schemas.market_data import TickerInfo
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemUpdate


class WatchlistService:
    """Service for managing a user's watchlist.

    Provides CRUD operations for watchlist items and enrichment with market data.
    All operations are scoped to a specific user_id for data isolation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_item(
        self, user_id: uuid.UUID, data: WatchlistItemCreate
    ) -> WatchlistItem:
        """Add a stock to the user's watchlist.

        Args:
            user_id: The authenticated user's ID.
            data: Validated watchlist item creation data (symbol, optional price, optional notes).

        Returns:
            The newly created WatchlistItem record.

        Raises:
            HTTPException(409): If the symbol is already on the user's watchlist.
        """
        # Check if already on watchlist
        existing = await self._get_by_symbol(user_id, data.stock_symbol)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Stock '{data.stock_symbol}' is already on your watchlist",
            )

        item = WatchlistItem(
            id=uuid.uuid4(),
            user_id=user_id,
            stock_symbol=data.stock_symbol,
            interested_at_price=data.interested_at_price,
            notes=data.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def list_items(self, user_id: uuid.UUID) -> list[WatchlistItem]:
        """List all watchlist items for a user, sorted by created_at descending.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            List of WatchlistItem records.
        """
        stmt = (
            select(WatchlistItem)
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_item(
        self, user_id: uuid.UUID, item_id: uuid.UUID, data: WatchlistItemUpdate
    ) -> WatchlistItem:
        """Update a watchlist item's notes or target price.

        Args:
            user_id: The authenticated user's ID.
            item_id: The watchlist item ID to update.
            data: Update data (interested_at_price and/or notes).

        Returns:
            The updated WatchlistItem record.

        Raises:
            HTTPException(404): If the item does not exist or does not belong to the user.
        """
        item = await self._get_item_or_404(user_id, item_id)

        if data.interested_at_price is not None:
            item.interested_at_price = data.interested_at_price
        if data.notes is not None:
            item.notes = data.notes

        item.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def delete_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
        """Remove a stock from the user's watchlist.

        Args:
            user_id: The authenticated user's ID.
            item_id: The watchlist item ID to delete.

        Raises:
            HTTPException(404): If the item does not exist or does not belong to the user.
        """
        item = await self._get_item_or_404(user_id, item_id)
        await self.db.delete(item)
        await self.db.flush()

    @staticmethod
    def is_at_target(
        interested_at_price: Optional[Decimal], current_price: Optional[Decimal]
    ) -> bool:
        """Determine if a watchlist item is at its target price.

        An item is "At Target" when the current market price is less than or equal
        to the user's interested_at_price.

        Args:
            interested_at_price: The user's target price (optional).
            current_price: The current market price (optional).

        Returns:
            True if both prices are set and current_price <= interested_at_price.
        """
        if interested_at_price is None or current_price is None:
            return False
        return current_price <= interested_at_price

    async def _get_item_or_404(
        self, user_id: uuid.UUID, item_id: uuid.UUID
    ) -> WatchlistItem:
        """Fetch a watchlist item by ID, ensuring it belongs to the given user.

        Raises:
            HTTPException(404): If the item is not found.
        """
        stmt = select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Watchlist item not found",
            )
        return item

    async def _get_by_symbol(
        self, user_id: uuid.UUID, stock_symbol: str
    ) -> Optional[WatchlistItem]:
        """Fetch a watchlist item by symbol for a given user.

        Args:
            user_id: The authenticated user's ID.
            stock_symbol: The stock symbol to look up.

        Returns:
            The WatchlistItem if found, or None.
        """
        stmt = select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.stock_symbol == stock_symbol,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
