"""Trading service - Business logic for buy/sell/snapshot transactions."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, TransactionTag
from app.models.transaction import Transaction
from app.schemas.enums import ActionType
from app.schemas.transactions import (
    SnapshotCreate,
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)
from app.services.realized_pl_service import RealizedPLService


class TradingService:
    """Service for managing stock trading transactions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_holdings(self, user_id: uuid.UUID, symbol: str) -> Decimal:
        """Calculate total held quantity for a symbol.

        Total held = Σ buy_qty + Σ snapshot_qty - Σ sell_qty
        Supports fractional shares.
        """
        stmt = select(
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.action.in_(["Buy", "Snapshot"]), Transaction.quantity),
                        else_=-Transaction.quantity,
                    )
                ),
                0,
            )
        ).where(
            Transaction.user_id == user_id,
            Transaction.stock_symbol == symbol.upper(),
        )
        result = await self.db.execute(stmt)
        return Decimal(str(result.scalar_one()))

    async def create_transaction(
        self, user_id: uuid.UUID, data: TransactionCreate
    ) -> Transaction:
        """Create a new transaction with computed derived fields.

        - gross_value = quantity × price_per_share
        - net_capital_flow: Buy/Snapshot = gross_value + fee + vat
                           Sell = gross_value - fee - vat
        - For Sell: check holdings >= sell quantity
        """
        gross_value = Decimal(data.quantity) * data.price_per_share
        if data.action == ActionType.SELL:
            net_capital_flow = gross_value - data.brokerage_fee - data.vat
        else:
            # Buy and Snapshot both use addition
            net_capital_flow = gross_value + data.brokerage_fee + data.vat

        # Holdings check for Sell
        if data.action == ActionType.SELL:
            current_holdings = await self.get_holdings(user_id, data.stock_symbol)
            if current_holdings < data.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient holdings for {data.stock_symbol}. "
                    f"Current: {current_holdings}, Sell quantity: {data.quantity}",
                )

        transaction = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=data.date,
            stock_symbol=data.stock_symbol,
            action=data.action.value,
            quantity=data.quantity,
            price_per_share=data.price_per_share,
            gross_value=gross_value,
            brokerage_fee=data.brokerage_fee,
            vat=data.vat,
            net_capital_flow=net_capital_flow,
            broker=data.broker,
        )

        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)

        # Auto-calculate realized P/L on sell transactions
        if data.action == ActionType.SELL:
            realized_pl_service = RealizedPLService(self.db)
            await realized_pl_service.calculate_and_store(
                user_id=user_id,
                transaction_id=transaction.id,
                sell_date=data.date,
                stock_symbol=data.stock_symbol,
                sell_quantity=data.quantity,
                sell_price=data.price_per_share,
            )

        return transaction

    async def import_snapshot(
        self, user_id: uuid.UUID, data: SnapshotCreate
    ) -> list[Transaction]:
        """Bulk import snapshot entries atomically.

        - Pydantic schema handles field-level validation (SnapshotCreate/SnapshotEntry)
        - If any entry is invalid, the entire request is rejected (422 from Pydantic)
        - All entries are persisted atomically within a single flush
        - Each entry gets action="Snapshot", date=today, brokerage_fee=0, vat=0
        - gross_value = quantity × price_per_share
        - net_capital_flow = gross_value (no fees for snapshots)
        """
        transactions: list[Transaction] = []

        for entry in data.entries:
            gross_value = Decimal(entry.quantity) * entry.price_per_share
            net_capital_flow = gross_value  # No fees for snapshots

            transaction = Transaction(
                id=uuid.uuid4(),
                user_id=user_id,
                date=date.today(),
                stock_symbol=entry.stock_symbol,
                action=ActionType.SNAPSHOT.value,
                quantity=entry.quantity,
                price_per_share=entry.price_per_share,
                gross_value=gross_value,
                brokerage_fee=Decimal("0"),
                vat=Decimal("0"),
                net_capital_flow=net_capital_flow,
                broker=entry.broker,
            )
            self.db.add(transaction)
            transactions.append(transaction)

        # Flush all at once — if any insert fails, none persist (atomic)
        await self.db.flush()

        # Refresh all to get DB-generated fields
        for tx in transactions:
            await self.db.refresh(tx)

        return transactions

    async def edit_transaction(
        self, user_id: uuid.UUID, tx_id: uuid.UUID, data: TransactionUpdate
    ) -> Transaction:
        """Edit an existing transaction.

        - Verify transaction exists and belongs to user
        - Merge updated fields, recalculate gross_value and net_capital_flow
        - Check holdings invariant with the new values
        """
        transaction = await self._get_user_transaction(user_id, tx_id)

        # Build the updated values by merging provided fields
        update_fields = data.model_dump(exclude_unset=True)

        # Apply updates to a working copy of values
        new_date_raw = update_fields.get("date", transaction.date)
        # Parse date string if needed
        if isinstance(new_date_raw, str):
            from datetime import datetime as dt
            new_date = dt.strptime(new_date_raw, "%Y-%m-%d").date()
        else:
            new_date = new_date_raw
        new_symbol = update_fields.get("stock_symbol", transaction.stock_symbol)
        new_action = update_fields.get("action", transaction.action)
        new_quantity = update_fields.get("quantity", transaction.quantity)
        new_price = update_fields.get("price_per_share", transaction.price_per_share)
        new_fee = update_fields.get("brokerage_fee", transaction.brokerage_fee)
        new_vat = update_fields.get("vat", transaction.vat)
        new_broker = update_fields.get("broker", transaction.broker)

        # Normalize action value
        if isinstance(new_action, ActionType):
            new_action_str = new_action.value
        else:
            new_action_str = new_action

        # Recalculate derived fields
        new_gross_value = Decimal(new_quantity) * Decimal(str(new_price))
        if new_action_str == ActionType.SELL.value:
            new_net_capital_flow = new_gross_value - Decimal(str(new_fee)) - Decimal(str(new_vat))
        else:
            new_net_capital_flow = new_gross_value + Decimal(str(new_fee)) + Decimal(str(new_vat))

        # Holdings invariant check
        # We need to check if the edit would cause negative holdings
        # First, calculate holdings WITHOUT the old transaction
        old_action = transaction.action
        old_symbol = transaction.stock_symbol
        old_quantity = transaction.quantity

        # Check the old symbol's holdings after removing this transaction
        if old_action in ("Buy", "Snapshot"):
            holdings_without_old = await self.get_holdings(user_id, old_symbol) - old_quantity
        else:  # Sell
            holdings_without_old = await self.get_holdings(user_id, old_symbol) + old_quantity

        # If the symbol changed, check both old and new symbol
        if new_symbol.upper() != old_symbol.upper():
            # Old symbol: removing a buy/snapshot reduces holdings, removing a sell increases
            if old_action in ("Buy", "Snapshot"):
                if holdings_without_old < 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Editing this transaction would result in negative holdings "
                        f"for {old_symbol}.",
                    )
            # New symbol: adding a sell requires sufficient holdings
            if new_action_str == ActionType.SELL.value:
                new_symbol_holdings = await self.get_holdings(user_id, new_symbol)
                if new_symbol_holdings < new_quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient holdings for {new_symbol}. "
                        f"Current: {new_symbol_holdings}, Sell quantity: {new_quantity}",
                    )
        else:
            # Same symbol - simulate the edit
            if new_action_str == ActionType.SELL.value:
                # After removing old tx and applying new sell
                if new_action_str == ActionType.SELL.value:
                    simulated_holdings = holdings_without_old - new_quantity
                else:
                    simulated_holdings = holdings_without_old + new_quantity
            elif new_action_str in (ActionType.BUY.value, ActionType.SNAPSHOT.value):
                simulated_holdings = holdings_without_old + new_quantity
            else:
                simulated_holdings = holdings_without_old

            # Check if changing from Buy/Snapshot to Sell would cause negative
            if new_action_str == ActionType.SELL.value and simulated_holdings < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Editing this transaction would result in negative holdings "
                    f"for {new_symbol}. Simulated holdings: {simulated_holdings}",
                )
            # If old was Buy/Snapshot, check the remaining holdings are not negative
            if old_action in ("Buy", "Snapshot") and new_action_str in (
                ActionType.BUY.value,
                ActionType.SNAPSHOT.value,
            ):
                # Reducing buy quantity: check that remaining holds are ok
                # holdings_without_old already excludes the old buy, so adding new buy is fine
                pass

        # Apply updates
        transaction.date = new_date
        transaction.stock_symbol = new_symbol.upper() if isinstance(new_symbol, str) else new_symbol
        transaction.action = new_action_str
        transaction.quantity = new_quantity
        transaction.price_per_share = new_price
        transaction.brokerage_fee = new_fee
        transaction.vat = new_vat
        transaction.gross_value = new_gross_value
        transaction.net_capital_flow = new_net_capital_flow
        transaction.broker = new_broker

        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def delete_transaction(
        self, user_id: uuid.UUID, tx_id: uuid.UUID
    ) -> None:
        """Delete a transaction.

        - Verify transaction exists and belongs to user
        - If it's a Buy/Snapshot, check that removing it won't make holdings negative
        """
        transaction = await self._get_user_transaction(user_id, tx_id)

        # If it's a Buy or Snapshot, removing it reduces holdings
        if transaction.action in ("Buy", "Snapshot"):
            current_holdings = await self.get_holdings(user_id, transaction.stock_symbol)
            holdings_after_delete = current_holdings - transaction.quantity
            if holdings_after_delete < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete this {transaction.action} transaction. "
                    f"It would result in negative holdings for "
                    f"{transaction.stock_symbol} "
                    f"(current: {current_holdings}, "
                    f"after delete: {holdings_after_delete}).",
                )

        await self.db.delete(transaction)
        await self.db.flush()

    async def list_transactions(
        self, user_id: uuid.UUID, filters: Optional[TransactionFilters] = None
    ) -> list[Transaction]:
        """List transactions with optional filters, sorted by date descending.

        Filters: date_from, date_to, stock_symbol (case-insensitive),
                 broker (case-insensitive), action, tag (case-insensitive)
        """
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        )

        if filters:
            if filters.date_from is not None:
                stmt = stmt.where(Transaction.date >= filters.date_from)
            if filters.date_to is not None:
                stmt = stmt.where(Transaction.date <= filters.date_to)
            if filters.stock_symbol is not None:
                stmt = stmt.where(
                    func.upper(Transaction.stock_symbol) == filters.stock_symbol.upper()
                )
            if filters.broker is not None:
                stmt = stmt.where(
                    func.upper(Transaction.broker) == filters.broker.upper()
                )
            if filters.action is not None:
                stmt = stmt.where(Transaction.action == filters.action.value)
            if filters.tag is not None:
                # Join with TransactionTag and Tag to filter by tag name
                stmt = stmt.join(
                    TransactionTag, TransactionTag.transaction_id == Transaction.id
                ).join(
                    Tag, Tag.id == TransactionTag.tag_id
                ).where(
                    func.lower(Tag.name) == filters.tag.lower(),
                    Tag.user_id == user_id,
                )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def import_snapshot(
        self, user_id: uuid.UUID, data: SnapshotCreate
    ) -> list[Transaction]:
        """Bulk import snapshot entries atomically.

        All entries are validated and inserted together. If any entry fails,
        the entire batch is rejected (all-or-nothing).
        Snapshot entries use Action="Snapshot" and date is today.
        """
        transactions: list[Transaction] = []
        snapshot_date = date.today()

        for entry in data.entries:
            gross_value = Decimal(entry.quantity) * entry.price_per_share
            # Snapshot uses the same formula as Buy: gross + fee + vat
            # Snapshots have no fee/vat by default
            net_capital_flow = gross_value

            transaction = Transaction(
                id=uuid.uuid4(),
                user_id=user_id,
                date=snapshot_date,
                stock_symbol=entry.stock_symbol.upper(),
                action=ActionType.SNAPSHOT.value,
                quantity=entry.quantity,
                price_per_share=entry.price_per_share,
                gross_value=gross_value,
                brokerage_fee=Decimal("0"),
                vat=Decimal("0"),
                net_capital_flow=net_capital_flow,
                broker=entry.broker,
            )
            self.db.add(transaction)
            transactions.append(transaction)

        await self.db.flush()
        for tx in transactions:
            await self.db.refresh(tx)
        return transactions

    async def _get_user_transaction(
        self, user_id: uuid.UUID, tx_id: uuid.UUID
    ) -> Transaction:
        """Get a transaction by ID, verifying it belongs to the user."""
        stmt = select(Transaction).where(
            Transaction.id == tx_id,
            Transaction.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        transaction = result.scalar_one_or_none()
        if transaction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction {tx_id} not found.",
            )
        return transaction
