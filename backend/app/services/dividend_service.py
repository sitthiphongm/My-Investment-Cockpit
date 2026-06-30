"""Dividend service - Business logic for dividend tracking operations."""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dividend_record import DividendRecord
from app.models.transaction import Transaction
from app.schemas.dividends import (
    DividendCreate,
    DividendFilters,
    DividendProjectionEntry,
    DividendProjectionResponse,
    DividendSummaryEntry,
    DividendSummaryResponse,
)

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


class DividendService:
    """Service for managing dividend records, summaries, and projections."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_dividend(
        self, user_id: uuid.UUID, data: DividendCreate
    ) -> DividendRecord:
        """Record a new dividend payment.

        Validation is handled by the Pydantic schema (DividendCreate).
        Persists the validated data and returns the created record.
        """
        record = DividendRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            date=data.date,
            stock_symbol=data.stock_symbol,
            amount_per_share=data.amount_per_share,
            shares_held=data.shares_held,
            total_amount=data.total_amount,
            created_at=datetime.utcnow(),
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_dividends(
        self, user_id: uuid.UUID, filters: DividendFilters
    ) -> list[DividendRecord]:
        """List dividend records sorted by date descending.

        Supports optional filters: stock_symbol, date_from, date_to.
        """
        stmt = select(DividendRecord).where(DividendRecord.user_id == user_id)

        if filters.stock_symbol is not None:
            stmt = stmt.where(
                DividendRecord.stock_symbol.ilike(filters.stock_symbol)
            )

        if filters.date_from is not None:
            stmt = stmt.where(DividendRecord.date >= filters.date_from)

        if filters.date_to is not None:
            stmt = stmt.where(DividendRecord.date <= filters.date_to)

        stmt = stmt.order_by(
            DividendRecord.date.desc(), DividendRecord.created_at.desc()
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(
        self, user_id: uuid.UUID, filters: DividendFilters
    ) -> DividendSummaryResponse:
        """Get dividend summary grouped by stock or by time period.

        group_by options:
        - "stock": aggregate by stock_symbol
        - "monthly": aggregate by year-month
        - "yearly": aggregate by year
        - None: returns a single total entry
        """
        group_by = filters.group_by

        if group_by == "stock":
            return await self._summary_by_stock(user_id, filters)
        elif group_by == "monthly":
            return await self._summary_by_period(user_id, filters, "monthly")
        elif group_by == "yearly":
            return await self._summary_by_period(user_id, filters, "yearly")
        else:
            return await self._summary_by_stock(user_id, filters)

    async def _summary_by_stock(
        self, user_id: uuid.UUID, filters: DividendFilters
    ) -> DividendSummaryResponse:
        """Aggregate dividends by stock symbol."""
        stmt = (
            select(
                DividendRecord.stock_symbol,
                func.sum(DividendRecord.total_amount).label("total_dividends"),
                func.count(DividendRecord.id).label("record_count"),
            )
            .where(DividendRecord.user_id == user_id)
            .group_by(DividendRecord.stock_symbol)
            .order_by(DividendRecord.stock_symbol)
        )

        stmt = self._apply_date_filters(stmt, filters)

        result = await self.db.execute(stmt)
        rows = result.all()

        entries = [
            DividendSummaryEntry(
                stock_symbol=row.stock_symbol,
                period=None,
                total_dividends=Decimal(str(row.total_dividends)).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                ),
                record_count=row.record_count,
            )
            for row in rows
        ]

        total_all = sum(
            (e.total_dividends for e in entries), Decimal("0.00")
        )

        return DividendSummaryResponse(
            entries=entries,
            total_all_dividends=total_all.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        )

    async def _summary_by_period(
        self, user_id: uuid.UUID, filters: DividendFilters, period_type: str
    ) -> DividendSummaryResponse:
        """Aggregate dividends by time period (monthly or yearly)."""
        year_col = extract("year", DividendRecord.date)

        if period_type == "monthly":
            month_col = extract("month", DividendRecord.date)
            # Build period label as "YYYY-MM"
            stmt = (
                select(
                    year_col.label("year"),
                    month_col.label("month"),
                    func.sum(DividendRecord.total_amount).label("total_dividends"),
                    func.count(DividendRecord.id).label("record_count"),
                )
                .where(DividendRecord.user_id == user_id)
                .group_by(year_col, month_col)
                .order_by(year_col.desc(), month_col.desc())
            )
        else:
            stmt = (
                select(
                    year_col.label("year"),
                    func.sum(DividendRecord.total_amount).label("total_dividends"),
                    func.count(DividendRecord.id).label("record_count"),
                )
                .where(DividendRecord.user_id == user_id)
                .group_by(year_col)
                .order_by(year_col.desc())
            )

        stmt = self._apply_date_filters(stmt, filters)

        result = await self.db.execute(stmt)
        rows = result.all()

        entries = []
        for row in rows:
            if period_type == "monthly":
                period_label = f"{int(row.year)}-{int(row.month):02d}"
            else:
                period_label = str(int(row.year))

            entries.append(
                DividendSummaryEntry(
                    stock_symbol=None,
                    period=period_label,
                    total_dividends=Decimal(str(row.total_dividends)).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    ),
                    record_count=row.record_count,
                )
            )

        total_all = sum(
            (e.total_dividends for e in entries), Decimal("0.00")
        )

        return DividendSummaryResponse(
            entries=entries,
            total_all_dividends=total_all.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        )

    async def get_projection(
        self, user_id: uuid.UUID
    ) -> DividendProjectionResponse:
        """Project annual dividend income based on most recent dividend rate × current holdings.

        For each stock with dividend history:
        1. Find the most recent dividend_per_share
        2. Get current held quantity from transactions
        3. Estimate frequency (dividends per year from historical data)
        4. projected_annual = last_dividend_per_share × current_shares × frequency
        5. yield_on_cost = (projected_annual / total_cost) × 100
        """
        # Get the most recent dividend per stock
        latest_dividends = await self._get_latest_dividends_per_stock(user_id)

        if not latest_dividends:
            return DividendProjectionResponse(
                projections=[],
                total_projected_annual=Decimal("0.00"),
            )

        # Get current holdings
        holdings = await self._get_current_holdings(user_id)

        # Get dividend frequency per stock (how many times per year)
        frequencies = await self._get_dividend_frequencies(user_id)

        # Get avg_cost per stock for yield on cost
        avg_costs = await self._get_avg_costs(user_id)

        projections = []
        total_projected = Decimal("0.00")

        for symbol, last_div_per_share in latest_dividends.items():
            current_shares = holdings.get(symbol, 0)
            if current_shares <= 0:
                continue

            frequency = frequencies.get(symbol, 1)  # Default to 1 if only 1 record
            projected_annual = (
                last_div_per_share * Decimal(str(current_shares)) * Decimal(str(frequency))
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

            # Calculate yield on cost
            avg_cost = avg_costs.get(symbol, Decimal("0"))
            total_cost = (avg_cost * Decimal(str(current_shares))).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )

            yield_on_cost: Optional[Decimal] = None
            if total_cost > Decimal("0"):
                yield_on_cost = (
                    (projected_annual / total_cost) * Decimal("100")
                ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

            projections.append(
                DividendProjectionEntry(
                    stock_symbol=symbol,
                    current_shares=current_shares,
                    last_dividend_per_share=last_div_per_share,
                    projected_annual=projected_annual,
                    yield_on_cost=yield_on_cost,
                )
            )

            total_projected += projected_annual

        return DividendProjectionResponse(
            projections=projections,
            total_projected_annual=total_projected.quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            ),
        )

    async def _get_latest_dividends_per_stock(
        self, user_id: uuid.UUID
    ) -> dict[str, Decimal]:
        """Get the most recent dividend_per_share for each stock."""
        # Subquery: max date per stock
        max_date_subq = (
            select(
                DividendRecord.stock_symbol,
                func.max(DividendRecord.date).label("max_date"),
            )
            .where(DividendRecord.user_id == user_id)
            .group_by(DividendRecord.stock_symbol)
            .subquery()
        )

        # Join to get the amount_per_share for the most recent record
        stmt = (
            select(
                DividendRecord.stock_symbol,
                DividendRecord.amount_per_share,
            )
            .join(
                max_date_subq,
                (DividendRecord.stock_symbol == max_date_subq.c.stock_symbol)
                & (DividendRecord.date == max_date_subq.c.max_date),
            )
            .where(DividendRecord.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # If multiple records on the same date for a symbol, use the latest one
        latest: dict[str, Decimal] = {}
        for row in rows:
            latest[row.stock_symbol] = Decimal(str(row.amount_per_share))

        return latest

    async def _get_current_holdings(self, user_id: uuid.UUID) -> dict[str, int]:
        """Get current held quantity per stock from transactions."""
        stmt = (
            select(
                Transaction.stock_symbol,
                func.sum(
                    case(
                        (
                            Transaction.action.in_(["Buy", "Snapshot"]),
                            Transaction.quantity,
                        ),
                        else_=-Transaction.quantity,
                    )
                ).label("holdings"),
            )
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.stock_symbol)
            .having(
                func.sum(
                    case(
                        (
                            Transaction.action.in_(["Buy", "Snapshot"]),
                            Transaction.quantity,
                        ),
                        else_=-Transaction.quantity,
                    )
                )
                > 0
            )
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return {row.stock_symbol: int(row.holdings) for row in rows}

    async def _get_dividend_frequencies(
        self, user_id: uuid.UUID
    ) -> dict[str, int]:
        """Estimate dividend payment frequency per stock (times per year).

        Looks at distinct years of dividend records. If records span multiple years,
        frequency = total_records / years_span. Otherwise defaults to count of records
        in a single year (capped at reasonable values like 1-4).
        """
        stmt = (
            select(
                DividendRecord.stock_symbol,
                func.count(DividendRecord.id).label("total_records"),
                func.min(extract("year", DividendRecord.date)).label("min_year"),
                func.max(extract("year", DividendRecord.date)).label("max_year"),
            )
            .where(DividendRecord.user_id == user_id)
            .group_by(DividendRecord.stock_symbol)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        frequencies: dict[str, int] = {}
        for row in rows:
            total_records = row.total_records
            min_year = int(row.min_year)
            max_year = int(row.max_year)
            years_span = max_year - min_year + 1

            if years_span > 1:
                # Estimate frequency as records per year
                freq = round(total_records / years_span)
            else:
                # Single year: use record count but cap at 4 (quarterly max)
                freq = min(total_records, 4)

            frequencies[row.stock_symbol] = max(freq, 1)  # At least 1

        return frequencies

    async def _get_avg_costs(self, user_id: uuid.UUID) -> dict[str, Decimal]:
        """Get weighted average cost per stock for yield on cost calculation."""
        stmt = (
            select(
                Transaction.stock_symbol,
                func.sum(
                    Transaction.quantity * Transaction.price_per_share
                ).label("total_cost"),
                func.sum(Transaction.quantity).label("total_qty"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.action.in_(["Buy", "Snapshot"]),
            )
            .group_by(Transaction.stock_symbol)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        avg_costs: dict[str, Decimal] = {}
        for row in rows:
            if row.total_qty and row.total_qty > 0:
                avg_cost = (
                    Decimal(str(row.total_cost)) / Decimal(str(row.total_qty))
                ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                avg_costs[row.stock_symbol] = avg_cost

        return avg_costs

    def _apply_date_filters(self, stmt, filters: DividendFilters):
        """Apply date range filters to a query statement."""
        if filters.date_from is not None:
            stmt = stmt.where(DividendRecord.date >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(DividendRecord.date <= filters.date_to)
        return stmt
