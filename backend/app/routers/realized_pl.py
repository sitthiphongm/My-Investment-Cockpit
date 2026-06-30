"""Realized P/L API routes."""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.enums import TermType
from app.schemas.realized_pl import (
    RealizedPLFilters,
    RealizedPLListResponse,
    RealizedPLResponse,
    RealizedPLSummaryResponse,
)
from app.services.realized_pl_service import RealizedPLService

router = APIRouter(prefix="/api/realized-pl", tags=["realized-pl"])


@router.get("", response_model=RealizedPLListResponse)
async def list_realized_pl(
    stock_symbol: Optional[str] = Query(
        None, description="Filter by stock symbol (case-insensitive)"
    ),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    term_type: Optional[TermType] = Query(
        None, description="Filter by term type (Short-term or Long-term)"
    ),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List realized P/L records sorted by date descending."""
    filters = RealizedPLFilters(
        stock_symbol=stock_symbol,
        date_from=date_from,
        date_to=date_to,
        term_type=term_type,
    )
    service = RealizedPLService(db)
    records = await service.list_realized_pl(user.id, filters)
    return RealizedPLListResponse(
        records=[
            RealizedPLResponse(
                id=str(r.id),
                date=r.date,
                stock_symbol=r.stock_symbol,
                sell_quantity=r.sell_quantity,
                sell_price=r.sell_price,
                avg_cost_at_sale=r.avg_cost_at_sale,
                realized_pl=r.realized_pl,
                hold_duration_days=r.hold_duration_days,
                term_type=TermType(r.term_type),
                transaction_id=str(r.transaction_id) if r.transaction_id else None,
                created_at=r.created_at,
            )
            for r in records
        ]
    )


@router.get("/summary", response_model=RealizedPLSummaryResponse)
async def get_realized_pl_summary(
    group_by: Optional[str] = Query(
        None,
        description="Group by: 'monthly' or 'yearly'. Omit for all-time only.",
        pattern="^(monthly|yearly)$",
    ),
    stock_symbol: Optional[str] = Query(
        None, description="Filter by stock symbol"
    ),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    term_type: Optional[TermType] = Query(
        None, description="Filter by term type"
    ),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get cumulative realized P/L totals (monthly, yearly, all-time)."""
    filters = RealizedPLFilters(
        stock_symbol=stock_symbol,
        date_from=date_from,
        date_to=date_to,
        term_type=term_type,
        group_by=group_by,
    )
    service = RealizedPLService(db)
    return await service.get_summary(user.id, filters)
