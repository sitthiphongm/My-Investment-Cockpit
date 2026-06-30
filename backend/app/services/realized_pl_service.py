"""Realized P/L service - Business logic for realized profit/loss tracking.

Auto-calculates realized P/L on each sell transaction:
- realized_pl = (sell_price - avg_cost_at_sale) × sell_qty
- Classifies as Short-term (<365 days) or Long-term (≥365 days)
- Stores date, symbol, sell_qty, sell_price, avg_cost_at_sale, realized_pl,
  hold_duration_days, term_type
"""

import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.realized_pl import RealizedPL
from app.models.transaction import Transaction
from app.schemas.realized_pl import (
    RealizedPLFilters,
    RealizedPLSummaryEntry,
    RealizedPLSummaryResponse,
)

TWO_PLACES = Decimal("0.01")


class RealizedPLService:
    """Service for managing realized P/L records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_and_store(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        sell_date: date,
        stock_symbol: str,
        sell_quantity: int,
        sell_price: Decimal,
    ) -> RealizedPL:
        """Auto-calculate realized P/L for a sell transaction.

        Steps:
        1. Calculate avg_cost at time of sale from buy/snapshot transactions
        2. Calculate realized_pl = (sell_price - avg_cost) × sell_qty
        3. Calculate hold_duration_days (weighted average buy date to sell date)
        4. Classify as Short-term (<365) or Long-term (≥365)
        5. Store the record
        """
        # Calculate avg cost at time of sale
        avg_cost = await self._calculate_avg_cost(user_id, stock_symbol)

        # Calculate realized P/L
        realized_pl = (sell_price - avg_cost) * Decimal(str(sell_quantity))
        realized_pl = realized_pl.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Calculate hold duration (weighted average buy date)
        hold_duration_days = await self._calculate_hold_duration(
            user_id, stock_symbol, sell_date
        )

        # Classify term type
        term_type = "Short-term" if hold_duration_days < 365 else "Long-term"

        record = RealizedPL(
            id=uuid.uuid4(),
            user_id=user_id,
            date=sell_date,
            stock_symbol=stock_symbol.upper(),
            sell_quantity=sell_quantity,
            sell_price=sell_price,
            avg_cost_at_sale=avg_cost,
            realized_pl=realized_pl,
            hold_duration_days=hold_duration_days,
            term_type=term_type,
            transaction_id=transaction_id,
            created_at=datetime.utcnow(),
        )

        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_realized_pl(
        self, user_id: uuid.UUID, filters: Optional[RealizedPLFilters] = None
    ) -> list[RealizedPL]:
        """List realized P/L records sorted by date descending.

        Supports filters: stock_symbol, date_from, date_to, term_type.
        """
        stmt = select(RealizedPL).where(RealizedPL.user_id == user_id)

        if filters:
            if filters.stock_symbol is not None:
                stmt = stmt.where(
                    func.upper(RealizedPL.stock_symbol)
                    == filters.stock_symbol.upper()
                )
            if filters.date_from is not None:
                stmt = stmt.where(RealizedPL.date >= filters.date_from)
            if filters.date_to is not None:
                stmt = stmt.where(RealizedPL.date <= filters.date_to)
            if filters.term_type is not None:
                stmt = stmt.where(RealizedPL.term_type == filters.term_type.value)

        stmt = stmt.order_by(RealizedPL.date.desc(), RealizedPL.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(
        self, user_id: uuid.UUID, filters: Optional[RealizedPLFilters] = None
    ) -> RealizedPLSummaryResponse:
        """Get cumulative realized P/L totals (monthly, yearly, all-time).

        group_by options from filters:
        - "monthly": aggregate by year-month
        - "yearly": aggregate by year
        - None: returns all-time totals only
        """
        group_by = filters.group_by if filters else None

        if group_by == "monthly":
            entries = await self._summary_by_period(user_id, filters, "monthly")
        elif group_by == "yearly":
            entries = await self._summary_by_period(user_id, filters, "yearly")
        else:
            entries = []

        # Calculate all-time totals
        all_time = await self._get_all_time_totals(user_id, filters)

        return RealizedPLSummaryResponse(
            entries=entries,
            all_time_total=all_time["total"],
            all_time_short_term=all_time["short_term"],
            all_time_long_term=all_time["long_term"],
        )

    async def _calculate_avg_cost(
        self, user_id: uuid.UUID, stock_symbol: str
    ) -> Decimal:
        """Calculate weighted average cost for a stock from buy/snapshot transactions.

        avg_cost = Σ(quantity × price_per_share) / Σ(quantity)
        Only considers Buy and Snapshot entries.
        """
        stmt = select(
            func.sum(Transaction.quantity * Transaction.price_per_share).label(
                "total_cost"
            ),
            func.sum(Transaction.quantity).label("total_qty"),
        ).where(
            Transaction.user_id == user_id,
            func.upper(Transaction.stock_symbol) == stock_symbol.upper(),
            Transaction.action.in_(["Buy", "Snapshot"]),
        )

        result = await self.db.execute(stmt)
        row = result.one()

        total_cost = row.total_cost
        total_qty = row.total_qty

        if not total_qty or total_qty == 0:
            return Decimal("0.00")

        avg_cost = (Decimal(str(total_cost)) / Decimal(str(total_qty))).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        return avg_cost

    async def _calculate_hold_duration(
        self, user_id: uuid.UUID, stock_symbol: str, sell_date: date
    ) -> int:
        """Calculate hold duration in days.

        Uses the weighted average buy date based on quantity-weighted buy dates.
        hold_duration = sell_date - weighted_avg_buy_date
        """
        # Get all buy/snapshot transactions for this symbol
        stmt = select(
            Transaction.date,
            Transaction.quantity,
        ).where(
            Transaction.user_id == user_id,
            func.upper(Transaction.stock_symbol) == stock_symbol.upper(),
            Transaction.action.in_(["Buy", "Snapshot"]),
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            return 0

        # Calculate weighted average buy date
        # Convert dates to days from epoch for weighting
        total_weighted_days = 0
        total_qty = 0

        for row in rows:
            buy_date = row.date
            qty = row.quantity
            # Days from sell_date
            days_held = (sell_date - buy_date).days
            total_weighted_days += days_held * qty
            total_qty += qty

        if total_qty == 0:
            return 0

        # Weighted average holding duration
        avg_duration = total_weighted_days // total_qty
        return max(avg_duration, 0)

    async def _summary_by_period(
        self,
        user_id: uuid.UUID,
        filters: Optional[RealizedPLFilters],
        period_type: str,
    ) -> list[RealizedPLSummaryEntry]:
        """Aggregate realized P/L by time period (monthly or yearly)."""
        year_col = extract("year", RealizedPL.date)

        if period_type == "monthly":
            month_col = extract("month", RealizedPL.date)
            stmt = (
                select(
                    year_col.label("year"),
                    month_col.label("month"),
                    func.sum(RealizedPL.realized_pl).label("total_pl"),
                    func.sum(
                        case(
                            (RealizedPL.term_type == "Short-term", RealizedPL.realized_pl),
                            else_=Decimal("0"),
                        )
                    ).label("total_short"),
                    func.sum(
                        case(
                            (RealizedPL.term_type == "Long-term", RealizedPL.realized_pl),
                            else_=Decimal("0"),
                        )
                    ).label("total_long"),
                    func.count(RealizedPL.id).label("record_count"),
                )
                .where(RealizedPL.user_id == user_id)
                .group_by(year_col, month_col)
                .order_by(year_col.desc(), month_col.desc())
            )
        else:
            stmt = (
                select(
                    year_col.label("year"),
                    func.sum(RealizedPL.realized_pl).label("total_pl"),
                    func.sum(
                        case(
                            (RealizedPL.term_type == "Short-term", RealizedPL.realized_pl),
                            else_=Decimal("0"),
                        )
                    ).label("total_short"),
                    func.sum(
                        case(
                            (RealizedPL.term_type == "Long-term", RealizedPL.realized_pl),
                            else_=Decimal("0"),
                        )
                    ).label("total_long"),
                    func.count(RealizedPL.id).label("record_count"),
                )
                .where(RealizedPL.user_id == user_id)
                .group_by(year_col)
                .order_by(year_col.desc())
            )

        stmt = self._apply_filters(stmt, filters)

        result = await self.db.execute(stmt)
        rows = result.all()

        entries = []
        for row in rows:
            if period_type == "monthly":
                period_label = f"{int(row.year)}-{int(row.month):02d}"
            else:
                period_label = str(int(row.year))

            entries.append(
                RealizedPLSummaryEntry(
                    period=period_label,
                    total_realized_pl=Decimal(str(row.total_pl)).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    ),
                    total_short_term=Decimal(str(row.total_short)).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    ),
                    total_long_term=Decimal(str(row.total_long)).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    ),
                    record_count=row.record_count,
                )
            )

        return entries

    async def _get_all_time_totals(
        self, user_id: uuid.UUID, filters: Optional[RealizedPLFilters]
    ) -> dict[str, Decimal]:
        """Get all-time cumulative totals for realized P/L."""
        stmt = (
            select(
                func.coalesce(func.sum(RealizedPL.realized_pl), Decimal("0")).label(
                    "total"
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RealizedPL.term_type == "Short-term", RealizedPL.realized_pl),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("short_term"),
                func.coalesce(
                    func.sum(
                        case(
                            (RealizedPL.term_type == "Long-term", RealizedPL.realized_pl),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("long_term"),
            )
            .where(RealizedPL.user_id == user_id)
        )

        # Apply date filters for all-time calculation when filters present
        stmt = self._apply_filters(stmt, filters)

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total": Decimal(str(row.total)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            "short_term": Decimal(str(row.short_term)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            ),
            "long_term": Decimal(str(row.long_term)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            ),
        }

    def _apply_filters(self, stmt, filters: Optional[RealizedPLFilters]):
        """Apply date and symbol filters to a query statement."""
        if filters:
            if filters.stock_symbol is not None:
                stmt = stmt.where(
                    func.upper(RealizedPL.stock_symbol)
                    == filters.stock_symbol.upper()
                )
            if filters.date_from is not None:
                stmt = stmt.where(RealizedPL.date >= filters.date_from)
            if filters.date_to is not None:
                stmt = stmt.where(RealizedPL.date <= filters.date_to)
            if filters.term_type is not None:
                stmt = stmt.where(RealizedPL.term_type == filters.term_type.value)
        return stmt
