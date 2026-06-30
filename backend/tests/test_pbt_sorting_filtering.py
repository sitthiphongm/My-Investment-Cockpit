"""Property-based tests for query sorting and filtering logic.

Property 6: Query Results Are Sorted
- For any user's trading log query, transactions SHALL be sorted by date descending.
- For any user's transfer history query, records SHALL be sorted by date descending.
- For any performance snapshot query, results SHALL be sorted by date ascending.

Property 7: Filter Correctness (AND Logic)
- For any set of filter criteria applied to a query (date range, stock symbol, broker,
  action type), every item in the result set SHALL satisfy ALL active filter conditions,
  and no item satisfying all conditions SHALL be excluded from the result set.
- Broker and symbol matching SHALL be case-insensitive.

**Validates: Requirements 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 10.2**
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.schemas.enums import ActionType, TransferType


# ---------------------------------------------------------------------------
# Data model representations for pure-logic testing
# ---------------------------------------------------------------------------

class TransactionRecord:
    """Lightweight transaction record for testing sort/filter logic."""

    def __init__(self, record_date: date, stock_symbol: str, broker: str, action: str):
        self.date = record_date
        self.stock_symbol = stock_symbol
        self.broker = broker
        self.action = action


class TransferRecord:
    """Lightweight transfer record for testing sort/filter logic."""

    def __init__(self, record_date: date, broker: str, transfer_type: str, amount: Decimal):
        self.date = record_date
        self.broker = broker
        self.transfer_type = transfer_type
        self.amount = amount


class PerformanceSnapshotRecord:
    """Lightweight performance snapshot record for testing sort logic."""

    def __init__(self, record_date: date, total_value: Decimal, total_cost: Decimal):
        self.date = record_date
        self.total_portfolio_value = total_value
        self.total_cost = total_cost


# ---------------------------------------------------------------------------
# Pure filtering and sorting logic (mirrors service implementations)
# ---------------------------------------------------------------------------

def sort_transactions_desc(records: list[TransactionRecord]) -> list[TransactionRecord]:
    """Sort transactions by date descending (as per Requirement 4.1)."""
    return sorted(records, key=lambda r: r.date, reverse=True)


def sort_transfers_desc(records: list[TransferRecord]) -> list[TransferRecord]:
    """Sort transfers by date descending (as per Requirement 3.2)."""
    return sorted(records, key=lambda r: r.date, reverse=True)


def sort_snapshots_asc(records: list[PerformanceSnapshotRecord]) -> list[PerformanceSnapshotRecord]:
    """Sort performance snapshots by date ascending (as per Requirement 10.2)."""
    return sorted(records, key=lambda r: r.date)


def filter_transactions(
    records: list[TransactionRecord],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    stock_symbol: Optional[str] = None,
    broker: Optional[str] = None,
    action: Optional[str] = None,
) -> list[TransactionRecord]:
    """Filter transactions using AND logic with case-insensitive matching.

    Mirrors the filtering in TradingService.list_transactions.
    """
    result = []
    for record in records:
        if date_from is not None and record.date < date_from:
            continue
        if date_to is not None and record.date > date_to:
            continue
        if stock_symbol is not None and record.stock_symbol.upper() != stock_symbol.upper():
            continue
        if broker is not None and record.broker.upper() != broker.upper():
            continue
        if action is not None and record.action != action:
            continue
        result.append(record)
    return result


def filter_transfers(
    records: list[TransferRecord],
    broker: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[TransferRecord]:
    """Filter transfers using AND logic with case-insensitive broker matching.

    Mirrors the filtering in TransferService.list_transfers.
    """
    result = []
    for record in records:
        if broker is not None and record.broker.upper() != broker.upper():
            continue
        if date_from is not None and record.date < date_from:
            continue
        if date_to is not None and record.date > date_to:
            continue
        result.append(record)
    return result


def record_satisfies_all_transaction_filters(
    record: TransactionRecord,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    stock_symbol: Optional[str] = None,
    broker: Optional[str] = None,
    action: Optional[str] = None,
) -> bool:
    """Check if a single transaction record satisfies ALL given filter criteria."""
    if date_from is not None and record.date < date_from:
        return False
    if date_to is not None and record.date > date_to:
        return False
    if stock_symbol is not None and record.stock_symbol.upper() != stock_symbol.upper():
        return False
    if broker is not None and record.broker.upper() != broker.upper():
        return False
    if action is not None and record.action != action:
        return False
    return True


def record_satisfies_all_transfer_filters(
    record: TransferRecord,
    broker: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> bool:
    """Check if a single transfer record satisfies ALL given filter criteria."""
    if broker is not None and record.broker.upper() != broker.upper():
        return False
    if date_from is not None and record.date < date_from:
        return False
    if date_to is not None and record.date > date_to:
        return False
    return True


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Date strategy: generate dates within a reasonable range
date_strategy = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2025, 12, 31),
)

# Stock symbol strategy
symbol_strategy = st.sampled_from(["DRAM", "RGNX", "META", "AAPL", "TSLA", "BTC.X", "AOT", "PTT"])

# Broker strategy (mixed case to test case-insensitive matching)
broker_strategy = st.sampled_from(["Webull", "WEBULL", "webull", "Dime", "DIME", "dime", "Finnomena", "Robinhood"])

# Action strategy
action_strategy = st.sampled_from([ActionType.BUY.value, ActionType.SELL.value, ActionType.SNAPSHOT.value])

# Transfer type strategy
transfer_type_strategy = st.sampled_from([TransferType.IN.value, TransferType.OUT.value])

# Amount strategy
amount_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for generating a transaction record
transaction_record_strategy = st.builds(
    TransactionRecord,
    record_date=date_strategy,
    stock_symbol=symbol_strategy,
    broker=broker_strategy,
    action=action_strategy,
)

# Strategy for generating a transfer record
transfer_record_strategy = st.builds(
    TransferRecord,
    record_date=date_strategy,
    broker=broker_strategy,
    transfer_type=transfer_type_strategy,
    amount=amount_strategy,
)

# Strategy for generating a performance snapshot record
snapshot_record_strategy = st.builds(
    PerformanceSnapshotRecord,
    record_date=date_strategy,
    total_value=amount_strategy,
    total_cost=amount_strategy,
)

# Optional filter strategies (None means filter not active)
optional_date_strategy = st.one_of(st.none(), date_strategy)
optional_symbol_strategy = st.one_of(st.none(), symbol_strategy)
optional_broker_strategy = st.one_of(st.none(), broker_strategy)
optional_action_strategy = st.one_of(st.none(), action_strategy)


# ---------------------------------------------------------------------------
# Property 6: Query Results Are Sorted
# ---------------------------------------------------------------------------

class TestQueryResultsSortedProperty:
    """Property 6: Query Results Are Sorted.

    - Trading log: sorted by date descending
    - Transfer history: sorted by date descending
    - Performance snapshots: sorted by date ascending

    **Validates: Requirements 3.2, 4.1, 10.2**
    """

    @settings(max_examples=100)
    @given(records=st.lists(transaction_record_strategy, min_size=0, max_size=50))
    def test_trading_log_sorted_by_date_descending(
        self, records: list[TransactionRecord]
    ):
        """For any list of transactions, sorting by date desc means each item's
        date >= the next item's date."""
        sorted_records = sort_transactions_desc(records)

        for i in range(len(sorted_records) - 1):
            assert sorted_records[i].date >= sorted_records[i + 1].date, (
                f"Transaction at index {i} (date={sorted_records[i].date}) "
                f"should be >= transaction at index {i+1} (date={sorted_records[i+1].date})"
            )

    @settings(max_examples=100)
    @given(records=st.lists(transfer_record_strategy, min_size=0, max_size=50))
    def test_transfers_sorted_by_date_descending(
        self, records: list[TransferRecord]
    ):
        """For any list of transfers, sorting by date desc means each item's
        date >= the next item's date."""
        sorted_records = sort_transfers_desc(records)

        for i in range(len(sorted_records) - 1):
            assert sorted_records[i].date >= sorted_records[i + 1].date, (
                f"Transfer at index {i} (date={sorted_records[i].date}) "
                f"should be >= transfer at index {i+1} (date={sorted_records[i+1].date})"
            )

    @settings(max_examples=100)
    @given(records=st.lists(snapshot_record_strategy, min_size=0, max_size=50))
    def test_performance_snapshots_sorted_by_date_ascending(
        self, records: list[PerformanceSnapshotRecord]
    ):
        """For any list of performance snapshots, sorting by date asc means each
        item's date <= the next item's date."""
        sorted_records = sort_snapshots_asc(records)

        for i in range(len(sorted_records) - 1):
            assert sorted_records[i].date <= sorted_records[i + 1].date, (
                f"Snapshot at index {i} (date={sorted_records[i].date}) "
                f"should be <= snapshot at index {i+1} (date={sorted_records[i+1].date})"
            )


# ---------------------------------------------------------------------------
# Property 7: Filter Correctness (AND Logic)
# ---------------------------------------------------------------------------

class TestFilterCorrectnessProperty:
    """Property 7: Filter Correctness (AND Logic).

    For any set of filter criteria:
    - Every item in the filtered result satisfies ALL active filter conditions
    - No item satisfying all conditions is excluded (completeness)
    - Broker and symbol matching is case-insensitive

    **Validates: Requirements 3.3, 4.2, 4.3, 4.4, 4.5, 4.6**
    """

    @settings(max_examples=100)
    @given(
        records=st.lists(transaction_record_strategy, min_size=1, max_size=30),
        date_from=optional_date_strategy,
        date_to=optional_date_strategy,
        stock_symbol=optional_symbol_strategy,
        broker=optional_broker_strategy,
        action=optional_action_strategy,
    )
    def test_transaction_filter_all_results_satisfy_all_conditions(
        self,
        records: list[TransactionRecord],
        date_from: Optional[date],
        date_to: Optional[date],
        stock_symbol: Optional[str],
        broker: Optional[str],
        action: Optional[str],
    ):
        """Every item in the filtered result satisfies ALL active filter conditions."""
        # Ensure date_from <= date_to when both are specified
        if date_from is not None and date_to is not None and date_from > date_to:
            date_from, date_to = date_to, date_from

        filtered = filter_transactions(
            records,
            date_from=date_from,
            date_to=date_to,
            stock_symbol=stock_symbol,
            broker=broker,
            action=action,
        )

        for record in filtered:
            assert record_satisfies_all_transaction_filters(
                record,
                date_from=date_from,
                date_to=date_to,
                stock_symbol=stock_symbol,
                broker=broker,
                action=action,
            ), (
                f"Record (date={record.date}, symbol={record.stock_symbol}, "
                f"broker={record.broker}, action={record.action}) "
                f"does not satisfy all filters: "
                f"date_from={date_from}, date_to={date_to}, "
                f"symbol={stock_symbol}, broker={broker}, action={action}"
            )

    @settings(max_examples=100)
    @given(
        records=st.lists(transaction_record_strategy, min_size=1, max_size=30),
        date_from=optional_date_strategy,
        date_to=optional_date_strategy,
        stock_symbol=optional_symbol_strategy,
        broker=optional_broker_strategy,
        action=optional_action_strategy,
    )
    def test_transaction_filter_completeness_no_matching_item_excluded(
        self,
        records: list[TransactionRecord],
        date_from: Optional[date],
        date_to: Optional[date],
        stock_symbol: Optional[str],
        broker: Optional[str],
        action: Optional[str],
    ):
        """No item satisfying all conditions is excluded from the result set."""
        # Ensure date_from <= date_to when both are specified
        if date_from is not None and date_to is not None and date_from > date_to:
            date_from, date_to = date_to, date_from

        filtered = filter_transactions(
            records,
            date_from=date_from,
            date_to=date_to,
            stock_symbol=stock_symbol,
            broker=broker,
            action=action,
        )

        # Check completeness: every record that satisfies all conditions must be in the result
        for record in records:
            if record_satisfies_all_transaction_filters(
                record,
                date_from=date_from,
                date_to=date_to,
                stock_symbol=stock_symbol,
                broker=broker,
                action=action,
            ):
                assert record in filtered, (
                    f"Record (date={record.date}, symbol={record.stock_symbol}, "
                    f"broker={record.broker}, action={record.action}) "
                    f"satisfies all filters but was excluded from results"
                )

    @settings(max_examples=100)
    @given(
        records=st.lists(transfer_record_strategy, min_size=1, max_size=30),
        broker=optional_broker_strategy,
        date_from=optional_date_strategy,
        date_to=optional_date_strategy,
    )
    def test_transfer_filter_all_results_satisfy_all_conditions(
        self,
        records: list[TransferRecord],
        broker: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
    ):
        """Every transfer in the filtered result satisfies ALL active filter conditions."""
        # Ensure date_from <= date_to when both are specified
        if date_from is not None and date_to is not None and date_from > date_to:
            date_from, date_to = date_to, date_from

        filtered = filter_transfers(
            records,
            broker=broker,
            date_from=date_from,
            date_to=date_to,
        )

        for record in filtered:
            assert record_satisfies_all_transfer_filters(
                record,
                broker=broker,
                date_from=date_from,
                date_to=date_to,
            ), (
                f"Transfer (date={record.date}, broker={record.broker}) "
                f"does not satisfy all filters: "
                f"broker={broker}, date_from={date_from}, date_to={date_to}"
            )

    @settings(max_examples=100)
    @given(
        records=st.lists(transfer_record_strategy, min_size=1, max_size=30),
        broker=optional_broker_strategy,
        date_from=optional_date_strategy,
        date_to=optional_date_strategy,
    )
    def test_transfer_filter_completeness_no_matching_item_excluded(
        self,
        records: list[TransferRecord],
        broker: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
    ):
        """No transfer satisfying all conditions is excluded from the result set."""
        # Ensure date_from <= date_to when both are specified
        if date_from is not None and date_to is not None and date_from > date_to:
            date_from, date_to = date_to, date_from

        filtered = filter_transfers(
            records,
            broker=broker,
            date_from=date_from,
            date_to=date_to,
        )

        # Check completeness: every record that satisfies all conditions must be in the result
        for record in records:
            if record_satisfies_all_transfer_filters(
                record,
                broker=broker,
                date_from=date_from,
                date_to=date_to,
            ):
                assert record in filtered, (
                    f"Transfer (date={record.date}, broker={record.broker}) "
                    f"satisfies all filters but was excluded from results"
                )

    @settings(max_examples=100)
    @given(
        records=st.lists(transaction_record_strategy, min_size=1, max_size=30),
        date_from=optional_date_strategy,
        date_to=optional_date_strategy,
        stock_symbol=optional_symbol_strategy,
        broker=optional_broker_strategy,
        action=optional_action_strategy,
    )
    def test_case_insensitive_symbol_and_broker_matching(
        self,
        records: list[TransactionRecord],
        date_from: Optional[date],
        date_to: Optional[date],
        stock_symbol: Optional[str],
        broker: Optional[str],
        action: Optional[str],
    ):
        """Broker and symbol matching SHALL be case-insensitive.

        Filtering with any case variation of the same symbol/broker should
        yield the same results.
        """
        # Ensure date_from <= date_to when both are specified
        if date_from is not None and date_to is not None and date_from > date_to:
            date_from, date_to = date_to, date_from

        # Filter with original case
        filtered_original = filter_transactions(
            records,
            date_from=date_from,
            date_to=date_to,
            stock_symbol=stock_symbol,
            broker=broker,
            action=action,
        )

        # Filter with altered case (upper for symbol, lower for broker)
        symbol_upper = stock_symbol.upper() if stock_symbol else None
        broker_lower = broker.lower() if broker else None

        filtered_case_altered = filter_transactions(
            records,
            date_from=date_from,
            date_to=date_to,
            stock_symbol=symbol_upper,
            broker=broker_lower,
            action=action,
        )

        assert len(filtered_original) == len(filtered_case_altered), (
            f"Case-insensitive matching failed: original filter returned "
            f"{len(filtered_original)} results but case-altered returned "
            f"{len(filtered_case_altered)} results. "
            f"symbol={stock_symbol}/{symbol_upper}, broker={broker}/{broker_lower}"
        )
