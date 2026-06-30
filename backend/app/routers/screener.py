"""Stock Screener API routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_user_id
from app.models.user import User
from app.schemas.screener import (
    ScreenerFilterCreate,
    ScreenerPresetCreate,
    ScreenerPresetListResponse,
    ScreenerPresetResponse,
    ScreenerSearchResponse,
)
from app.services.screener_service import ScreenerService

router = APIRouter(prefix="/api/screener", tags=["screener"])


def _build_preset_response(preset) -> ScreenerPresetResponse:
    """Build a ScreenerPresetResponse from a ScreenerPreset model."""
    return ScreenerPresetResponse(
        id=str(preset.id),
        name=preset.name,
        filter_criteria=preset.filter_criteria,
        created_at=preset.created_at,
    )


@router.post("/search", response_model=ScreenerSearchResponse)
async def search_stocks(
    data: ScreenerFilterCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a stock screener query.

    Filters stocks by PE ratio range, dividend yield range, market cap,
    sector, industry, beta range, and price-to-book range.

    Results are limited to 50 stocks per query, sorted by market cap descending.
    """
    service = ScreenerService(db)
    return await service.search(data)


@router.get("/presets", response_model=ScreenerPresetListResponse)
async def list_presets(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all saved screener presets for the current user.

    Returns presets sorted by creation date descending.
    """
    service = ScreenerService(db)
    presets = await service.list_presets(user_id)
    return ScreenerPresetListResponse(
        presets=[_build_preset_response(p) for p in presets]
    )


@router.post("/presets", response_model=ScreenerPresetResponse, status_code=201)
async def create_preset(
    data: ScreenerPresetCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a new screener filter preset.

    Preset name must be 1-100 characters. Filter criteria is stored as JSON.
    """
    service = ScreenerService(db)
    preset = await service.create_preset(user.id, data)
    return _build_preset_response(preset)


@router.delete("/presets/{preset_id}", status_code=204)
async def delete_preset(
    preset_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved screener preset.

    Returns 404 if the preset does not exist or does not belong to the user.
    """
    service = ScreenerService(db)
    await service.delete_preset(user.id, preset_id)
