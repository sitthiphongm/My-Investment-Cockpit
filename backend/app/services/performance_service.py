"""Performance service - Business logic for portfolio performance tracking."""

import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance_snapshot import PerformanceSnapshot
from app.schemas.performance import (
    CumulativeReturnResponse,
    PerformanceListResponse,
    PerformanceSnapshotResponse,
    SnapshotCreate,
    SnapshotFilters,
    SnapshotUpdate,
)


class PerformanceService:
    """Service for managing portfolio performance snapshots and return calculations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_snapshot(
        self, user_id: uuid.UUID, data: SnapshotCreate
    ) -> PerformanceSnapshot:
        """Record a new portfolio value snapshot.

        Stores date, total_portfolio_value, and total_cost.
        Validation (date not future, value ranges) is handled by the Pydantic schema.
        """
        snapshot = PerformanceSnapshot(
            id=uuid.uuid4(),
            user_id=user_id,
            date=data.date,
            total_portfolio_value=data.total_portfolio_value,
            total_cost=data.total_cost,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(snapshot)
        await self.db.flush()
        await self.db.refresh(snapshot)
        return snapshot

    async def list_snapshots(
        self, user_id: uuid.UUID, filters: SnapshotFilters
    ) -> PerformanceListResponse:
        """List performance snapshots sorted by date ascending with period return calculations.

        Supports:
        - Date range filter (inclusive start/end)
        - Monthly aggregation (last snapshot per month)
        - Yearly aggregation (last snapshot per year)

        Returns snapshots with calculated P/L and period returns, plus cumulative return.
        """
        snapshots = await self._fetch_snapshots(user_id, filters)

        if filters.aggregation == "monthly":
            snapshots = self._aggregate_monthly(snapshots)
        elif filters.aggregation == "yearly":
            snapshots = self._aggregate_yearly(snapshots)

        snapshot_responses = self._build_snapshot_responses(snapshots)
        cumulative_return = self._calculate_cumulative_return(snapshots)

        return PerformanceListResponse(
            snapshots=snapshot_responses,
            cumulative_return=cumulative_return,
        )

    async def edit_snapshot(
        self, user_id: uuid.UUID, snapshot_id: uuid.UUID, data: SnapshotUpdate
    ) -> PerformanceSnapshot:
        """Edit an existing performance snapshot.

        Only non-None fields from the update data are applied.
        Adjacent period returns are recalculated automatically when listing.
        Raises HTTPException(404) if the snapshot does not exist or does not belong to the user.
        """
        snapshot = await self._get_snapshot_or_404(user_id, snapshot_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(snapshot, field, value)

        snapshot.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(snapshot)
        return snapshot

    async def delete_snapshot(
        self, user_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> None:
        """Delete a performance snapshot.

        Adjacent period returns are recalculated automatically when listing.
        Raises HTTPException(404) if the snapshot does not exist or does not belong to the user.
        """
        snapshot = await self._get_snapshot_or_404(user_id, snapshot_id)
        await self.db.delete(snapshot)
        await self.db.flush()

    def calculate_period_return(
        self, current_value: Decimal, previous_value: Decimal
    ) -> Optional[Decimal]:
        """Calculate period return between two consecutive snapshots.

        Formula: (current - previous) / previous × 100, to 2 decimal places.
        Returns None if previous_value is zero (division by zero).
        """
        if previous_value == Decimal("0"):
            return None
        result = ((current_value - previous_value) / previous_value) * Decimal("100")
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_cumulative_return(
        self, earliest_value: Decimal, latest_value: Decimal
    ) -> Optional[Decimal]:
        """Calculate cumulative return from earliest to latest snapshot.

        Formula: (latest - earliest) / earliest × 100, to 2 decimal places.
        Returns None if earliest_value is zero.
        """
        if earliest_value == Decimal("0"):
            return None
        result = ((latest_value - earliest_value) / earliest_value) * Decimal("100")
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    async def _fetch_snapshots(
        self, user_id: uuid.UUID, filters: SnapshotFilters
    ) -> list[PerformanceSnapshot]:
        """Fetch snapshots from database with optional date range filter, sorted by date ascending."""
        stmt = select(PerformanceSnapshot).where(
            PerformanceSnapshot.user_id == user_id
        )

        if filters.date_from is not None:
            stmt = stmt.where(PerformanceSnapshot.date >= filters.date_from)

        if filters.date_to is not None:
            stmt = stmt.where(PerformanceSnapshot.date <= filters.date_to)

        stmt = stmt.order_by(
            PerformanceSnapshot.date.asc(), PerformanceSnapshot.created_at.asc()
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def _aggregate_monthly(
        self, snapshots: list[PerformanceSnapshot]
    ) -> list[PerformanceSnapshot]:
        """Aggregate snapshots by month — keep only the last snapshot per month."""
        if not snapshots:
            return []

        monthly: dict[str, PerformanceSnapshot] = {}
        for snapshot in snapshots:
            key = snapshot.date.strftime("%Y-%m")
            monthly[key] = snapshot  # last one per month wins (sorted ascending)

        return list(monthly.values())

    def _aggregate_yearly(
        self, snapshots: list[PerformanceSnapshot]
    ) -> list[PerformanceSnapshot]:
        """Aggregate snapshots by year — keep only the last snapshot per year."""
        if not snapshots:
            return []

        yearly: dict[str, PerformanceSnapshot] = {}
        for snapshot in snapshots:
            key = str(snapshot.date.year)
            yearly[key] = snapshot  # last one per year wins (sorted ascending)

        return list(yearly.values())

    def _build_snapshot_responses(
        self, snapshots: list[PerformanceSnapshot]
    ) -> list[PerformanceSnapshotResponse]:
        """Build response objects with calculated P/L and period returns.

        First snapshot has period_return = None (N/A).
        Subsequent snapshots get period return calculated from the previous snapshot's value.
        """
        responses = []
        for i, snapshot in enumerate(snapshots):
            pl = snapshot.total_portfolio_value - snapshot.total_cost

            if i == 0:
                period_return = None
            else:
                previous_value = snapshots[i - 1].total_portfolio_value
                period_return = self.calculate_period_return(
                    snapshot.total_portfolio_value, previous_value
                )

            responses.append(
                PerformanceSnapshotResponse(
                    id=str(snapshot.id),
                    date=snapshot.date,
                    total_portfolio_value=snapshot.total_portfolio_value,
                    total_cost=snapshot.total_cost,
                    pl=pl,
                    period_return=period_return,
                    created_at=snapshot.created_at,
                    updated_at=snapshot.updated_at,
                )
            )

        return responses

    def _calculate_cumulative_return(
        self, snapshots: list[PerformanceSnapshot]
    ) -> CumulativeReturnResponse:
        """Calculate cumulative return from the full snapshot list.

        Returns cumulative_return_percent = None if fewer than 2 snapshots or earliest value is 0.
        """
        if len(snapshots) < 2:
            if len(snapshots) == 1:
                return CumulativeReturnResponse(
                    cumulative_return_percent=None,
                    earliest_value=snapshots[0].total_portfolio_value,
                    latest_value=snapshots[0].total_portfolio_value,
                    earliest_date=snapshots[0].date,
                    latest_date=snapshots[0].date,
                )
            return CumulativeReturnResponse()

        earliest = snapshots[0]
        latest = snapshots[-1]
        cumulative = self.calculate_cumulative_return(
            earliest.total_portfolio_value, latest.total_portfolio_value
        )

        return CumulativeReturnResponse(
            cumulative_return_percent=cumulative,
            earliest_value=earliest.total_portfolio_value,
            latest_value=latest.total_portfolio_value,
            earliest_date=earliest.date,
            latest_date=latest.date,
        )

    async def _get_snapshot_or_404(
        self, user_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> PerformanceSnapshot:
        """Fetch a snapshot by ID, ensuring it belongs to the given user.

        Raises HTTPException(404) if not found.
        """
        stmt = select(PerformanceSnapshot).where(
            PerformanceSnapshot.id == snapshot_id,
            PerformanceSnapshot.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail="Performance snapshot not found",
            )
        return snapshot
