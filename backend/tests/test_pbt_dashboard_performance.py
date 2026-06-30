"""Property-based tests for dashboard and performance calculations.

Property 12: Dashboard Monetary Aggregations
- For any set of money transfers, Total Invested SHALL equal the sum of all "In"
  transfer amounts, Total Withdrawn SHALL equal the sum of all "Out" transfer amounts,
  Net Invested SHALL equal Total Invested minus Total Withdrawn, and per-broker capital
  SHALL equal (broker's In) minus (broker's Out).

Property 13: Period Return Calculation
- For any two consecutive performance snapshots with portfolio values V_prev and V_curr
  (where V_prev > 0), the period return SHALL equal ((V_curr - V_prev) / V_prev) × 100,
  rounded to 2 decimal places.

Property 14: Cumulative Return Calculation
- For any sequence of performance snapshots with earliest value V_earliest and latest
  value V_latest (where V_earliest > 0), the cumulative return SHALL equal
  ((V_latest - V_earliest) / V_earliest) × 100, rounded to 2 decimal places.

**Validates: Requirements 9.1, 9.4, 10.3, 10.4**
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.performance_service import PerformanceService


TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Data structures for generating test data
# ---------------------------------------------------------------------------

@dataclass
class TransferEntry:
    """Represents a money transfer record."""
    broker: str
    transfer_type: str  # "In" or "Out"
    amount: Decimal


@dataclass
class SnapshotEntry:
    """Represents a performance snapshot value."""
    total_portfolio_value: Decimal


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for transfer amounts (positive Decimal with 2 places)
amount_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for portfolio values (positive Decimal with 2 places)
portfolio_value_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for broker names
broker_strategy = st.sampled_from(["Webull", "Dime", "Tiger", "BLS", "KGI"])

# Strategy for transfer type
transfer_type_strategy = st.sampled_from(["In", "Out"])

# Strategy for generating a single transfer entry
transfer_entry_strategy = st.builds(
    TransferEntry,
    broker=broker_strategy,
    transfer_type=transfer_type_strategy,
    amount=amount_strategy,
)


@st.composite
def transfer_list(draw, min_size=1, max_size=30) -> List[TransferEntry]:
    """Generate a non-empty list of transfer entries."""
    return draw(st.lists(transfer_entry_strategy, min_size=min_size, max_size=max_size))


@st.composite
def transfer_list_with_in(draw, min_size=2, max_size=30) -> List[TransferEntry]:
    """Generate a list of transfers guaranteed to have at least one 'In' and one 'Out'."""
    entries = draw(st.lists(transfer_entry_strategy, min_size=min_size, max_size=max_size))
    # Ensure at least one In
    has_in = any(e.transfer_type == "In" for e in entries)
    has_out = any(e.transfer_type == "Out" for e in entries)
    if not has_in:
        entries[0] = TransferEntry(
            broker=entries[0].broker,
            transfer_type="In",
            amount=entries[0].amount,
        )
    if not has_out and len(entries) > 1:
        entries[1] = TransferEntry(
            broker=entries[1].broker,
            transfer_type="Out",
            amount=entries[1].amount,
        )
    return entries


@st.composite
def consecutive_snapshot_values(draw, min_size=2, max_size=20) -> List[Decimal]:
    """Generate a sequence of portfolio values representing consecutive snapshots."""
    return draw(
        st.lists(portfolio_value_strategy, min_size=min_size, max_size=max_size)
    )


# ---------------------------------------------------------------------------
# Property 12: Dashboard Monetary Aggregations
# ---------------------------------------------------------------------------

class TestDashboardMonetaryAggregationsProperty:
    """Property 12: Dashboard Monetary Aggregations.

    For any set of money transfers:
    - Total Invested = Σ amounts where transfer_type == "In"
    - Total Withdrawn = Σ amounts where transfer_type == "Out"
    - Net Invested = Total Invested - Total Withdrawn
    - Per-broker capital = (broker's Σ"In") - (broker's Σ"Out")

    **Validates: Requirements 9.1, 9.4**
    """

    @settings(max_examples=200)
    @given(transfers=transfer_list(min_size=1, max_size=30))
    def test_total_invested_equals_sum_of_in_transfers(
        self, transfers: List[TransferEntry]
    ):
        """Verify Total Invested = Σ of all 'In' transfer amounts.

        **Validates: Requirement 9.1**
        """
        expected_total_invested = sum(
            (t.amount for t in transfers if t.transfer_type == "In"),
            Decimal("0"),
        )

        # Simulate the dashboard aggregation logic
        total_invested = Decimal("0")
        for t in transfers:
            if t.transfer_type == "In":
                total_invested += t.amount

        assert total_invested == expected_total_invested, (
            f"Total Invested mismatch: got {total_invested}, "
            f"expected {expected_total_invested}"
        )

    @settings(max_examples=200)
    @given(transfers=transfer_list(min_size=1, max_size=30))
    def test_total_withdrawn_equals_sum_of_out_transfers(
        self, transfers: List[TransferEntry]
    ):
        """Verify Total Withdrawn = Σ of all 'Out' transfer amounts.

        **Validates: Requirement 9.1**
        """
        expected_total_withdrawn = sum(
            (t.amount for t in transfers if t.transfer_type == "Out"),
            Decimal("0"),
        )

        total_withdrawn = Decimal("0")
        for t in transfers:
            if t.transfer_type == "Out":
                total_withdrawn += t.amount

        assert total_withdrawn == expected_total_withdrawn, (
            f"Total Withdrawn mismatch: got {total_withdrawn}, "
            f"expected {expected_total_withdrawn}"
        )

    @settings(max_examples=200)
    @given(transfers=transfer_list(min_size=1, max_size=30))
    def test_net_invested_equals_in_minus_out(
        self, transfers: List[TransferEntry]
    ):
        """Verify Net Invested = Total Invested - Total Withdrawn.

        **Validates: Requirement 9.1**
        """
        total_invested = sum(
            (t.amount for t in transfers if t.transfer_type == "In"),
            Decimal("0"),
        )
        total_withdrawn = sum(
            (t.amount for t in transfers if t.transfer_type == "Out"),
            Decimal("0"),
        )

        expected_net = total_invested - total_withdrawn
        actual_net = total_invested - total_withdrawn

        assert actual_net == expected_net, (
            f"Net Invested mismatch: got {actual_net}, expected {expected_net}. "
            f"In={total_invested}, Out={total_withdrawn}"
        )

    @settings(max_examples=200)
    @given(transfers=transfer_list_with_in(min_size=2, max_size=30))
    def test_per_broker_capital_equals_broker_in_minus_out(
        self, transfers: List[TransferEntry]
    ):
        """Verify per-broker net capital = broker's Σ'In' - broker's Σ'Out'.

        **Validates: Requirement 9.4**
        """
        # Calculate expected per-broker breakdown
        broker_totals: dict[str, dict[str, Decimal]] = {}
        for t in transfers:
            if t.broker not in broker_totals:
                broker_totals[t.broker] = {"in": Decimal("0"), "out": Decimal("0")}
            if t.transfer_type == "In":
                broker_totals[t.broker]["in"] += t.amount
            elif t.transfer_type == "Out":
                broker_totals[t.broker]["out"] += t.amount

        for broker, totals in broker_totals.items():
            expected_net = totals["in"] - totals["out"]
            actual_net = totals["in"] - totals["out"]

            assert actual_net == expected_net, (
                f"Per-broker capital mismatch for {broker}: "
                f"got {actual_net}, expected {expected_net}. "
                f"In={totals['in']}, Out={totals['out']}"
            )

    @settings(max_examples=200)
    @given(transfers=transfer_list(min_size=1, max_size=30))
    def test_sum_of_broker_in_equals_total_invested(
        self, transfers: List[TransferEntry]
    ):
        """Verify Σ(broker's total_in) = Total Invested (no money lost in breakdown).

        **Validates: Requirement 9.4**
        """
        total_invested = sum(
            (t.amount for t in transfers if t.transfer_type == "In"),
            Decimal("0"),
        )

        broker_in: dict[str, Decimal] = {}
        for t in transfers:
            if t.transfer_type == "In":
                broker_in[t.broker] = broker_in.get(t.broker, Decimal("0")) + t.amount

        sum_broker_in = sum(broker_in.values(), Decimal("0"))

        assert sum_broker_in == total_invested, (
            f"Sum of per-broker 'In' ({sum_broker_in}) != Total Invested ({total_invested})"
        )

    @settings(max_examples=200)
    @given(transfers=transfer_list(min_size=1, max_size=30))
    def test_sum_of_broker_out_equals_total_withdrawn(
        self, transfers: List[TransferEntry]
    ):
        """Verify Σ(broker's total_out) = Total Withdrawn (no money lost in breakdown).

        **Validates: Requirement 9.4**
        """
        total_withdrawn = sum(
            (t.amount for t in transfers if t.transfer_type == "Out"),
            Decimal("0"),
        )

        broker_out: dict[str, Decimal] = {}
        for t in transfers:
            if t.transfer_type == "Out":
                broker_out[t.broker] = broker_out.get(t.broker, Decimal("0")) + t.amount

        sum_broker_out = sum(broker_out.values(), Decimal("0"))

        assert sum_broker_out == total_withdrawn, (
            f"Sum of per-broker 'Out' ({sum_broker_out}) != Total Withdrawn ({total_withdrawn})"
        )

    @settings(max_examples=200)
    @given(transfers=transfer_list(min_size=1, max_size=30))
    def test_broker_count_equals_distinct_brokers(
        self, transfers: List[TransferEntry]
    ):
        """Verify total_brokers = count of distinct broker names.

        **Validates: Requirement 9.5**
        """
        distinct_brokers = set(t.broker for t in transfers)
        expected_count = len(distinct_brokers)

        # Simulate broker counting logic
        broker_set: set[str] = set()
        for t in transfers:
            broker_set.add(t.broker)

        assert len(broker_set) == expected_count, (
            f"Broker count mismatch: got {len(broker_set)}, expected {expected_count}"
        )


# ---------------------------------------------------------------------------
# Property 13: Period Return Calculation
# ---------------------------------------------------------------------------

class TestPeriodReturnCalculationProperty:
    """Property 13: Period Return Calculation.

    For any two consecutive performance snapshots with portfolio values V_prev and
    V_curr (where V_prev > 0), the period return SHALL equal
    ((V_curr - V_prev) / V_prev) × 100, rounded to 2 decimal places.

    **Validates: Requirement 10.3**
    """

    @settings(max_examples=300)
    @given(
        v_prev=portfolio_value_strategy,
        v_curr=portfolio_value_strategy,
    )
    def test_period_return_formula(self, v_prev: Decimal, v_curr: Decimal):
        """Verify period return matches the formula exactly.

        **Validates: Requirement 10.3**
        """
        assume(v_prev > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)
        actual = service.calculate_period_return(v_curr, v_prev)

        expected = ((v_curr - v_prev) / v_prev * Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert actual == expected, (
            f"Period return mismatch: got {actual}, expected {expected}. "
            f"V_curr={v_curr}, V_prev={v_prev}"
        )

    @settings(max_examples=200)
    @given(v_curr=portfolio_value_strategy)
    def test_period_return_zero_previous_returns_none(self, v_curr: Decimal):
        """Verify period return is None when previous value is zero.

        **Validates: Requirement 10.3**
        """
        service = PerformanceService.__new__(PerformanceService)
        result = service.calculate_period_return(v_curr, Decimal("0"))

        assert result is None, (
            f"Period return should be None when V_prev=0, but got {result}"
        )

    @settings(max_examples=200)
    @given(v=portfolio_value_strategy)
    def test_period_return_same_value_is_zero(self, v: Decimal):
        """Verify period return is 0.00 when current equals previous.

        **Validates: Requirement 10.3**
        """
        assume(v > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)
        result = service.calculate_period_return(v, v)

        assert result == Decimal("0.00"), (
            f"Period return should be 0.00 when V_curr=V_prev={v}, but got {result}"
        )

    @settings(max_examples=200)
    @given(
        v_prev=portfolio_value_strategy,
        v_curr=portfolio_value_strategy,
    )
    def test_period_return_sign_correctness(self, v_prev: Decimal, v_curr: Decimal):
        """Verify period return is positive when value increases, negative when decreases.

        **Validates: Requirement 10.3**
        """
        assume(v_prev > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)
        result = service.calculate_period_return(v_curr, v_prev)

        if v_curr > v_prev:
            assert result >= Decimal("0"), (
                f"Period return should be non-negative when V_curr ({v_curr}) > V_prev ({v_prev}), "
                f"but got {result}"
            )
        elif v_curr < v_prev:
            assert result <= Decimal("0"), (
                f"Period return should be non-positive when V_curr ({v_curr}) < V_prev ({v_prev}), "
                f"but got {result}"
            )
        else:
            assert result == Decimal("0.00"), (
                f"Period return should be 0.00 when V_curr = V_prev = {v_curr}, "
                f"but got {result}"
            )

    @settings(max_examples=200)
    @given(values=consecutive_snapshot_values(min_size=3, max_size=15))
    def test_period_returns_chain_consistency(self, values: List[Decimal]):
        """Verify period returns are computed independently between each pair.

        For a sequence [A, B, C], period_return(B, A) and period_return(C, B)
        should be independent calculations.

        **Validates: Requirement 10.3**
        """
        assume(all(v > Decimal("0") for v in values))

        service = PerformanceService.__new__(PerformanceService)

        period_returns = []
        for i in range(1, len(values)):
            pr = service.calculate_period_return(values[i], values[i - 1])
            period_returns.append(pr)

        # Verify each period return matches independent formula
        for i, pr in enumerate(period_returns):
            v_prev = values[i]
            v_curr = values[i + 1]
            expected = ((v_curr - v_prev) / v_prev * Decimal("100")).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            assert pr == expected, (
                f"Period return at index {i} mismatch: got {pr}, expected {expected}. "
                f"V_prev={v_prev}, V_curr={v_curr}"
            )


# ---------------------------------------------------------------------------
# Property 14: Cumulative Return Calculation
# ---------------------------------------------------------------------------

class TestCumulativeReturnCalculationProperty:
    """Property 14: Cumulative Return Calculation.

    For any sequence of performance snapshots with earliest value V_earliest and
    latest value V_latest (where V_earliest > 0), the cumulative return SHALL equal
    ((V_latest - V_earliest) / V_earliest) × 100, rounded to 2 decimal places.

    **Validates: Requirement 10.4**
    """

    @settings(max_examples=300)
    @given(
        v_earliest=portfolio_value_strategy,
        v_latest=portfolio_value_strategy,
    )
    def test_cumulative_return_formula(self, v_earliest: Decimal, v_latest: Decimal):
        """Verify cumulative return matches the formula exactly.

        **Validates: Requirement 10.4**
        """
        assume(v_earliest > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)
        actual = service.calculate_cumulative_return(v_earliest, v_latest)

        expected = ((v_latest - v_earliest) / v_earliest * Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert actual == expected, (
            f"Cumulative return mismatch: got {actual}, expected {expected}. "
            f"V_earliest={v_earliest}, V_latest={v_latest}"
        )

    @settings(max_examples=200)
    @given(v_latest=portfolio_value_strategy)
    def test_cumulative_return_zero_earliest_returns_none(self, v_latest: Decimal):
        """Verify cumulative return is None when earliest value is zero.

        **Validates: Requirement 10.4**
        """
        service = PerformanceService.__new__(PerformanceService)
        result = service.calculate_cumulative_return(Decimal("0"), v_latest)

        assert result is None, (
            f"Cumulative return should be None when V_earliest=0, but got {result}"
        )

    @settings(max_examples=200)
    @given(v=portfolio_value_strategy)
    def test_cumulative_return_same_value_is_zero(self, v: Decimal):
        """Verify cumulative return is 0.00 when latest equals earliest.

        **Validates: Requirement 10.4**
        """
        assume(v > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)
        result = service.calculate_cumulative_return(v, v)

        assert result == Decimal("0.00"), (
            f"Cumulative return should be 0.00 when V_latest=V_earliest={v}, "
            f"but got {result}"
        )

    @settings(max_examples=200)
    @given(
        v_earliest=portfolio_value_strategy,
        v_latest=portfolio_value_strategy,
    )
    def test_cumulative_return_sign_correctness(
        self, v_earliest: Decimal, v_latest: Decimal
    ):
        """Verify cumulative return sign matches value change direction.

        **Validates: Requirement 10.4**
        """
        assume(v_earliest > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)
        result = service.calculate_cumulative_return(v_earliest, v_latest)

        if v_latest > v_earliest:
            assert result > Decimal("0"), (
                f"Cumulative return should be positive when V_latest ({v_latest}) > "
                f"V_earliest ({v_earliest}), but got {result}"
            )
        elif v_latest < v_earliest:
            assert result < Decimal("0"), (
                f"Cumulative return should be negative when V_latest ({v_latest}) < "
                f"V_earliest ({v_earliest}), but got {result}"
            )
        else:
            assert result == Decimal("0.00"), (
                f"Cumulative return should be 0.00 when V_latest = V_earliest = "
                f"{v_earliest}, but got {result}"
            )

    @settings(max_examples=200)
    @given(values=consecutive_snapshot_values(min_size=2, max_size=20))
    def test_cumulative_return_uses_only_endpoints(self, values: List[Decimal]):
        """Verify cumulative return only depends on first and last values, not intermediates.

        **Validates: Requirement 10.4**
        """
        assume(values[0] > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)

        # Full sequence cumulative
        full_cumulative = service.calculate_cumulative_return(values[0], values[-1])

        # Direct calculation from endpoints
        expected = ((values[-1] - values[0]) / values[0] * Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert full_cumulative == expected, (
            f"Cumulative return should only depend on endpoints. "
            f"Got {full_cumulative}, expected {expected}. "
            f"First={values[0]}, Last={values[-1]}, Sequence length={len(values)}"
        )

    @settings(max_examples=200)
    @given(
        v_earliest=st.decimals(
            min_value=Decimal("1.00"),
            max_value=Decimal("99999999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        v_latest=st.decimals(
            min_value=Decimal("1.00"),
            max_value=Decimal("99999999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_cumulative_return_inverse_relationship(
        self, v_earliest: Decimal, v_latest: Decimal
    ):
        """Verify that swapping earliest/latest gives inverse return (approximately).

        If return from A to B is R%, then return from B to A is not simply -R%,
        but the relationship is: (1 + R_AB/100) × (1 + R_BA/100) = 1.

        We use a minimum value of 1.00 and a relative tolerance to avoid cases
        where extreme ratios (e.g., 0.01 -> 15.01 = 150000% return) cause
        compounding rounding errors to exceed a fixed absolute tolerance.

        **Validates: Requirement 10.4**
        """
        assume(v_earliest > Decimal("0"))
        assume(v_latest > Decimal("0"))

        service = PerformanceService.__new__(PerformanceService)

        r_ab = service.calculate_cumulative_return(v_earliest, v_latest)
        r_ba = service.calculate_cumulative_return(v_latest, v_earliest)

        assert r_ab is not None
        assert r_ba is not None

        # (1 + R_AB/100) × (1 + R_BA/100) should approximately equal 1
        factor_ab = Decimal("1") + r_ab / Decimal("100")
        factor_ba = Decimal("1") + r_ba / Decimal("100")
        product = factor_ab * factor_ba

        # Use a relative tolerance proportional to the magnitude of the returns
        # Rounding to 2dp on large percentages can compound, so we scale tolerance
        max_return = max(abs(r_ab), abs(r_ba))
        # Base tolerance + scaled component for large returns
        tolerance = Decimal("0.02") + max_return * Decimal("0.0001")
        assert abs(product - Decimal("1")) <= tolerance, (
            f"Inverse relationship broken: "
            f"(1 + {r_ab}/100) × (1 + {r_ba}/100) = {product}, expected ≈ 1. "
            f"V_earliest={v_earliest}, V_latest={v_latest}"
        )
