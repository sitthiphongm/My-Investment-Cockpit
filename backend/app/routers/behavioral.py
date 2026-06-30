"""Behavioral Analytics API router."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.behavioral_service import BehavioralAnalyticsService

router = APIRouter(prefix="/api/behavioral", tags=["behavioral"])


class BehavioralStatsResponse(BaseModel):
    total_closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    avg_winner: Decimal
    avg_loser: Decimal
    payoff_ratio: Decimal
    avg_holding_days: Decimal
    best_trade_pl: Decimal
    worst_trade_pl: Decimal
    total_realized_pl: Decimal


class BehaviorPatternResponse(BaseModel):
    pattern_id: str
    label: str
    description: str
    severity: str
    count: int = 0


@router.get("/stats", response_model=BehavioralStatsResponse)
async def get_behavioral_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get behavioral analytics statistics from realized trades."""
    service = BehavioralAnalyticsService(db)
    stats = await service.get_stats(user_id)
    return BehavioralStatsResponse(
        total_closed_trades=stats.total_closed_trades,
        winning_trades=stats.winning_trades,
        losing_trades=stats.losing_trades,
        win_rate=stats.win_rate,
        avg_winner=stats.avg_winner,
        avg_loser=stats.avg_loser,
        payoff_ratio=stats.payoff_ratio,
        avg_holding_days=stats.avg_holding_days,
        best_trade_pl=stats.best_trade_pl,
        worst_trade_pl=stats.worst_trade_pl,
        total_realized_pl=stats.total_realized_pl,
    )


@router.get("/patterns", response_model=list[BehaviorPatternResponse])
async def get_behavioral_patterns(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Identify behavioral patterns from trading history."""
    service = BehavioralAnalyticsService(db)
    patterns = await service.get_patterns(user_id)
    return [
        BehaviorPatternResponse(
            pattern_id=p.pattern_id,
            label=p.label,
            description=p.description,
            severity=p.severity,
            count=p.count,
        )
        for p in patterns
    ]
