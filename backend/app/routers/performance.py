"""Performance history API routes."""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.performance import (
    PerformanceListResponse,
    PerformanceSnapshotResponse,
    SnapshotCreate,
    SnapshotFilters,
    SnapshotUpdate,
)
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/snapshots", response_model=PerformanceListResponse)
async def list_snapshots(
    date_from: Optional[date] = Query(None, description="Filter: start date (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter: end date (inclusive)"),
    aggregation: Optional[str] = Query(
        None, description="Aggregation view: 'monthly' or 'yearly'"
    ),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List performance snapshots sorted by date ascending with period return calculations.

    Supports:
    - Date range filter (date_from / date_to inclusive)
    - Monthly aggregation (last snapshot per month)
    - Yearly aggregation (last snapshot per year)

    Returns snapshots with P/L and period returns, plus cumulative return summary.
    """
    filters = SnapshotFilters(
        date_from=date_from,
        date_to=date_to,
        aggregation=aggregation,
    )
    service = PerformanceService(db)
    return await service.list_snapshots(user_id, filters)


@router.post("/snapshots", response_model=PerformanceSnapshotResponse, status_code=201)
async def record_snapshot(
    data: SnapshotCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Record a new portfolio value snapshot.

    Stores date, total_portfolio_value, and total_cost for historical tracking.
    The P/L and period return are calculated automatically when listing.
    """
    service = PerformanceService(db)
    snapshot = await service.record_snapshot(user_id, data)
    return PerformanceSnapshotResponse(
        id=str(snapshot.id),
        date=snapshot.date,
        total_portfolio_value=snapshot.total_portfolio_value,
        total_cost=snapshot.total_cost,
        pl=snapshot.total_portfolio_value - snapshot.total_cost,
        period_return=None,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


@router.put("/snapshots/{snapshot_id}", response_model=PerformanceSnapshotResponse)
async def edit_snapshot(
    snapshot_id: uuid.UUID,
    data: SnapshotUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Edit an existing performance snapshot.

    Only non-None fields from the update are applied.
    Adjacent period returns are recalculated automatically when listing.
    """
    service = PerformanceService(db)
    snapshot = await service.edit_snapshot(user_id, snapshot_id, data)
    return PerformanceSnapshotResponse(
        id=str(snapshot.id),
        date=snapshot.date,
        total_portfolio_value=snapshot.total_portfolio_value,
        total_cost=snapshot.total_cost,
        pl=snapshot.total_portfolio_value - snapshot.total_cost,
        period_return=None,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


@router.delete("/snapshots/{snapshot_id}", status_code=204)
async def delete_snapshot(
    snapshot_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a performance snapshot.

    Adjacent period returns are recalculated automatically when listing.
    """
    service = PerformanceService(db)
    await service.delete_snapshot(user_id, snapshot_id)
