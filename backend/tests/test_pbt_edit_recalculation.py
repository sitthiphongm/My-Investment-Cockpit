"""Property-based tests for edit recalculation consistency.

Property 25: Edit Recalculation Consistency
- Generate edit operations; verify gross_value, net_capital_flow, and holdings
  are recalculated correctly after editing a transaction.

For any edited transaction with new quantity Q, new price P, new fee F, and new VAT V:
- gross_value SHALL equal Q × P
- net_capital_flow SHALL equal:
  - Buy/Snapshot: gross_value + F + V
  - Sell: gross_value - F - V
- No edit operation SHALL cause negative holdings for any stock symbol.

**Validates: Requirements 6.5**
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.models.transaction import Transaction
from app.schemas.enums import ActionType
from app.schemas.transactions import TransactionUpdate
from app.services.trading_service import TradingService


# Strategies for generating valid values
decimal_price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

fee_strategy = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("10000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

vat_strategy = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

quantity_strategy = st.integers(min_value=1, max_value=99_999_999)

action_strategy = st.sampled_from([ActionType.BUY, ActionType.SELL])


def make_existing_transaction(
    user_id: uuid.UUID,
    tx_id: uuid.UUID,
    action: str = "Buy",
    quantity: int = 100,
    price: Decimal = Decimal("10.00"),
    fee: Decimal = Decimal("1.50"),
    vat: Decimal = Decimal("0.11"),
) -> Transaction:
    """Create a mock existing transaction object."""
    gross_value = Decimal(quantity) * price
    if action == "Sell":
        net_capital_flow = gross_value - fee - vat
    else:
        net_capital_flow = gross_value + fee + vat

    tx = Transaction()
    tx.id = tx_id
    tx.user_id = user_id
    tx.date = date(2024, 1, 15)
    tx.stock_symbol = "TEST"
    tx.action = action
    tx.quantity = quantity
    tx.price_per_share = price
    tx.gross_value = gross_value
    tx.brokerage_fee = fee
    tx.vat = vat
    tx.net_capital_flow = net_capital_flow
    tx.broker = "TestBroker"
    return tx


class FakeResult:
    """Fake SQLAlchemy result for mocking queries."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class TestEditRecalculationConsistencyProperty:
    """Property 25: Edit Recalculation Consistency.

    For any edited transaction with new quantity Q, new price P, new fee F, new VAT V:
    - gross_value is recalculated as Q × P
    - net_capital_flow is recalculated based on the action:
      - Buy: gross_value + fee + vat
      - Sell: gross_value - fee - vat
    - The recalculated values are consistent with the formula

    **Validates: Requirements 6.5**
    """

    @pytest.mark.asyncio
    @settings(max_examples=200)
    @given(
        new_quantity=quantity_strategy,
        new_price=decimal_price_strategy,
        new_fee=fee_strategy,
        new_vat=vat_strategy,
    )
    async def test_edit_buy_recalculates_correctly(
        self,
        new_quantity: int,
        new_price: Decimal,
        new_fee: Decimal,
        new_vat: Decimal,
    ):
        """Editing a Buy transaction recalculates gross_value and net_capital_flow.

        After edit: gross_value = new_qty × new_price,
                    net_capital_flow = gross_value + new_fee + new_vat
        """
        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()

        # Create existing Buy transaction with initial values
        existing_tx = make_existing_transaction(
            user_id=user_id,
            tx_id=tx_id,
            action="Buy",
            quantity=100,
            price=Decimal("50.00"),
            fee=Decimal("7.50"),
            vat=Decimal("0.53"),
        )

        # Mock DB: _get_user_transaction returns the existing tx
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock execute to handle both _get_user_transaction and get_holdings
        # First call: _get_user_transaction (returns the transaction)
        # Second call: get_holdings (returns large enough holdings)
        get_tx_result = MagicMock()
        get_tx_result.scalar_one_or_none.return_value = existing_tx

        holdings_result = MagicMock()
        holdings_result.scalar_one.return_value = 99_999_999

        db.execute = AsyncMock(side_effect=[get_tx_result, holdings_result])

        service = TradingService(db)

        update_data = TransactionUpdate(
            quantity=new_quantity,
            price_per_share=new_price,
            brokerage_fee=new_fee,
            vat=new_vat,
        )

        result = await service.edit_transaction(user_id, tx_id, update_data)

        # Verify recalculation
        expected_gross = Decimal(new_quantity) * new_price
        expected_net = expected_gross + new_fee + new_vat

        assert result.gross_value == expected_gross, (
            f"gross_value mismatch: got {result.gross_value}, "
            f"expected {expected_gross} (qty={new_quantity}, price={new_price})"
        )
        assert result.net_capital_flow == expected_net, (
            f"net_capital_flow mismatch: got {result.net_capital_flow}, "
            f"expected {expected_net} (gross={expected_gross}, fee={new_fee}, vat={new_vat})"
        )

    @pytest.mark.asyncio
    @settings(max_examples=200)
    @given(
        new_quantity=quantity_strategy,
        new_price=decimal_price_strategy,
        new_fee=fee_strategy,
        new_vat=vat_strategy,
    )
    async def test_edit_sell_recalculates_correctly(
        self,
        new_quantity: int,
        new_price: Decimal,
        new_fee: Decimal,
        new_vat: Decimal,
    ):
        """Editing a Sell transaction recalculates gross_value and net_capital_flow.

        After edit: gross_value = new_qty × new_price,
                    net_capital_flow = gross_value - new_fee - new_vat
        """
        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()

        # Create existing Sell transaction with initial values
        existing_tx = make_existing_transaction(
            user_id=user_id,
            tx_id=tx_id,
            action="Sell",
            quantity=50,
            price=Decimal("60.00"),
            fee=Decimal("9.00"),
            vat=Decimal("0.63"),
        )

        # Mock DB
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        get_tx_result = MagicMock()
        get_tx_result.scalar_one_or_none.return_value = existing_tx

        # Holdings must be large enough to support the sell
        holdings_result = MagicMock()
        holdings_result.scalar_one.return_value = 99_999_999

        db.execute = AsyncMock(side_effect=[get_tx_result, holdings_result])

        service = TradingService(db)

        update_data = TransactionUpdate(
            quantity=new_quantity,
            price_per_share=new_price,
            brokerage_fee=new_fee,
            vat=new_vat,
        )

        result = await service.edit_transaction(user_id, tx_id, update_data)

        # Verify recalculation
        expected_gross = Decimal(new_quantity) * new_price
        expected_net = expected_gross - new_fee - new_vat

        assert result.gross_value == expected_gross, (
            f"gross_value mismatch: got {result.gross_value}, "
            f"expected {expected_gross} (qty={new_quantity}, price={new_price})"
        )
        assert result.net_capital_flow == expected_net, (
            f"net_capital_flow mismatch: got {result.net_capital_flow}, "
            f"expected {expected_net} (gross={expected_gross}, fee={new_fee}, vat={new_vat})"
        )

    @pytest.mark.asyncio
    @settings(max_examples=200)
    @given(
        new_quantity=quantity_strategy,
        new_price=decimal_price_strategy,
        new_fee=fee_strategy,
        new_vat=vat_strategy,
        new_action=action_strategy,
    )
    async def test_edit_action_change_recalculates_correctly(
        self,
        new_quantity: int,
        new_price: Decimal,
        new_fee: Decimal,
        new_vat: Decimal,
        new_action: ActionType,
    ):
        """Editing a transaction's action type recalculates net_capital_flow per new action.

        Changing from Buy to Sell or Sell to Buy should recalculate using the
        new action's formula.
        """
        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()

        # Start with a Buy transaction
        existing_tx = make_existing_transaction(
            user_id=user_id,
            tx_id=tx_id,
            action="Buy",
            quantity=100,
            price=Decimal("50.00"),
            fee=Decimal("7.50"),
            vat=Decimal("0.53"),
        )

        # Mock DB
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        get_tx_result = MagicMock()
        get_tx_result.scalar_one_or_none.return_value = existing_tx

        # Holdings must be large enough to cover any action change.
        # When changing Buy(100) to Sell(new_quantity):
        #   holdings_without_old = holdings - 100 (removing old buy)
        #   simulated = holdings_without_old - new_quantity
        # We need: holdings - 100 - new_quantity >= 0
        # So holdings >= new_quantity + 100
        required_holdings = new_quantity + existing_tx.quantity
        holdings_result = MagicMock()
        holdings_result.scalar_one.return_value = required_holdings

        db.execute = AsyncMock(side_effect=[get_tx_result, holdings_result])

        service = TradingService(db)

        update_data = TransactionUpdate(
            action=new_action,
            quantity=new_quantity,
            price_per_share=new_price,
            brokerage_fee=new_fee,
            vat=new_vat,
        )

        result = await service.edit_transaction(user_id, tx_id, update_data)

        # Verify recalculation based on new action
        expected_gross = Decimal(new_quantity) * new_price
        if new_action == ActionType.SELL:
            expected_net = expected_gross - new_fee - new_vat
        else:
            expected_net = expected_gross + new_fee + new_vat

        assert result.gross_value == expected_gross, (
            f"gross_value mismatch: got {result.gross_value}, "
            f"expected {expected_gross} (qty={new_quantity}, price={new_price})"
        )
        assert result.net_capital_flow == expected_net, (
            f"net_capital_flow mismatch for action={new_action.value}: "
            f"got {result.net_capital_flow}, expected {expected_net} "
            f"(gross={expected_gross}, fee={new_fee}, vat={new_vat})"
        )


    @pytest.mark.asyncio
    @settings(max_examples=200)
    @given(
        existing_holdings=st.integers(min_value=1, max_value=1000),
        old_buy_quantity=st.integers(min_value=1, max_value=500),
        new_sell_quantity=st.integers(min_value=1, max_value=99_999_999),
    )
    async def test_edit_rejects_negative_holdings(
        self,
        existing_holdings: int,
        old_buy_quantity: int,
        new_sell_quantity: int,
    ):
        """Editing a transaction SHALL be rejected if it would cause negative holdings.

        When changing a Buy to a Sell, or increasing a Sell quantity beyond available
        holdings, the edit must be rejected.

        **Validates: Requirements 6.5**
        """
        # Ensure old buy quantity is part of existing holdings
        assume(old_buy_quantity <= existing_holdings)
        # Ensure new sell quantity exceeds holdings without the old buy
        # holdings_without_old = existing_holdings - old_buy_quantity
        # For a sell, simulated_holdings = holdings_without_old - new_sell_quantity < 0
        holdings_without_old = existing_holdings - old_buy_quantity
        assume(new_sell_quantity > holdings_without_old)

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()

        # Create existing Buy transaction
        existing_tx = make_existing_transaction(
            user_id=user_id,
            tx_id=tx_id,
            action="Buy",
            quantity=old_buy_quantity,
            price=Decimal("10.00"),
            fee=Decimal("1.50"),
            vat=Decimal("0.11"),
        )

        # Mock DB
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        get_tx_result = MagicMock()
        get_tx_result.scalar_one_or_none.return_value = existing_tx

        # get_holdings returns current holdings (including the old buy)
        holdings_result = MagicMock()
        holdings_result.scalar_one.return_value = existing_holdings

        db.execute = AsyncMock(side_effect=[get_tx_result, holdings_result])

        service = TradingService(db)

        # Change Buy to Sell with quantity that exceeds available holdings
        update_data = TransactionUpdate(
            action=ActionType.SELL,
            quantity=new_sell_quantity,
            price_per_share=Decimal("10.00"),
            brokerage_fee=Decimal("1.50"),
            vat=Decimal("0.11"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.edit_transaction(user_id, tx_id, update_data)

        assert exc_info.value.status_code == 400
        assert "negative holdings" in exc_info.value.detail.lower() or \
               "insufficient holdings" in exc_info.value.detail.lower()
