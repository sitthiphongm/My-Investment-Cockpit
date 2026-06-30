"""Watchlist API routes."""

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_user_id
from app.models.user import User
from app.redis import get_redis
from app.schemas.watchlist import (
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistResponse,
)
from app.services.market_data_service import MarketDataService
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _build_response(
    item,
    market_data: Optional[dict] = None,
) -> WatchlistItemResponse:
    """Build a WatchlistItemResponse from a WatchlistItem model and optional market data.

    Enriches the response with market data fields and computes the "At Target" flag.
    """
    current_price: Optional[Decimal] = None
    company_name: Optional[str] = None
    day_change_percent: Optional[Decimal] = None
    fifty_two_week_low: Optional[Decimal] = None
    fifty_two_week_high: Optional[Decimal] = None
    pe_trailing: Optional[Decimal] = None
    sector: Optional[str] = None

    if market_data and item.stock_symbol in market_data:
        ticker_info = market_data[item.stock_symbol]
        current_price = ticker_info.current_price
        company_name = ticker_info.long_name
        sector = ticker_info.sector
        fifty_two_week_low = ticker_info.fifty_two_week_low
        fifty_two_week_high = ticker_info.fifty_two_week_high
        pe_trailing = ticker_info.trailing_pe

        # Calculate day change percent from current_price and previous_close
        if ticker_info.current_price is not None and ticker_info.previous_close is not None:
            if ticker_info.previous_close > 0:
                day_change_percent = (
                    (ticker_info.current_price - ticker_info.previous_close)
                    / ticker_info.previous_close
                    * 100
                )

    at_target = WatchlistService.is_at_target(item.interested_at_price, current_price)

    return WatchlistItemResponse(
        id=str(item.id),
        stock_symbol=item.stock_symbol,
        interested_at_price=item.interested_at_price,
        notes=item.notes,
        at_target=at_target,
        created_at=item.created_at,
        updated_at=item.updated_at,
        company_name=company_name,
        current_price=current_price,
        day_change_percent=day_change_percent,
        fifty_two_week_low=fifty_two_week_low,
        fifty_two_week_high=fifty_two_week_high,
        pe_trailing=pe_trailing,
        sector=sector,
    )


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def add_to_watchlist(
    data: WatchlistItemCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a stock to the user's watchlist.

    Stores the stock symbol with an optional target price and notes.
    Returns 409 if the symbol is already on the watchlist.
    """
    service = WatchlistService(db)
    item = await service.add_item(user.id, data)
    return _build_response(item)


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """List all watchlist items with market data.

    Fetches current market data for all watched symbols and highlights
    items where the current price is at or below the user's target price
    ("At Target").
    """
    service = WatchlistService(db)
    items = await service.list_items(user_id)

    # Fetch market data for all watchlist symbols
    market_data: Optional[dict] = None
    if items:
        market_data_service = MarketDataService(redis_client)
        market_data = {}
        symbols = list(set(item.stock_symbol for item in items))
        for symbol in symbols:
            try:
                ticker_info = await market_data_service.get_ticker_info(symbol)
                market_data[symbol] = ticker_info
            except Exception:
                # If market data fetch fails for a symbol, skip it
                pass

    return WatchlistResponse(
        items=[_build_response(item, market_data) for item in items]
    )


@router.put("/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    item_id: uuid.UUID,
    data: WatchlistItemUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a watchlist item's notes or target price.

    Returns 404 if the item does not exist or does not belong to the user.
    """
    service = WatchlistService(db)
    item = await service.update_item(user.id, item_id, data)
    return _build_response(item)


@router.delete("/{item_id}", status_code=204)
async def remove_from_watchlist(
    item_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a stock from the user's watchlist.

    Returns 404 if the item does not exist or does not belong to the user.
    """
    service = WatchlistService(db)
    await service.delete_item(user.id, item_id)
