"""Property-based test for Snapshot Import Atomicity (Property 4).

**Validates: Requirements 2.5, 2.4, 2.6**

Property 4: Snapshot Import Atomicity
For any batch of snapshot entries where at least one entry fails validation
(missing field, quantity <= 0, or price <= 0), the system SHALL reject the
entire batch and persist none of the entries.

Tests verify:
1. Valid batches: SnapshotCreate(entries=[...valid...]) succeeds, all entries persisted
2. Invalid batches: SnapshotCreate(entries=[...some invalid...]) raises ValidationError
   before reaching the service (nothing persisted)
3. The count of persisted entries matches: either ALL or NONE
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.transactions import SnapshotCreate, SnapshotEntry
from app.services.trading_service import TradingService


# --- Strategies ---

# Valid stock symbol: 1-20 uppercase alphanumeric chars + dots
valid_symbol_st = st.from_regex(r"^[A-Z0-9.]{1,10}$", fullmatch=True)

# Valid quantity: integer > 0 and <= 99,999,999
valid_quantity_st = st.integers(min_value=1, max_value=99_999_999)

# Valid price_per_share: Decimal > 0 and <= 99,999,999.99
valid_price_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Valid broker: 1-100 non-blank characters
valid_broker_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")


# A valid SnapshotEntry as a dict
valid_entry_st = st.builds(
    dict,
    stock_symbol=valid_symbol_st,
    quantity=valid_quantity_st,
    price_per_share=valid_price_st,
    broker=valid_broker_st,
)


# Invalid entry strategies: at least one field violates constraints
def invalid_quantity_entry():
    """Generate entry with invalid quantity (<=0)."""
    return st.builds(
        dict,
        stock_symbol=valid_symbol_st,
        quantity=st.integers(max_value=0),
        price_per_share=valid_price_st,
        broker=valid_broker_st,
    )


def invalid_price_entry():
    """Generate entry with invalid price (<=0)."""
    return st.builds(
        dict,
        stock_symbol=valid_symbol_st,
        quantity=valid_quantity_st,
        price_per_share=st.decimals(
            max_value=Decimal("0"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        broker=valid_broker_st,
    )


def missing_symbol_entry():
    """Generate entry with empty stock_symbol."""
    return st.builds(
        dict,
        stock_symbol=st.just(""),
        quantity=valid_quantity_st,
        price_per_share=valid_price_st,
        broker=valid_broker_st,
    )


def missing_broker_entry():
    """Generate entry with empty/whitespace-only broker."""
    return st.builds(
        dict,
        stock_symbol=valid_symbol_st,
        quantity=valid_quantity_st,
        price_per_share=valid_price_st,
        broker=st.just(""),
    )


# An invalid entry is one of the above types
invalid_entry_st = st.one_of(
    invalid_quantity_entry(),
    invalid_price_entry(),
    missing_symbol_entry(),
    missing_broker_entry(),
)


class TestSnapshotAtomicityProperty:
    """Property 4: Snapshot Import Atomicity.

    **Validates: Requirements 2.5, 2.4, 2.6**
    """

    @given(
        entries=st.lists(valid_entry_st, min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_valid_batch_all_entries_accepted(self, entries):
        """For any batch of entirely valid entries, SnapshotCreate succeeds
        and all entries are accepted (count matches input count).

        **Validates: Requirements 2.5**
        """
        # Create the SnapshotCreate from valid entries - should not raise
        snapshot = SnapshotCreate(
            entries=[SnapshotEntry(**entry) for entry in entries]
        )

        # All entries should be present
        assert len(snapshot.entries) == len(entries)

    @given(
        entries=st.lists(valid_entry_st, min_size=1, max_size=10)
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_valid_batch_all_persisted_via_service(self, entries):
        """For any valid batch, calling import_snapshot persists ALL entries.

        **Validates: Requirements 2.5**
        """
        # Create valid SnapshotCreate
        snapshot = SnapshotCreate(
            entries=[SnapshotEntry(**entry) for entry in entries]
        )

        # Mock DB
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)
        user_id = uuid.uuid4()

        result = await service.import_snapshot(user_id, snapshot)

        # ALL entries are persisted
        assert db.add.call_count == len(entries)
        assert len(result) == len(entries)
        # flush is called exactly once (atomic commit)
        assert db.flush.call_count == 1

    @given(
        valid_entries=st.lists(valid_entry_st, min_size=0, max_size=5),
        invalid_entries=st.lists(invalid_entry_st, min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_batch_with_invalid_entries_entirely_rejected(
        self, valid_entries, invalid_entries
    ):
        """For any batch containing at least one invalid entry, the entire
        batch is rejected by Pydantic validation. Nothing reaches the service.

        **Validates: Requirements 2.4, 2.5, 2.6**
        """
        # Mix valid and invalid entries
        all_entries = valid_entries + invalid_entries

        # Attempting to create SnapshotCreate should raise ValidationError
        with pytest.raises(ValidationError):
            SnapshotCreate(
                entries=[SnapshotEntry(**entry) for entry in all_entries]
            )

    @given(
        valid_entries=st.lists(valid_entry_st, min_size=1, max_size=5),
        invalid_entries=st.lists(invalid_entry_st, min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_no_entries_persisted_when_batch_invalid(
        self, valid_entries, invalid_entries
    ):
        """When a batch has invalid entries, Pydantic rejects the entire
        SnapshotCreate at schema level — the service is never called,
        so zero entries are persisted.

        **Validates: Requirements 2.4, 2.5, 2.6**
        """
        all_entries = valid_entries + invalid_entries

        # The ValidationError prevents the service from being reached
        try:
            snapshot = SnapshotCreate(
                entries=[SnapshotEntry(**entry) for entry in all_entries]
            )
            # If somehow it passes (shouldn't), that's a test failure
            pytest.fail(
                "SnapshotCreate should have raised ValidationError for invalid entries"
            )
        except ValidationError:
            # Correct behavior: entire batch rejected, nothing persisted
            pass

    @given(
        entries=st.lists(valid_entry_st, min_size=1, max_size=10)
    )
    @settings(max_examples=50, deadline=None)
    def test_persisted_count_is_all_or_none_valid_batch(self, entries):
        """For valid batches, the count of entries that would be persisted
        equals the total input count (ALL).

        **Validates: Requirements 2.5**
        """
        snapshot = SnapshotCreate(
            entries=[SnapshotEntry(**entry) for entry in entries]
        )
        # ALL entries are accepted
        assert len(snapshot.entries) == len(entries)

    @given(
        invalid_entries=st.lists(invalid_entry_st, min_size=1, max_size=10),
    )
    @settings(max_examples=50, deadline=None)
    def test_persisted_count_is_all_or_none_invalid_batch(self, invalid_entries):
        """For invalid batches, the count of entries that would be persisted
        is NONE (zero).

        **Validates: Requirements 2.4, 2.6**
        """
        with pytest.raises(ValidationError):
            SnapshotCreate(
                entries=[SnapshotEntry(**entry) for entry in invalid_entries]
            )
        # Zero entries persisted — ValidationError prevents service call
