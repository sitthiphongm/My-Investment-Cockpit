"""User settings API routes — FX rate caching and manual entry."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.fx_rates import FXRateCreate, FXRateResponse
from app.services.fx_rate_service import FXRateService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/fx-rates", response_model=FXRateResponse | None)
async def get_fx_rate(
    currency_pair: str = Query(
        ...,
        min_length=7,
        max_length=7,
        description="Currency pair in format 'XXX/YYY' (e.g. 'THB/USD')",
    ),
    date: date = Query(..., description="Date to look up the FX rate for"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a cached or manual FX rate for a currency pair and date.

    Returns the cached rate if available for auto-population in the transfer form.
    Returns null (204 No Content) if no rate is found, with a stale indicator
    in the response when the rate exists but is outdated.
    """
    # Validate currency_pair format
    if len(currency_pair) != 7 or currency_pair[3] != "/":
        raise HTTPException(
            status_code=422,
            detail="Currency pair must be in format 'XXX/YYY' (e.g. 'THB/USD')",
        )

    base_currency = currency_pair[:3].upper()
    quote_currency = currency_pair[4:].upper()

    if not base_currency.isalpha() or not quote_currency.isalpha():
        raise HTTPException(
            status_code=422,
            detail="Currency codes must be alphabetic",
        )

    service = FXRateService(db)
    entry = await service.get_rate(user.id, base_currency, quote_currency, date)

    if entry is None:
        return None

    return FXRateResponse(
        id=str(entry.id),
        currency_pair=f"{entry.base_currency}/{entry.quote_currency}",
        date=entry.rate_date,
        rate=entry.rate,
        provider=entry.provider_name,
        source_timestamp=entry.source_timestamp,
        fetch_timestamp=entry.fetch_timestamp,
        is_manual=entry.is_manual,
        is_stale=(entry.staleness == "Stale"),
        created_at=entry.created_at,
    )


@router.post("/fx-rates", response_model=FXRateResponse, status_code=201)
async def create_fx_rate(
    data: FXRateCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually enter an FX rate for a currency pair and date.

    If a rate already exists for the same pair and date, it will be updated
    (upsert behavior). Manual entries are marked with is_manual=True.

    This supports manual FX rate entry when no free provider is configured
    or when provider data is unavailable.
    """
    service = FXRateService(db)
    entry = await service.create_manual_rate(user.id, data)

    return FXRateResponse(
        id=str(entry.id),
        currency_pair=f"{entry.base_currency}/{entry.quote_currency}",
        date=entry.rate_date,
        rate=entry.rate,
        provider=entry.provider_name,
        source_timestamp=entry.source_timestamp,
        fetch_timestamp=entry.fetch_timestamp,
        is_manual=entry.is_manual,
        is_stale=(entry.staleness == "Stale"),
        created_at=entry.created_at,
    )
