"""Advanced Stock Screener API routes with multi-provider support."""

from fastapi import APIRouter, Depends
import redis.asyncio as redis

from app.dependencies import get_current_user_id
from app.redis import redis_client
from app.services.providers.screener_orchestrator import ScreenerOrchestrator

router = APIRouter(prefix="/api/screener", tags=["advanced-screener"])


def get_redis():
    return redis_client


@router.post("/advanced")
async def advanced_screen(
    body: dict,
    _user_id=Depends(get_current_user_id),
):
    """Execute advanced stock screener with multi-provider orchestration.

    Body:
    {
        "filters": {"pe_min": 10, "pe_max": 25, "sector": "Technology", ...},
        "signals": ["wallstreet_hi", "not_200d_new_lo"],  // optional
        "preset": "garp"  // optional - if set, uses preset filters
    }
    """
    orchestrator = ScreenerOrchestrator(redis_client)

    filters = body.get("filters", {})
    signals = body.get("signals")
    preset_id = body.get("preset")

    # If preset specified, merge preset filters with user filters
    if preset_id:
        from app.services.providers.screener_orchestrator import SYSTEM_PRESETS
        preset = SYSTEM_PRESETS.get(preset_id)
        if preset:
            preset_filters = preset.get("filters", {})
            # Preset as base, user filters override
            merged = {**preset_filters, **{k: v for k, v in filters.items() if v is not None}}
            filters = merged
            # Also apply preset signals
            if not signals and preset.get("signals"):
                signals = preset["signals"]

    result = await orchestrator.execute_screen(filters, signals)
    return result


@router.get("/presets/system")
async def get_system_presets(
    _user_id=Depends(get_current_user_id),
):
    """Get all built-in strategy presets with their filter configurations."""
    orchestrator = ScreenerOrchestrator(redis_client)
    return await orchestrator.get_system_presets()


@router.get("/filters/available")
async def get_available_filters(
    _user_id=Depends(get_current_user_id),
):
    """Get all available filter metrics with metadata (min, max, step, type)."""
    orchestrator = ScreenerOrchestrator(redis_client)
    return await orchestrator.get_available_filters()


@router.get("/provider-status")
async def get_provider_status(
    _user_id=Depends(get_current_user_id),
):
    """Get current provider health and quota status."""
    from app.config import settings

    return {
        "providers": {
            "fmp": {
                "configured": bool(settings.fmp_api_key),
                "role": "Primary Screener",
                "daily_limit": 250,
            },
            "eodhd": {
                "configured": bool(settings.eodhd_api_key),
                "role": "Market Signals",
                "daily_limit": 20,
            },
            "alpha_vantage": {
                "configured": bool(settings.alpha_vantage_api_key),
                "role": "Financial Ratios",
                "daily_limit": 25,
            },
            "twelve_data": {
                "configured": bool(settings.twelve_data_api_key),
                "role": "Real-time Prices",
                "daily_limit": 800,
            },
            "yfinance": {
                "configured": True,
                "role": "Fallback & Historicals",
                "daily_limit": None,
            },
        }
    }
