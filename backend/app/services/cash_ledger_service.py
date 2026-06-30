"""Cash Ledger service — calculates broker-level cash from all financial activities."""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash_adjustment import CashAdjustment
from app.models.dividend_record import DividendRecord
from app.models.transaction import Transaction
from app.models.transfer import Transfer


@dataclass
class BrokerCashLedger:
    """Cash ledger summary for a single broker."""

    broker: str
    starting_cash: Decimal = Decimal("0")
    deposits: Decimal = Decimal("0")
    withdrawals: Decimal = Decimal("0")
    buy_outflows: Decimal = Decimal("0")
    sell_inflows: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    dividends: Decimal = Decimal("0")
    fx_adjustments: Decimal = Decimal("0")
    manual_adjustments: Decimal = Decimal("0")

    @property
    def ending_cash(self) -> Decimal:
        return (
            self.starting_cash
            + self.deposits
            - self.withdrawals
            - self.buy_outflows
            + self.sell_inflows
            - self.fees
            + self.dividends
            + self.fx_adjustments
            + self.manual_adjustments
        )

    @property
    def is_negative(self) -> bool:
        return self.ending_cash < 0


class CashLedgerService:
    """Calculates cash ledger per broker from transfers, transactions, dividends, and adjustments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ledger_by_broker(self, user_id: uuid.UUID) -> list[BrokerCashLedger]:
        """Calculate cash ledger for all brokers used by this user."""
        brokers = await self._get_all_brokers(user_id)
        ledgers = []
        for broker in brokers:
            ledger = await self._calculate_broker_ledger(user_id, broker)
            ledgers.append(ledger)
        return ledgers

    async def get_total_cash(self, user_id: uuid.UUID) -> Decimal:
        """Total cash available across all brokers."""
        ledgers = await self.get_ledger_by_broker(user_id)
        return sum(l.ending_cash for l in ledgers)

    async def _get_all_brokers(self, user_id: uuid.UUID) -> list[str]:
        """Get all unique brokers from transfers and transactions."""
        transfer_brokers = await self.db.execute(
            select(Transfer.broker).where(Transfer.user_id == user_id).distinct()
        )
        tx_brokers = await self.db.execute(
            select(Transaction.broker).where(Transaction.user_id == user_id).distinct()
        )
        all_brokers = set()
        for row in transfer_brokers.scalars():
            all_brokers.add(row)
        for row in tx_brokers.scalars():
            all_brokers.add(row)
        return sorted(all_brokers)

    async def _calculate_broker_ledger(
        self, user_id: uuid.UUID, broker: str
    ) -> BrokerCashLedger:
        """Calculate the full cash ledger for a single broker."""
        ledger = BrokerCashLedger(broker=broker)

        # Deposits (In transfers)
        result = await self.db.execute(
            select(func.coalesce(func.sum(Transfer.converted_usd_amount), 0)).where(
                Transfer.user_id == user_id,
                Transfer.broker == broker,
                Transfer.transfer_type == "In",
            )
        )
        ledger.deposits = result.scalar() or Decimal("0")

        # Withdrawals (Out transfers)
        result = await self.db.execute(
            select(func.coalesce(func.sum(Transfer.converted_usd_amount), 0)).where(
                Transfer.user_id == user_id,
                Transfer.broker == broker,
                Transfer.transfer_type == "Out",
            )
        )
        ledger.withdrawals = result.scalar() or Decimal("0")

        # Buy outflows (net_capital_flow for Buy + Snapshot transactions)
        result = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.net_capital_flow), 0)).where(
                Transaction.user_id == user_id,
                Transaction.broker == broker,
                Transaction.action.in_(["Buy", "Snapshot"]),
            )
        )
        ledger.buy_outflows = result.scalar() or Decimal("0")

        # Sell inflows (net_capital_flow for Sell transactions)
        result = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.net_capital_flow), 0)).where(
                Transaction.user_id == user_id,
                Transaction.broker == broker,
                Transaction.action == "Sell",
            )
        )
        ledger.sell_inflows = result.scalar() or Decimal("0")

        # Dividends
        result = await self.db.execute(
            select(func.coalesce(func.sum(DividendRecord.total_amount), 0)).where(
                DividendRecord.user_id == user_id,
                DividendRecord.broker == broker,
            )
        )
        ledger.dividends = result.scalar() or Decimal("0")

        # Manual adjustments
        result = await self.db.execute(
            select(func.coalesce(func.sum(CashAdjustment.amount), 0)).where(
                CashAdjustment.user_id == user_id,
                CashAdjustment.broker == broker,
            )
        )
        ledger.manual_adjustments = result.scalar() or Decimal("0")

        # FX fees from transfers
        result = await self.db.execute(
            select(func.coalesce(func.sum(Transfer.fx_fee), 0)).where(
                Transfer.user_id == user_id,
                Transfer.broker == broker,
            )
        )
        ledger.fx_adjustments = -(result.scalar() or Decimal("0"))

        return ledger
