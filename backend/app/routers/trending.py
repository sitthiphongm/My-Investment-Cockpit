"""Trending stocks API routes.

Uses FMP as primary provider (gainers/losers/most active with intelligent reasons).
Falls back to yfinance if FMP fails or is not configured.
Results are cached in Redis with a 15-minute TTL.
"""

import json
import logging
import time

import redis.asyncio as redis
from fastapi import APIRouter, Depends

from app.config import settings
from app.redis import get_redis
from app.schemas.market_data import TrendingData, TrendingStock
from app.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trending", tags=["trending"])

TRENDING_CACHE_KEY = "trending_data_v3"
TRENDING_CACHE_TTL = 900  # 15 minutes


@router.get("")
async def get_trending_stocks(
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get trending stocks: top gainers, top losers, and most active.

    Uses FMP as primary provider for intelligent catalyst-driven reasons.
    Falls back to yfinance if FMP fails.

    Each stock entry includes:
    - symbol, company_name, current_price, day_change_percent
    - volume, market_cap, sector
    - reason: Intelligent catalyst-driven explanation
    """
    # Check cache first
    try:
        cached = await redis_client.get(TRENDING_CACHE_KEY)
        if cached:
            data = json.loads(cached)
            age = time.time() - data.get("_cached_at", 0)
            if age <= TRENDING_CACHE_TTL:
                data.pop("_cached_at", None)
                return data
    except Exception:
        pass

    # FMP legacy gainers/losers/actives endpoints require paid plan
    # Use yfinance as the primary source (it has reliable day_gainers/day_losers/most_actives)
    market_data_service = MarketDataService(redis_client)
    trending = await market_data_service.get_trending()

    result = {
        "gainers": [_trending_stock_to_dict(s) for s in trending.gainers],
        "losers": [_trending_stock_to_dict(s) for s in trending.losers],
        "most_active": [_trending_stock_to_dict(s) for s in trending.most_active],
        "provider": "yfinance",
    }

    # Cache
    try:
        cache_data = {**result, "_cached_at": time.time()}
        await redis_client.set(TRENDING_CACHE_KEY, json.dumps(cache_data, default=str), ex=TRENDING_CACHE_TTL)
    except Exception:
        pass

    return result


def _trending_stock_to_dict(stock: TrendingStock) -> dict:
    """Convert TrendingStock schema to dict."""
    return {
        "symbol": stock.symbol,
        "company_name": stock.company_name,
        "current_price": float(stock.current_price) if stock.current_price else None,
        "day_change_percent": float(stock.day_change_percent) if stock.day_change_percent else None,
        "volume": stock.volume,
        "market_cap": stock.market_cap,
        "sector": stock.sector,
        "reason": stock.reason or "",
        "data_source": "yfinance",
    }
