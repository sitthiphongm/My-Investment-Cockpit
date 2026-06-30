"""Dashboard API routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis

from app.database import get_db
from app.dependencies import get_current_user_id
from app.redis import get_redis
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService
from app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get aggregated dashboard overview data.

    Returns:
    - Total Invested / Total Withdrawn / Net Invested
    - Total Market Value / Overall P/L / Overall ROI%
    - Capital per broker breakdown
    - Total held positions count and total brokers count
    - Market data completeness flag

    Handles edge cases:
    - No data: all zeros
    - Incomplete market data: market value and P/L shown as None
    """
    market_data_service = MarketDataService(redis_client)
    service = DashboardService(db, market_data_service=market_data_service)
    return await service.get_overview(user_id)
