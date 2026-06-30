"""Unit tests for TradingService."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.enums import ActionType
from app.schemas.transactions import (
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)
from app.services.trading_service import TradingService


class FakeTransaction:
    """Minimal fake Transaction object for testing."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeResult:
    """Fake SQLAlchemy result wrapper."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [self._value] if self._value is not None else []

    def one(self):
        return self._value


class TestGrossValueCalculation:
    """Test that gross_value = quantity × price_per_share."""

    @pytest.mark.asyncio
    async def test_gross_value_buy(self):
        """Gross value for a buy is quantity * price_per_share."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="AAPL",
            action=ActionType.BUY,
            quantity=100,
            price_per_share=Decimal("25.50"),
            brokerage_fee=Decimal("3.83"),
            vat=Decimal("0.27"),
            broker="Webull",
        )

        result = await service.create_transaction(uuid.uuid4(), data)

        # The Transaction constructor is called via db.add
        call_args = db.add.call_args[0][0]
        assert call_args.gross_value == Decimal("2550.00")

    @pytest.mark.asyncio
    async def test_gross_value_sell(self):
        """Gross value for a sell is quantity * price_per_share."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock for: holdings check, avg_cost calc, hold_duration calc
        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("5000.00")
        avg_cost_row.total_qty = 200

        hold_row = MagicMock()
        hold_row.date = date(2024, 1, 1)
        hold_row.quantity = 200

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(200),  # get_holdings check
                FakeResult(avg_cost_row),  # _calculate_avg_cost
                FakeResult([hold_row]),  # _calculate_hold_duration
            ]
        )

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="AAPL",
            action=ActionType.SELL,
            quantity=50,
            price_per_share=Decimal("30.00"),
            brokerage_fee=Decimal("2.25"),
            vat=Decimal("0.16"),
            broker="Webull",
        )

        await service.create_transaction(uuid.uuid4(), data)

        # First add is the transaction, second is the realized P/L record
        call_args = db.add.call_args_list[0][0][0]
        assert call_args.gross_value == Decimal("1500.00")


class TestNetCapitalFlowCalculation:
    """Test net capital flow formula: Buy = gross + fee + vat, Sell = gross - fee - vat."""

    @pytest.mark.asyncio
    async def test_net_capital_flow_buy(self):
        """Net capital flow for buy = gross_value + brokerage_fee + vat."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="META",
            action=ActionType.BUY,
            quantity=200,
            price_per_share=Decimal("10.00"),
            brokerage_fee=Decimal("3.00"),
            vat=Decimal("0.21"),
            broker="Dime",
        )

        await service.create_transaction(uuid.uuid4(), data)

        call_args = db.add.call_args[0][0]
        # gross = 200 * 10 = 2000
        # net = 2000 + 3.00 + 0.21 = 2003.21
        assert call_args.gross_value == Decimal("2000.00")
        assert call_args.net_capital_flow == Decimal("2003.21")

    @pytest.mark.asyncio
    async def test_net_capital_flow_sell(self):
        """Net capital flow for sell = gross_value - brokerage_fee - vat."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock for: holdings check, avg_cost calc, hold_duration calc
        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("5000.00")
        avg_cost_row.total_qty = 500

        hold_row = MagicMock()
        hold_row.date = date(2024, 1, 1)
        hold_row.quantity = 500

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(500),  # get_holdings check
                FakeResult(avg_cost_row),  # _calculate_avg_cost
                FakeResult([hold_row]),  # _calculate_hold_duration
            ]
        )

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="META",
            action=ActionType.SELL,
            quantity=100,
            price_per_share=Decimal("15.00"),
            brokerage_fee=Decimal("2.25"),
            vat=Decimal("0.16"),
            broker="Dime",
        )

        await service.create_transaction(uuid.uuid4(), data)

        # First add is the transaction
        call_args = db.add.call_args_list[0][0][0]
        # gross = 100 * 15 = 1500
        # net = 1500 - 2.25 - 0.16 = 1497.59
        assert call_args.gross_value == Decimal("1500.00")
        assert call_args.net_capital_flow == Decimal("1497.59")


class TestHoldingsCheckBlocksOverselling:
    """Test that selling more than held quantity is rejected."""

    @pytest.mark.asyncio
    async def test_sell_exceeds_holdings_rejected(self):
        """Selling more than current holdings raises HTTPException 400."""
        db = AsyncMock()
        # Mock holdings check - user only has 50 shares
        db.execute = AsyncMock(return_value=FakeResult(50))

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="DRAM",
            action=ActionType.SELL,
            quantity=100,
            price_per_share=Decimal("5.00"),
            brokerage_fee=Decimal("0.75"),
            vat=Decimal("0.05"),
            broker="Webull",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_transaction(uuid.uuid4(), data)

        assert exc_info.value.status_code == 400
        assert "Insufficient holdings" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_sell_exact_holdings_allowed(self):
        """Selling exactly the held quantity is allowed."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock for: holdings check, avg_cost calc, hold_duration calc
        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("500.00")
        avg_cost_row.total_qty = 100

        hold_row = MagicMock()
        hold_row.date = date(2024, 1, 1)
        hold_row.quantity = 100

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(100),  # get_holdings check
                FakeResult(avg_cost_row),  # _calculate_avg_cost
                FakeResult([hold_row]),  # _calculate_hold_duration
            ]
        )

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="DRAM",
            action=ActionType.SELL,
            quantity=100,
            price_per_share=Decimal("5.00"),
            brokerage_fee=Decimal("0.75"),
            vat=Decimal("0.05"),
            broker="Webull",
        )

        # Should not raise
        await service.create_transaction(uuid.uuid4(), data)
        assert db.add.called


class TestEditRecalculatesDerivedFields:
    """Test that editing recalculates gross_value and net_capital_flow."""

    @pytest.mark.asyncio
    async def test_edit_recalculates_gross_value(self):
        """Editing quantity or price recalculates gross_value."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock existing transaction
        existing_tx = FakeTransaction(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            date=date(2024, 1, 10),
            stock_symbol="AAPL",
            action="Buy",
            quantity=100,
            price_per_share=Decimal("25.00"),
            gross_value=Decimal("2500.00"),
            brokerage_fee=Decimal("3.75"),
            vat=Decimal("0.26"),
            net_capital_flow=Decimal("2504.01"),
            broker="Webull",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # First call: _get_user_transaction, second call: get_holdings
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(existing_tx),  # _get_user_transaction
                FakeResult(200),  # get_holdings for old symbol
            ]
        )

        service = TradingService(db)

        data = TransactionUpdate(
            quantity=200,
            price_per_share=Decimal("30.00"),
        )

        user_id = existing_tx.user_id
        result = await service.edit_transaction(user_id, existing_tx.id, data)

        # gross_value should be 200 * 30 = 6000
        assert existing_tx.gross_value == Decimal("6000.00")
        # net_capital_flow for Buy = 6000 + 3.75 + 0.26 = 6004.01
        assert existing_tx.net_capital_flow == Decimal("6004.01")

    @pytest.mark.asyncio
    async def test_edit_action_change_recalculates_net_flow(self):
        """Changing action from Buy to Sell recalculates net_capital_flow."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        user_id = uuid.uuid4()
        existing_tx = FakeTransaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 1, 10),
            stock_symbol="AAPL",
            action="Buy",
            quantity=50,
            price_per_share=Decimal("20.00"),
            gross_value=Decimal("1000.00"),
            brokerage_fee=Decimal("1.50"),
            vat=Decimal("0.11"),
            net_capital_flow=Decimal("1001.61"),
            broker="Webull",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # First call: _get_user_transaction
        # Second call: get_holdings (for the old symbol without old tx)
        # We need enough holdings to support the sell
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(existing_tx),  # _get_user_transaction
                FakeResult(200),  # get_holdings for old symbol (includes this tx's buy)
            ]
        )

        service = TradingService(db)

        data = TransactionUpdate(action=ActionType.SELL)

        result = await service.edit_transaction(user_id, existing_tx.id, data)

        # gross_value stays 50 * 20 = 1000
        assert existing_tx.gross_value == Decimal("1000.00")
        # net_capital_flow for Sell = 1000 - 1.50 - 0.11 = 998.39
        assert existing_tx.net_capital_flow == Decimal("998.39")


class TestDeleteChecksHoldingsInvariant:
    """Test that deleting a buy/snapshot checks holdings won't go negative."""

    @pytest.mark.asyncio
    async def test_delete_buy_with_insufficient_remaining_rejected(self):
        """Deleting a buy when it would make holdings negative is rejected."""
        db = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        existing_tx = FakeTransaction(
            id=tx_id,
            user_id=user_id,
            date=date(2024, 1, 10),
            stock_symbol="DRAM",
            action="Buy",
            quantity=100,
            price_per_share=Decimal("5.00"),
            gross_value=Decimal("500.00"),
            brokerage_fee=Decimal("0.75"),
            vat=Decimal("0.05"),
            net_capital_flow=Decimal("500.80"),
            broker="Webull",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Holdings is 50 (meaning user already sold some from this buy)
        # Deleting this 100-share buy would make it 50 - 100 = -50
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(existing_tx),  # _get_user_transaction
                FakeResult(50),  # get_holdings returns 50
            ]
        )

        service = TradingService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_transaction(user_id, tx_id)

        assert exc_info.value.status_code == 400
        assert "negative holdings" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_sell_always_allowed(self):
        """Deleting a sell transaction is always allowed (it increases holdings)."""
        db = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        existing_tx = FakeTransaction(
            id=tx_id,
            user_id=user_id,
            date=date(2024, 1, 10),
            stock_symbol="DRAM",
            action="Sell",
            quantity=50,
            price_per_share=Decimal("8.00"),
            gross_value=Decimal("400.00"),
            brokerage_fee=Decimal("0.60"),
            vat=Decimal("0.04"),
            net_capital_flow=Decimal("399.36"),
            broker="Webull",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.execute = AsyncMock(return_value=FakeResult(existing_tx))

        service = TradingService(db)
        await service.delete_transaction(user_id, tx_id)

        db.delete.assert_called_once_with(existing_tx)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises_404(self):
        """Deleting a non-existent transaction raises 404."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))

        service = TradingService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_transaction(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 404


class TestListTransactionsWithFilters:
    """Test listing with filters works correctly."""

    @pytest.mark.asyncio
    async def test_list_no_filters(self):
        """Listing without filters returns all user transactions."""
        db = AsyncMock()

        txns = [
            FakeTransaction(
                id=uuid.uuid4(),
                date=date(2024, 1, 15),
                stock_symbol="AAPL",
                action="Buy",
            ),
            FakeTransaction(
                id=uuid.uuid4(),
                date=date(2024, 1, 10),
                stock_symbol="META",
                action="Sell",
            ),
        ]

        db.execute = AsyncMock(return_value=FakeResult(txns))

        service = TradingService(db)
        result = await service.list_transactions(uuid.uuid4())

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_with_symbol_filter(self):
        """Listing with symbol filter works."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = TradingService(db)
        filters = TransactionFilters(stock_symbol="aapl")

        result = await service.list_transactions(uuid.uuid4(), filters)

        # Verify the filter was applied (symbol uppercased)
        assert filters.stock_symbol == "AAPL"
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_date_range_filter(self):
        """Listing with date range filter constrains results."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = TradingService(db)
        filters = TransactionFilters(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
        )

        result = await service.list_transactions(uuid.uuid4(), filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_action_filter(self):
        """Listing with action filter constrains results."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = TradingService(db)
        filters = TransactionFilters(action=ActionType.BUY)

        result = await service.list_transactions(uuid.uuid4(), filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_broker_filter(self):
        """Listing with broker filter (case-insensitive) works."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = TradingService(db)
        filters = TransactionFilters(broker="webull")

        result = await service.list_transactions(uuid.uuid4(), filters)
        assert result == []


class TestGetHoldings:
    """Test the holdings calculation helper."""

    @pytest.mark.asyncio
    async def test_get_holdings_returns_integer(self):
        """get_holdings returns an integer value."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(150))

        service = TradingService(db)
        result = await service.get_holdings(uuid.uuid4(), "AAPL")

        assert result == 150
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_get_holdings_zero_when_no_transactions(self):
        """get_holdings returns 0 when no transactions exist."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(0))

        service = TradingService(db)
        result = await service.get_holdings(uuid.uuid4(), "XYZ")

        assert result == 0
