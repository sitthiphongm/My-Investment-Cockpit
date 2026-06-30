"""Dividend tracker API routes."""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.dividends import (
    DividendCreate,
    DividendFilters,
    DividendProjectionResponse,
    DividendResponse,
    DividendSummaryResponse,
)
from app.services.dividend_service import DividendService

router = APIRouter(prefix="/api/dividends", tags=["dividends"])


@router.post("", response_model=DividendResponse, status_code=201)
async def create_dividend(
    data: DividendCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a new dividend payment."""
    service = DividendService(db)
    record = await service.create_dividend(user.id, data)
    return DividendResponse(
        id=str(record.id),
        date=record.date,
        stock_symbol=record.stock_symbol,
        amount_per_share=record.amount_per_share,
        shares_held=record.shares_held,
        total_amount=record.total_amount,
        created_at=record.created_at,
    )


@router.get("", response_model=list[DividendResponse])
async def list_dividends(
    stock_symbol: Optional[str] = Query(
        None, description="Filter by stock symbol (case-insensitive)"
    ),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List dividend records sorted by date descending."""
    filters = DividendFilters(
        stock_symbol=stock_symbol, date_from=date_from, date_to=date_to
    )
    service = DividendService(db)
    records = await service.list_dividends(user.id, filters)
    return [
        DividendResponse(
            id=str(r.id),
            date=r.date,
            stock_symbol=r.stock_symbol,
            amount_per_share=r.amount_per_share,
            shares_held=r.shares_held,
            total_amount=r.total_amount,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/summary", response_model=DividendSummaryResponse)
async def get_dividend_summary(
    group_by: Optional[str] = Query(
        None,
        description="Group by: 'stock', 'monthly', or 'yearly'",
        pattern="^(stock|monthly|yearly)$",
    ),
    stock_symbol: Optional[str] = Query(
        None, description="Filter by stock symbol"
    ),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dividend summary by stock or by time period (monthly/yearly)."""
    filters = DividendFilters(
        stock_symbol=stock_symbol,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
    )
    service = DividendService(db)
    return await service.get_summary(user.id, filters)


@router.get("/projection", response_model=DividendProjectionResponse)
async def get_dividend_projection(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get projected annual dividend income based on recent rate × current holdings.

    Calculates:
    - Projected annual income per stock
    - Dividend yield on cost per stock
    - Total projected annual income
    """
    service = DividendService(db)
    return await service.get_projection(user.id)
