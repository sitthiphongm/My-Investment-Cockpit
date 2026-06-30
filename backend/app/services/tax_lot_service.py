"""Tax Lot service — manages cost basis tracking with FIFO/LIFO/AvgCost/SpecificLot."""

import uuid
from datetime import date
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tax_lot import TaxLot
from app.models.transaction import Transaction


class CostBasisMethod(str, Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    AVG_COST = "AvgCost"
    SPECIFIC_LOT = "SpecificLot"


class TaxLotService:
    """Manages tax lots for cost basis calculation and realized P/L."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_lot_from_buy(self, transaction: Transaction) -> TaxLot:
        """Create a new tax lot from a Buy or Snapshot transaction."""
        lot = TaxLot(
            user_id=transaction.user_id,
            stock_symbol=transaction.stock_symbol,
            buy_transaction_id=transaction.id,
            acquisition_date=transaction.date,
            original_quantity=transaction.quantity,
            remaining_quantity=transaction.quantity,
            cost_per_share=transaction.price_per_share,
            broker=transaction.broker,
            currency="USD",
            status="Open",
        )
        self.db.add(lot)
        return lot

    async def get_open_lots(
        self, user_id: uuid.UUID, symbol: str, method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> list[TaxLot]:
        """Get open tax lots for a symbol, ordered by method."""
        query = select(TaxLot).where(
            TaxLot.user_id == user_id,
            TaxLot.stock_symbol == symbol,
            TaxLot.remaining_quantity > 0,
        )

        if method == CostBasisMethod.FIFO:
            query = query.order_by(TaxLot.acquisition_date.asc())
        elif method == CostBasisMethod.LIFO:
            query = query.order_by(TaxLot.acquisition_date.desc())
        else:
            query = query.order_by(TaxLot.acquisition_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_avg_cost(self, user_id: uuid.UUID, symbol: str) -> Decimal:
        """Calculate weighted average cost across all open lots."""
        lots = await self.get_open_lots(user_id, symbol)
        if not lots:
            return Decimal("0")
        total_cost = sum(lot.remaining_quantity * lot.cost_per_share for lot in lots)
        total_qty = sum(lot.remaining_quantity for lot in lots)
        if total_qty == 0:
            return Decimal("0")
        return total_cost / total_qty

    async def deplete_lots(
        self,
        user_id: uuid.UUID,
        symbol: str,
        sell_quantity: int,
        sell_date: date,
        method: CostBasisMethod = CostBasisMethod.FIFO,
        specific_lot_ids: list[uuid.UUID] | None = None,
    ) -> list[dict]:
        """Deplete lots for a sell transaction. Returns list of lot matches with realized P/L info.

        Each match dict contains: lot_id, quantity_sold, cost_per_share, acquisition_date, holding_days
        """
        if method == CostBasisMethod.SPECIFIC_LOT and specific_lot_ids:
            lots = []
            for lot_id in specific_lot_ids:
                result = await self.db.execute(
                    select(TaxLot).where(TaxLot.id == lot_id, TaxLot.remaining_quantity > 0)
                )
                lot = result.scalar_one_or_none()
                if lot:
                    lots.append(lot)
        else:
            lots = await self.get_open_lots(user_id, symbol, method)

        remaining_to_sell = sell_quantity
        matches = []

        for lot in lots:
            if remaining_to_sell <= 0:
                break
            qty_from_lot = min(lot.remaining_quantity, remaining_to_sell)
            lot.remaining_quantity -= qty_from_lot
            if lot.remaining_quantity == 0:
                lot.status = "Closed"
            else:
                lot.status = "Partial"
            remaining_to_sell -= qty_from_lot
            holding_days = (sell_date - lot.acquisition_date).days

            matches.append({
                "lot_id": lot.id,
                "quantity_sold": qty_from_lot,
                "cost_per_share": lot.cost_per_share,
                "acquisition_date": lot.acquisition_date,
                "holding_days": holding_days,
            })

        if remaining_to_sell > 0:
            raise ValueError(
                f"Insufficient lots: needed {sell_quantity} shares of {symbol}, "
                f"only {sell_quantity - remaining_to_sell} available in lots"
            )

        return matches
