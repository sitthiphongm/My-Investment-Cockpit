"""Property-based tests for trading calculation logic.

Property 1: Net Capital Flow Calculation
- For any valid transaction (buy or sell) with quantity Q, price P, brokerage fee F,
  and VAT V, the gross_value SHALL equal Q × P, and the net_capital_flow SHALL equal
  (Q × P) + F + V for buys or (Q × P) - F - V for sells.

**Validates: Requirements 1.1, 1.2, 1.3**
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.enums import ActionType
from app.schemas.transactions import TransactionCreate
from app.services.trading_service import TradingService


class FakeResult:
    """Fake SQLAlchemy result for mocking database queries.

    Supports all result methods used by TradingService and RealizedPLService:
    - scalar_one() — for get_holdings query
    - one() — for _calculate_avg_cost aggregate query
    - all() — for _calculate_hold_duration list query
    - scalars().all() — for list queries
    """

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value

    def one(self):
        """Return a named-tuple-like object for aggregate queries."""
        from unittest.mock import MagicMock
        row = MagicMock()
        row.total_cost = self._value * Decimal("10")  # fake cost
        row.total_qty = self._value
        return row

    def all(self):
        """Return empty list for row-listing queries."""
        return []

    def scalars(self):
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.all.return_value = []
        return mock


# Strategy for generating valid Decimal values with 2 decimal places
decimal_strategy = st.decimals(
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


class TestNetCapitalFlowCalculationProperty:
    """Property 1: Net Capital Flow Calculation.

    For any valid transaction (buy or sell) with quantity Q, price P,
    brokerage fee F, and VAT V:
    - gross_value == Q × P
    - Buy: net_capital_flow == gross_value + F + V
    - Sell: net_capital_flow == gross_value - F - V

    **Validates: Requirements 1.1, 1.2, 1.3**
    """

    @pytest.mark.asyncio
    @settings(max_examples=200)
    @given(
        quantity=quantity_strategy,
        price_per_share=decimal_strategy,
        brokerage_fee=fee_strategy,
        vat=vat_strategy,
    )
    async def test_buy_net_capital_flow(
        self,
        quantity: int,
        price_per_share: Decimal,
        brokerage_fee: Decimal,
        vat: Decimal,
    ):
        """For Buy: gross_value = qty × price, net_capital_flow = gross + fee + vat."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="TEST",
            action=ActionType.BUY,
            quantity=quantity,
            price_per_share=price_per_share,
            brokerage_fee=brokerage_fee,
            vat=vat,
            broker="TestBroker",
        )

        await service.create_transaction(uuid.uuid4(), data)

        created_tx = db.add.call_args[0][0]

        expected_gross = Decimal(quantity) * price_per_share
        expected_net = expected_gross + brokerage_fee + vat

        assert created_tx.gross_value == expected_gross, (
            f"gross_value mismatch: got {created_tx.gross_value}, "
            f"expected {expected_gross} (qty={quantity}, price={price_per_share})"
        )
        assert created_tx.net_capital_flow == expected_net, (
            f"net_capital_flow mismatch: got {created_tx.net_capital_flow}, "
            f"expected {expected_net} (gross={expected_gross}, fee={brokerage_fee}, vat={vat})"
        )

    @pytest.mark.asyncio
    @settings(max_examples=200)
    @given(
        quantity=quantity_strategy,
        price_per_share=decimal_strategy,
        brokerage_fee=fee_strategy,
        vat=vat_strategy,
    )
    async def test_sell_net_capital_flow(
        self,
        quantity: int,
        price_per_share: Decimal,
        brokerage_fee: Decimal,
        vat: Decimal,
    ):
        """For Sell: gross_value = qty × price, net_capital_flow = gross - fee - vat."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        # Mock holdings check to always return sufficient holdings
        db.execute = AsyncMock(return_value=FakeResult(99_999_999))

        service = TradingService(db)

        data = TransactionCreate(
            date=date(2024, 1, 15),
            stock_symbol="TEST",
            action=ActionType.SELL,
            quantity=quantity,
            price_per_share=price_per_share,
            brokerage_fee=brokerage_fee,
            vat=vat,
            broker="TestBroker",
        )

        await service.create_transaction(uuid.uuid4(), data)

        # Get the Transaction object (first db.add call; RealizedPL may be added second)
        created_tx = db.add.call_args_list[0][0][0]

        expected_gross = Decimal(quantity) * price_per_share
        expected_net = expected_gross - brokerage_fee - vat

        assert created_tx.gross_value == expected_gross, (
            f"gross_value mismatch: got {created_tx.gross_value}, "
            f"expected {expected_gross} (qty={quantity}, price={price_per_share})"
        )
        assert created_tx.net_capital_flow == expected_net, (
            f"net_capital_flow mismatch: got {created_tx.net_capital_flow}, "
            f"expected {expected_net} (gross={expected_gross}, fee={brokerage_fee}, vat={vat})"
        )
