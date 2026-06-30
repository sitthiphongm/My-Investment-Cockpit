"""Stock Tags and Categories API routes."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_user_id
from app.models.user import User
from app.redis import get_redis
from app.schemas.tags import (
    StocksByTagResponse,
    StockTagsUpdate,
    TagCreate,
    TagListResponse,
    TagPerformanceResponse,
    TagResponse,
)
from app.services.market_data_service import MarketDataService
from app.services.tag_service import TagService

router = APIRouter(tags=["tags"])


@router.post("/api/tags", response_model=TagResponse, status_code=201)
async def create_tag(
    data: TagCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom tag for organizing stocks.

    Tag names must be 1-50 characters and unique per user (case-insensitive).
    Returns 409 if the tag name already exists.
    """
    service = TagService(db)
    tag = await service.create_tag(user.id, data)
    return TagResponse(
        id=str(tag.id),
        name=tag.name,
        created_at=tag.created_at,
    )


@router.get("/api/tags", response_model=TagListResponse)
async def list_tags(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all tags for the authenticated user."""
    service = TagService(db)
    tags = await service.list_tags(user_id)
    return TagListResponse(
        tags=[
            TagResponse(id=str(tag.id), name=tag.name, created_at=tag.created_at)
            for tag in tags
        ]
    )


@router.delete("/api/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a tag and remove it from all associated stocks.

    Returns 404 if the tag does not exist or does not belong to the user.
    """
    service = TagService(db)
    await service.delete_tag(user.id, tag_id)


@router.put("/api/stocks/{symbol}/tags", response_model=list[str])
async def assign_tags_to_stock(
    symbol: str,
    data: StockTagsUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign tags to a stock symbol (replaces existing assignments).

    Provide a list of tag_ids to assign. Pass an empty list to remove all tags.
    Returns 400 if any tag_id is invalid or does not belong to the user.
    """
    service = TagService(db)
    tag_names = await service.assign_tags_to_stock(user.id, symbol, data)
    return tag_names


@router.get("/api/tags/performance", response_model=TagPerformanceResponse)
async def get_tag_performance(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get aggregated performance metrics per tag.

    For each tag, returns total cost, market value, unrealized P/L, and ROI%
    for all stocks that share that tag and have positive holdings.
    """
    service = TagService(db)

    # Fetch market data for all symbols that have tag assignments
    from app.models.stock_tag_assignment import StockTagAssignment
    from sqlalchemy import select

    stmt = select(StockTagAssignment.stock_symbol).where(
        StockTagAssignment.user_id == user_id
    ).distinct()
    result = await db.execute(stmt)
    symbols = [row[0] for row in result.all()]

    market_data: Optional[dict] = None
    if symbols:
        market_data_service = MarketDataService(redis_client)
        market_data = {}
        for symbol in symbols:
            try:
                ticker_info = await market_data_service.get_ticker_info(symbol)
                market_data[symbol] = ticker_info
            except Exception:
                pass

    return await service.get_tag_performance(user_id, market_data)


@router.get("/api/tags/{tag_id}/stocks", response_model=StocksByTagResponse)
async def get_stocks_by_tag(
    tag_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get all stock symbols associated with a specific tag.

    Returns 404 if the tag does not exist or does not belong to the user.
    """
    service = TagService(db)
    return await service.get_stocks_by_tag(user_id, tag_id)
