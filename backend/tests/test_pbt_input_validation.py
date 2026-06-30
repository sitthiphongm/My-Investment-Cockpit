"""Property-based tests for input validation rejection.

**Validates: Requirements 1.4, 1.5, 1.7, 1.8**

Property 2: Invalid Transaction Inputs Are Rejected

For any transaction submission where at least one of the following holds:
quantity <= 0, price_per_share <= 0, brokerage_fee < 0, VAT < 0,
date is in the future, stock symbol contains invalid characters,
or broker name is blank — the system SHALL reject the transaction
and return a validation error identifying the invalid field(s).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.transactions import TransactionCreate
from app.schemas.enums import ActionType


# --- Strategies for valid base data ---

valid_actions = st.sampled_from([ActionType.BUY, ActionType.SELL])
valid_dates = st.dates(
    min_value=date(2000, 1, 1),
    max_value=date.today(),
)
valid_symbols = st.from_regex(r"[A-Z][A-Z0-9.]{0,19}", fullmatch=True).filter(
    lambda s: len(s) >= 1 and len(s) <= 20
)
valid_quantities = st.integers(min_value=1, max_value=99_999_999)
valid_prices = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
valid_fees = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
valid_brokers = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")


def _base_valid_data():
    """Return a dict of valid transaction data for overriding specific fields."""
    return {
        "date": date(2024, 1, 15),
        "stock_symbol": "AAPL",
        "action": ActionType.BUY,
        "quantity": 100,
        "price_per_share": Decimal("150.00"),
        "brokerage_fee": Decimal("22.50"),
        "vat": Decimal("1.58"),
        "broker": "Webull",
    }


class TestInvalidQuantityRejection:
    """Property: quantity <= 0 or > 99,999,999 is always rejected."""

    @given(quantity=st.integers(max_value=0))
    @settings(max_examples=100)
    def test_quantity_zero_or_negative_rejected(self, quantity: int):
        """
        **Validates: Requirements 1.5**

        For any quantity <= 0, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["quantity"] = quantity
        with pytest.raises(ValidationError):
            TransactionCreate(**data)

    @given(quantity=st.integers(min_value=100_000_000, max_value=999_999_999))
    @settings(max_examples=100)
    def test_quantity_exceeds_max_rejected(self, quantity: int):
        """
        **Validates: Requirements 1.5**

        For any quantity > 99,999,999, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["quantity"] = quantity
        with pytest.raises(ValidationError):
            TransactionCreate(**data)


class TestInvalidPriceRejection:
    """Property: price_per_share <= 0 or > 99,999,999.99 is always rejected."""

    @given(
        price=st.decimals(
            max_value=Decimal("0.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_price_zero_or_negative_rejected(self, price: Decimal):
        """
        **Validates: Requirements 1.5**

        For any price_per_share <= 0, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["price_per_share"] = price
        with pytest.raises(ValidationError):
            TransactionCreate(**data)

    @given(
        price=st.decimals(
            min_value=Decimal("100000000.00"),
            max_value=Decimal("999999999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_price_exceeds_max_rejected(self, price: Decimal):
        """
        **Validates: Requirements 1.5**

        For any price_per_share > 99,999,999.99, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["price_per_share"] = price
        with pytest.raises(ValidationError):
            TransactionCreate(**data)


class TestInvalidBrokerageFeeRejection:
    """Property: brokerage_fee < 0 is always rejected."""

    @given(
        fee=st.decimals(
            max_value=Decimal("-0.01"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_negative_brokerage_fee_rejected(self, fee: Decimal):
        """
        **Validates: Requirements 1.8**

        For any brokerage_fee < 0, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["brokerage_fee"] = fee
        with pytest.raises(ValidationError):
            TransactionCreate(**data)


class TestInvalidVatRejection:
    """Property: vat < 0 is always rejected."""

    @given(
        vat=st.decimals(
            max_value=Decimal("-0.01"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_negative_vat_rejected(self, vat: Decimal):
        """
        **Validates: Requirements 1.8**

        For any VAT < 0, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["vat"] = vat
        with pytest.raises(ValidationError):
            TransactionCreate(**data)


class TestFutureDateRejection:
    """Property: future dates are always rejected."""

    @given(
        days_in_future=st.integers(min_value=1, max_value=3650)
    )
    @settings(max_examples=100)
    def test_future_date_rejected(self, days_in_future: int):
        """
        **Validates: Requirements 1.7**

        For any date beyond today, TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["date"] = date.today() + timedelta(days=days_in_future)
        with pytest.raises(ValidationError):
            TransactionCreate(**data)


class TestInvalidStockSymbolRejection:
    """Property: stock symbols with spaces or special characters are rejected."""

    @given(
        symbol=st.from_regex(
            r"[A-Za-z0-9]*[ @#$%^&*!~`+=\-\[\]{}<>?,;:'\"\\|/]+[A-Za-z0-9]*",
            fullmatch=True,
        ).filter(lambda s: 1 <= len(s) <= 20)
    )
    @settings(max_examples=100)
    def test_invalid_symbol_rejected(self, symbol: str):
        """
        **Validates: Requirements 1.4**

        For any stock symbol containing spaces or special characters
        (anything other than A-Z, 0-9, or dots), TransactionCreate SHALL
        reject with ValidationError.
        """
        # Only test symbols that would actually be invalid after uppercasing
        import re
        upper_symbol = symbol.upper()
        assume(not re.match(r"^[A-Z0-9.]+$", upper_symbol) or len(upper_symbol) == 0)

        data = _base_valid_data()
        data["stock_symbol"] = symbol
        with pytest.raises(ValidationError):
            TransactionCreate(**data)


class TestBlankBrokerRejection:
    """Property: blank broker names are always rejected."""

    @given(
        broker=st.from_regex(r"[ \t\n\r]+", fullmatch=True).filter(
            lambda s: 1 <= len(s) <= 100
        )
    )
    @settings(max_examples=100)
    def test_blank_broker_rejected(self, broker: str):
        """
        **Validates: Requirements 1.4**

        For any broker name that is empty or only whitespace,
        TransactionCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["broker"] = broker
        with pytest.raises(ValidationError):
            TransactionCreate(**data)
