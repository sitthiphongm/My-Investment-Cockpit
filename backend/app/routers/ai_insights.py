"""AI Insights API router — weekly memos, trade reviews, settings."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.ai_insight_service import AIInsightService

router = APIRouter(prefix="/api/ai", tags=["ai-insights"])


class WeeklyMemoResponse(BaseModel):
    content: str
    generation_mode: str
    generated_at: str
    stale_warnings: list[str]


class TradeReviewResponse(BaseModel):
    content: str
    generation_mode: str
    realized_pl: str | None
    holding_days: int | None


class AISettingsResponse(BaseModel):
    ai_provider: str
    is_enabled: bool


@router.get("/weekly-memo", response_model=WeeklyMemoResponse)
async def get_weekly_memo(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest weekly portfolio memo."""
    service = AIInsightService(db)
    result = await service.generate_weekly_memo(user_id)
    return WeeklyMemoResponse(**result)


@router.post("/weekly-memo/generate", response_model=WeeklyMemoResponse)
async def generate_weekly_memo(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new weekly portfolio memo."""
    service = AIInsightService(db)
    result = await service.generate_weekly_memo(user_id)
    return WeeklyMemoResponse(**result)


@router.get("/trade-review/{transaction_id}", response_model=TradeReviewResponse)
async def get_trade_review(
    transaction_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get AI trade review for a sold position."""
    service = AIInsightService(db)
    result = await service.generate_trade_review(user_id, transaction_id)
    return TradeReviewResponse(**result)


@router.post("/trade-review/generate", response_model=TradeReviewResponse)
async def generate_trade_review(
    transaction_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new trade review for a sell transaction."""
    service = AIInsightService(db)
    result = await service.generate_trade_review(user_id, transaction_id)
    return TradeReviewResponse(**result)


@router.get("/settings", response_model=AISettingsResponse)
async def get_ai_settings(
    db: AsyncSession = Depends(get_db),
):
    """Get current AI provider settings."""
    service = AIInsightService(db)
    return AISettingsResponse(
        ai_provider=service.generation_mode,
        is_enabled=service.is_enabled,
    )
