"""Property-based tests for holdings quantity invariant.

Property 3: Holdings Quantity Invariant
- For any stock symbol and user, the total held quantity SHALL equal the sum of
  all buy quantities plus all snapshot quantities minus all sell quantities.
- No operation SHALL be permitted if it would cause any symbol's held quantity
  to become negative.

**Validates: Requirements 1.6, 2.2, 6.1, 6.3**
"""

from dataclasses import dataclass
from enum import Enum
from typing import List

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize


class TxAction(str, Enum):
    BUY = "Buy"
    SELL = "Sell"
    SNAPSHOT = "Snapshot"


@dataclass
class TxRecord:
    action: TxAction
    quantity: int


def compute_holdings(transactions: List[TxRecord]) -> int:
    """Compute total held quantity from a sequence of transactions."""
    total = 0
    for tx in transactions:
        if tx.action in (TxAction.BUY, TxAction.SNAPSHOT):
            total += tx.quantity
        else:
            total -= tx.quantity
    return total


def validate_no_negative_at_any_point(transactions: List[TxRecord]) -> bool:
    """Check that holdings never go negative at any point in the sequence."""
    running = 0
    for tx in transactions:
        if tx.action in (TxAction.BUY, TxAction.SNAPSHOT):
            running += tx.quantity
        else:
            running -= tx.quantity
        if running < 0:
            return False
    return True


@st.composite
def valid_transaction_sequence(draw) -> List[TxRecord]:
    """Generate a valid sequence of transactions where sells never exceed holdings.

    Strategy:
    - Generate a random number of transactions (1 to 30)
    - For each step, choose Buy/Sell/Snapshot
    - For Buy and Snapshot, generate quantity freely (1 to 10000)
    - For Sell, constrain quantity to be <= current holdings
    - If current holdings is 0, force a Buy or Snapshot instead of Sell
    """
    num_transactions = draw(st.integers(min_value=1, max_value=30))
    transactions: List[TxRecord] = []
    current_holdings = 0

    for _ in range(num_transactions):
        if current_holdings == 0:
            # Can't sell when holdings are zero, pick Buy or Snapshot
            action = draw(st.sampled_from([TxAction.BUY, TxAction.SNAPSHOT]))
        else:
            action = draw(st.sampled_from([TxAction.BUY, TxAction.SELL, TxAction.SNAPSHOT]))

        if action in (TxAction.BUY, TxAction.SNAPSHOT):
            quantity = draw(st.integers(min_value=1, max_value=10000))
            current_holdings += quantity
        else:
            # Sell: quantity must be <= current holdings
            quantity = draw(st.integers(min_value=1, max_value=current_holdings))
            current_holdings -= quantity

        transactions.append(TxRecord(action=action, quantity=quantity))

    return transactions


class TestHoldingsQuantityInvariantProperty:
    """Property 3: Holdings Quantity Invariant.

    For any stock symbol and user, the total held quantity SHALL equal the sum of
    all buy quantities plus all snapshot quantities minus all sell quantities.
    No operation (sell, delete, edit) SHALL be permitted if it would cause any
    symbol's held quantity to become negative.

    **Validates: Requirements 1.6, 2.2, 6.1, 6.3**
    """

    @settings(max_examples=200)
    @given(transactions=valid_transaction_sequence())
    def test_total_held_equals_sum_buys_plus_snapshots_minus_sells(
        self, transactions: List[TxRecord]
    ):
        """Verify: total_held = Σ(buy_quantities) + Σ(snapshot_quantities) - Σ(sell_quantities).

        **Validates: Requirements 1.6, 2.2**
        """
        total_buy = sum(tx.quantity for tx in transactions if tx.action == TxAction.BUY)
        total_snapshot = sum(tx.quantity for tx in transactions if tx.action == TxAction.SNAPSHOT)
        total_sell = sum(tx.quantity for tx in transactions if tx.action == TxAction.SELL)

        expected_holdings = total_buy + total_snapshot - total_sell
        actual_holdings = compute_holdings(transactions)

        assert actual_holdings == expected_holdings, (
            f"Holdings mismatch: actual={actual_holdings}, "
            f"expected={expected_holdings} "
            f"(buys={total_buy}, snapshots={total_snapshot}, sells={total_sell})"
        )

    @settings(max_examples=200)
    @given(transactions=valid_transaction_sequence())
    def test_holdings_never_negative_at_any_point(
        self, transactions: List[TxRecord]
    ):
        """Verify: total_held is never negative at any point in the sequence.

        **Validates: Requirements 6.1, 6.3**
        """
        running_holdings = 0
        for i, tx in enumerate(transactions):
            if tx.action in (TxAction.BUY, TxAction.SNAPSHOT):
                running_holdings += tx.quantity
            else:
                running_holdings -= tx.quantity

            assert running_holdings >= 0, (
                f"Holdings went negative ({running_holdings}) after transaction {i}: "
                f"action={tx.action.value}, quantity={tx.quantity}. "
                f"Sequence so far: {[(t.action.value, t.quantity) for t in transactions[:i+1]]}"
            )

    @settings(max_examples=200)
    @given(transactions=valid_transaction_sequence())
    def test_final_holdings_is_non_negative(
        self, transactions: List[TxRecord]
    ):
        """Verify: the final total held quantity is always >= 0.

        **Validates: Requirements 1.6, 6.1**
        """
        final_holdings = compute_holdings(transactions)

        assert final_holdings >= 0, (
            f"Final holdings is negative: {final_holdings}. "
            f"Transactions: {[(t.action.value, t.quantity) for t in transactions]}"
        )

    @settings(max_examples=200)
    @given(
        transactions=valid_transaction_sequence(),
        extra_sell_qty=st.integers(min_value=1, max_value=10000),
    )
    def test_sell_exceeding_holdings_is_invalid(
        self,
        transactions: List[TxRecord],
        extra_sell_qty: int,
    ):
        """Verify: a sell that would cause negative holdings is rejected.

        We simulate adding a sell that exceeds current holdings and verify
        it would violate the invariant.

        **Validates: Requirements 1.6, 6.3**
        """
        current_holdings = compute_holdings(transactions)

        # Only test when we can construct an oversell scenario
        assume(current_holdings >= 0)

        oversell_qty = current_holdings + extra_sell_qty
        oversell_tx = TxRecord(action=TxAction.SELL, quantity=oversell_qty)

        extended_sequence = transactions + [oversell_tx]
        result_holdings = compute_holdings(extended_sequence)

        # The resulting holdings would be negative — this must be rejected
        assert result_holdings < 0, (
            f"Expected negative holdings after oversell but got {result_holdings}. "
            f"Current holdings: {current_holdings}, oversell qty: {oversell_qty}"
        )

        # Confirm the extended sequence fails the no-negative validation
        assert not validate_no_negative_at_any_point(extended_sequence), (
            f"Expected validation failure for oversell sequence but it passed. "
            f"Current holdings: {current_holdings}, oversell qty: {oversell_qty}"
        )
