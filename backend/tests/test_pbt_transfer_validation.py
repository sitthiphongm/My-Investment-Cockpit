"""Property-based tests for transfer validation.

**Validates: Requirements 3.4, 3.5, 3.6, 3.7**

Property 5: Transfer Validation

For any money transfer where the amount is outside [0.01, 999,999,999.99],
has more than 2 decimal places, the broker name is empty/whitespace-only,
transfer type is not "In"/"Out", or date is invalid/future — the system
SHALL reject the transfer and return a validation error.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.transfers import TransferCreate
from app.schemas.enums import TransferType


# --- Strategies for valid base data ---

valid_dates = st.dates(
    min_value=date(2000, 1, 1),
    max_value=date.today(),
)
valid_brokers = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")
valid_transfer_types = st.sampled_from([TransferType.IN, TransferType.OUT])
valid_amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


def _base_valid_data():
    """Return a dict of valid transfer data for overriding specific fields."""
    return {
        "date": date(2024, 6, 15),
        "broker": "Webull",
        "transfer_type": TransferType.IN,
        "amount": Decimal("10000.00"),
    }


class TestInvalidAmountTooLow:
    """Property: amount < 0.01 is always rejected."""

    @given(
        amount=st.decimals(
            max_value=Decimal("0.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_amount_below_minimum_rejected(self, amount: Decimal):
        """
        **Validates: Requirements 3.4**

        For any amount < 0.01, TransferCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["amount"] = amount
        with pytest.raises(ValidationError):
            TransferCreate(**data)


class TestInvalidAmountTooHigh:
    """Property: amount > 999,999,999.99 is always rejected."""

    @given(
        amount=st.decimals(
            min_value=Decimal("1000000000.00"),
            max_value=Decimal("9999999999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_amount_above_maximum_rejected(self, amount: Decimal):
        """
        **Validates: Requirements 3.4**

        For any amount > 999,999,999.99, TransferCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["amount"] = amount
        with pytest.raises(ValidationError):
            TransferCreate(**data)


class TestInvalidAmountTooManyDecimals:
    """Property: amount with more than 2 decimal places is always rejected."""

    @given(
        amount=st.decimals(
            min_value=Decimal("0.001"),
            max_value=Decimal("999999999.999"),
            places=3,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100)
    def test_amount_more_than_2_decimals_rejected(self, amount: Decimal):
        """
        **Validates: Requirements 3.4**

        For any amount with more than 2 decimal places, TransferCreate
        SHALL reject with ValidationError.
        """
        # Ensure it actually has more than 2 decimal places
        assume(amount.as_tuple().exponent < -2)
        data = _base_valid_data()
        data["amount"] = amount
        with pytest.raises(ValidationError):
            TransferCreate(**data)


class TestBlankBrokerRejection:
    """Property: blank or whitespace-only broker names are always rejected."""

    @given(
        broker=st.from_regex(r"[ \t\n\r]+", fullmatch=True).filter(
            lambda s: 1 <= len(s) <= 100
        )
    )
    @settings(max_examples=100)
    def test_whitespace_only_broker_rejected(self, broker: str):
        """
        **Validates: Requirements 3.7**

        For any broker name that is only whitespace, TransferCreate
        SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["broker"] = broker
        with pytest.raises(ValidationError):
            TransferCreate(**data)


class TestInvalidTransferType:
    """Property: transfer_type not 'In' or 'Out' is always rejected."""

    @given(
        invalid_type=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s not in ("In", "Out"))
    )
    @settings(max_examples=100)
    def test_invalid_transfer_type_rejected(self, invalid_type: str):
        """
        **Validates: Requirements 3.5**

        For any transfer_type value that is not 'In' or 'Out',
        TransferCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["transfer_type"] = invalid_type
        with pytest.raises(ValidationError):
            TransferCreate(**data)


class TestFutureDateRejection:
    """Property: future dates are always rejected."""

    @given(
        days_in_future=st.integers(min_value=1, max_value=3650)
    )
    @settings(max_examples=100)
    def test_future_date_rejected(self, days_in_future: int):
        """
        **Validates: Requirements 3.6**

        For any date beyond today, TransferCreate SHALL reject with ValidationError.
        """
        data = _base_valid_data()
        data["date"] = date.today() + timedelta(days=days_in_future)
        with pytest.raises(ValidationError):
            TransferCreate(**data)
