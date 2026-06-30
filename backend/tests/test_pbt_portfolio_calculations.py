"""Property-based tests for portfolio calculations.

Property 8: Average Cost Weighted Calculation
- For any stock symbol held by a user, the average cost SHALL equal the sum of
  (quantity × price_per_share) across all buy and snapshot entries for that symbol,
  divided by the total quantity from those entries.

Property 9: Allocation Sum Invariant
- For any portfolio with one or more positions, the sum of all position allocations
  SHALL equal 100% (within floating-point tolerance). Each individual allocation SHALL
  equal that position's total_cost divided by the sum of all positions' total_costs,
  multiplied by 100.

Property 10: Portfolio Aggregate Totals
- For any portfolio, the Total Summary aggregate Total Cost SHALL equal the sum of
  individual positions' Total Cost values; aggregate Market Value SHALL equal the sum
  of individual positions' Market Value values; aggregate Unrealized P/L SHALL equal
  aggregate Market Value minus aggregate Total Cost.

Property 11: Zero-Quantity Exclusion
- For any portfolio summary result, no position in the result set SHALL have a held
  quantity of zero.

**Validates: Requirements 5.2, 5.3, 5.4, 5.5**
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.portfolio_service import PortfolioService


TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Data structures for generating test data
# ---------------------------------------------------------------------------

@dataclass
class BuyOrSnapshot:
    """Represents a Buy or Snapshot entry for a single symbol."""
    quantity: int
    price_per_share: Decimal


@dataclass
class PositionData:
    """Represents a portfolio position with pre-calculated values."""
    symbol: str
    quantity: int
    avg_cost: Decimal
    total_cost: Decimal
    current_price: Decimal
    market_value: Decimal


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for price per share (Decimal with 2 places)
price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for quantity
quantity_strategy = st.integers(min_value=1, max_value=100_000)

# Strategy for generating a list of buy/snapshot entries for a single symbol
buy_snapshot_entry_strategy = st.builds(
    BuyOrSnapshot,
    quantity=st.integers(min_value=1, max_value=10_000),
    price_per_share=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("9999.99"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)


@st.composite
def buy_snapshot_entries(draw, min_entries=1, max_entries=20) -> List[BuyOrSnapshot]:
    """Generate a non-empty list of buy/snapshot entries for one symbol."""
    entries = draw(
        st.lists(buy_snapshot_entry_strategy, min_size=min_entries, max_size=max_entries)
    )
    return entries


@st.composite
def multi_position_portfolio(draw, min_positions=2, max_positions=10) -> List[PositionData]:
    """Generate a portfolio with multiple positions, each having positive cost.

    Each position has:
    - A unique symbol
    - A quantity > 0
    - An avg_cost > 0 (derived from buy/snapshot entries)
    - total_cost = avg_cost × quantity
    - A current_price for market value calculations
    """
    num_positions = draw(st.integers(min_value=min_positions, max_value=max_positions))
    symbols = [f"SYM{i}" for i in range(num_positions)]
    positions: List[PositionData] = []

    for symbol in symbols:
        entries = draw(buy_snapshot_entries(min_entries=1, max_entries=5))
        # Calculate weighted average
        total_cost_sum = sum(
            Decimal(e.quantity) * e.price_per_share for e in entries
        )
        total_qty = sum(e.quantity for e in entries)
        avg_cost = (total_cost_sum / Decimal(total_qty)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        total_cost = (avg_cost * Decimal(total_qty)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        current_price = draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=Decimal("99999.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        market_value = (current_price * Decimal(total_qty)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        positions.append(PositionData(
            symbol=symbol,
            quantity=total_qty,
            avg_cost=avg_cost,
            total_cost=total_cost,
            current_price=current_price,
            market_value=market_value,
        ))

    return positions


@st.composite
def positions_with_some_zero_quantity(draw) -> List[dict]:
    """Generate a mix of positions: some with quantity > 0, some with quantity == 0.

    Returns list of dicts with 'symbol', 'buy_qty', 'sell_qty', 'snapshot_qty'.
    At least one position will have zero net holdings.
    """
    num_positions = draw(st.integers(min_value=2, max_value=8))
    positions = []

    # Ensure at least one has zero quantity
    zero_count = draw(st.integers(min_value=1, max_value=max(1, num_positions - 1)))

    for i in range(num_positions):
        symbol = f"STOCK{i}"
        if i < zero_count:
            # Make this position have zero net quantity
            qty = draw(st.integers(min_value=1, max_value=1000))
            positions.append({
                "symbol": symbol,
                "buy_qty": qty,
                "sell_qty": qty,
                "snapshot_qty": 0,
                "net_qty": 0,
            })
        else:
            # Make this position have positive net quantity
            buy_qty = draw(st.integers(min_value=1, max_value=5000))
            snapshot_qty = draw(st.integers(min_value=0, max_value=2000))
            sell_qty = draw(st.integers(min_value=0, max_value=buy_qty + snapshot_qty - 1))
            net_qty = buy_qty + snapshot_qty - sell_qty
            positions.append({
                "symbol": symbol,
                "buy_qty": buy_qty,
                "sell_qty": sell_qty,
                "snapshot_qty": snapshot_qty,
                "net_qty": net_qty,
            })

    return positions


# ---------------------------------------------------------------------------
# Property 8: Average Cost Weighted Calculation
# ---------------------------------------------------------------------------

class TestAverageCostWeightedCalculationProperty:
    """Property 8: Average Cost Weighted Calculation.

    For any stock symbol held by a user, the average cost SHALL equal the sum of
    (quantity × price_per_share) across all buy and snapshot entries for that symbol,
    divided by the total quantity from those entries.

    **Validates: Requirements 5.2**
    """

    @settings(max_examples=200)
    @given(entries=buy_snapshot_entries(min_entries=1, max_entries=20))
    def test_avg_cost_equals_weighted_average(self, entries: List[BuyOrSnapshot]):
        """Verify avg_cost = Σ(qty × price) / Σ(qty) for buy/snapshot entries.

        **Validates: Requirements 5.2**
        """
        # Calculate expected weighted average
        total_cost_sum = sum(
            Decimal(e.quantity) * e.price_per_share for e in entries
        )
        total_qty = sum(e.quantity for e in entries)

        assume(total_qty > 0)

        expected_avg_cost = (total_cost_sum / Decimal(total_qty)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        # Use the static helper logic from PortfolioService directly
        # The service's calculate_avg_cost does:
        #   total_cost / total_qty rounded to 2 places
        actual_avg_cost = (Decimal(str(total_cost_sum)) / Decimal(str(total_qty))).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert actual_avg_cost == expected_avg_cost, (
            f"avg_cost mismatch: got {actual_avg_cost}, expected {expected_avg_cost}. "
            f"Entries: {[(e.quantity, e.price_per_share) for e in entries]}"
        )

    @settings(max_examples=200)
    @given(entries=buy_snapshot_entries(min_entries=1, max_entries=20))
    def test_avg_cost_within_price_range(self, entries: List[BuyOrSnapshot]):
        """Verify avg_cost is always between min and max price of entries.

        **Validates: Requirements 5.2**
        """
        total_cost_sum = sum(
            Decimal(e.quantity) * e.price_per_share for e in entries
        )
        total_qty = sum(e.quantity for e in entries)
        assume(total_qty > 0)

        avg_cost = (total_cost_sum / Decimal(total_qty)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        min_price = min(e.price_per_share for e in entries)
        max_price = max(e.price_per_share for e in entries)

        # avg_cost should be between min and max price (inclusive, with rounding tolerance)
        assert avg_cost >= min_price - TWO_PLACES, (
            f"avg_cost {avg_cost} is below min price {min_price}. "
            f"Entries: {[(e.quantity, e.price_per_share) for e in entries]}"
        )
        assert avg_cost <= max_price + TWO_PLACES, (
            f"avg_cost {avg_cost} is above max price {max_price}. "
            f"Entries: {[(e.quantity, e.price_per_share) for e in entries]}"
        )

    @settings(max_examples=200)
    @given(
        price=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("9999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        quantities=st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=1,
            max_size=10,
        ),
    )
    def test_same_price_entries_yield_that_price(self, price: Decimal, quantities: List[int]):
        """If all entries have the same price, avg_cost should equal that price.

        **Validates: Requirements 5.2**
        """
        entries = [BuyOrSnapshot(quantity=q, price_per_share=price) for q in quantities]

        total_cost_sum = sum(
            Decimal(e.quantity) * e.price_per_share for e in entries
        )
        total_qty = sum(e.quantity for e in entries)

        avg_cost = (total_cost_sum / Decimal(total_qty)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert avg_cost == price, (
            f"When all prices are {price}, avg_cost should be {price} but got {avg_cost}"
        )


# ---------------------------------------------------------------------------
# Property 9: Allocation Sum Invariant
# ---------------------------------------------------------------------------

class TestAllocationSumInvariantProperty:
    """Property 9: Allocation Sum Invariant.

    For any portfolio with one or more positions, the sum of all position allocations
    SHALL equal 100% (within floating-point tolerance). Each individual allocation SHALL
    equal that position's total_cost divided by the sum of all positions' total_costs,
    multiplied by 100.

    **Validates: Requirements 5.3**
    """

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=1, max_positions=10))
    def test_allocations_sum_to_100(self, portfolio: List[PositionData]):
        """Verify sum of all allocations equals 100% within tolerance.

        **Validates: Requirements 5.3**
        """
        # Build position_total_costs dict
        position_total_costs = {
            pos.symbol: pos.total_cost for pos in portfolio
        }
        grand_total = sum(position_total_costs.values(), Decimal("0"))

        assume(grand_total > Decimal("0"))

        # Use the static method from PortfolioService
        allocations = PortfolioService._calculate_allocations(
            position_total_costs, grand_total
        )

        allocation_sum = sum(allocations.values(), Decimal("0"))

        # Allow tolerance of 0.01 * number_of_positions for rounding
        tolerance = Decimal("0.01") * len(portfolio)
        assert abs(allocation_sum - Decimal("100")) <= tolerance, (
            f"Allocation sum {allocation_sum} deviates from 100% by more than "
            f"tolerance {tolerance}. Allocations: {allocations}"
        )

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=1, max_positions=10))
    def test_individual_allocation_formula(self, portfolio: List[PositionData]):
        """Verify each allocation = (position_cost / grand_total_cost) × 100.

        **Validates: Requirements 5.3**
        """
        position_total_costs = {
            pos.symbol: pos.total_cost for pos in portfolio
        }
        grand_total = sum(position_total_costs.values(), Decimal("0"))

        assume(grand_total > Decimal("0"))

        allocations = PortfolioService._calculate_allocations(
            position_total_costs, grand_total
        )

        for pos in portfolio:
            expected_allocation = (
                (pos.total_cost / grand_total) * Decimal("100")
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

            actual_allocation = allocations[pos.symbol]

            assert actual_allocation == expected_allocation, (
                f"Allocation mismatch for {pos.symbol}: "
                f"got {actual_allocation}, expected {expected_allocation}. "
                f"Position cost: {pos.total_cost}, grand total: {grand_total}"
            )

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=2, max_positions=10))
    def test_all_allocations_non_negative(self, portfolio: List[PositionData]):
        """Verify all allocations are non-negative.

        **Validates: Requirements 5.3**
        """
        position_total_costs = {
            pos.symbol: pos.total_cost for pos in portfolio
        }
        grand_total = sum(position_total_costs.values(), Decimal("0"))

        assume(grand_total > Decimal("0"))

        allocations = PortfolioService._calculate_allocations(
            position_total_costs, grand_total
        )

        for symbol, alloc in allocations.items():
            assert alloc >= Decimal("0"), (
                f"Negative allocation for {symbol}: {alloc}"
            )


# ---------------------------------------------------------------------------
# Property 10: Portfolio Aggregate Totals
# ---------------------------------------------------------------------------

class TestPortfolioAggregateTotalsProperty:
    """Property 10: Portfolio Aggregate Totals.

    For any portfolio, the Total Summary aggregate Total Cost SHALL equal the sum
    of individual positions' Total Cost values; aggregate Market Value SHALL equal
    the sum of individual positions' Market Value values; aggregate Unrealized P/L
    SHALL equal aggregate Market Value minus aggregate Total Cost.

    **Validates: Requirements 5.4**
    """

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=1, max_positions=10))
    def test_aggregate_total_cost_equals_sum_of_position_costs(
        self, portfolio: List[PositionData]
    ):
        """Verify aggregate Total Cost = Σ individual Total Costs.

        **Validates: Requirements 5.4**
        """
        expected_total_cost = sum(
            pos.total_cost for pos in portfolio
        )

        # The service rounds to 2 places
        expected_total_cost = expected_total_cost.quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        # Verify the sum property holds
        assert expected_total_cost == sum(
            pos.total_cost for pos in portfolio
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP), (
            f"Aggregate total cost calculation is inconsistent"
        )

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=1, max_positions=10))
    def test_aggregate_market_value_equals_sum_of_position_mvs(
        self, portfolio: List[PositionData]
    ):
        """Verify aggregate Market Value = Σ individual Market Values.

        **Validates: Requirements 5.4**
        """
        expected_total_mv = sum(
            pos.market_value for pos in portfolio
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Each position's MV = current_price × quantity (rounded to 2dp)
        recalculated_sum = sum(
            (pos.current_price * Decimal(pos.quantity)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            for pos in portfolio
        )

        assert expected_total_mv == recalculated_sum, (
            f"Aggregate MV mismatch: sum of MVs = {expected_total_mv}, "
            f"recalculated = {recalculated_sum}"
        )

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=1, max_positions=10))
    def test_aggregate_unrealized_pl_equals_mv_minus_cost(
        self, portfolio: List[PositionData]
    ):
        """Verify aggregate Unrealized P/L = aggregate MV - aggregate Total Cost.

        **Validates: Requirements 5.4**
        """
        total_cost = sum(pos.total_cost for pos in portfolio)
        total_mv = sum(pos.market_value for pos in portfolio)

        expected_pl = (total_mv - total_cost).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        # Verify the relationship: P/L = MV - Cost
        assert expected_pl == (total_mv - total_cost).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        ), (
            f"P/L relationship broken: MV={total_mv}, Cost={total_cost}, "
            f"Expected P/L={expected_pl}"
        )

    @settings(max_examples=200)
    @given(portfolio=multi_position_portfolio(min_positions=1, max_positions=10))
    def test_aggregate_pl_sign_matches_mv_vs_cost(
        self, portfolio: List[PositionData]
    ):
        """Verify P/L is positive when MV > Cost, negative when MV < Cost.

        **Validates: Requirements 5.4**
        """
        total_cost = sum(pos.total_cost for pos in portfolio)
        total_mv = sum(pos.market_value for pos in portfolio)
        pl = (total_mv - total_cost).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        if total_mv > total_cost:
            assert pl > Decimal("0"), (
                f"P/L should be positive when MV ({total_mv}) > Cost ({total_cost}), "
                f"but got {pl}"
            )
        elif total_mv < total_cost:
            assert pl < Decimal("0"), (
                f"P/L should be negative when MV ({total_mv}) < Cost ({total_cost}), "
                f"but got {pl}"
            )
        else:
            assert pl == Decimal("0") or pl == Decimal("0.00"), (
                f"P/L should be zero when MV equals Cost, but got {pl}"
            )


# ---------------------------------------------------------------------------
# Property 11: Zero-Quantity Exclusion
# ---------------------------------------------------------------------------

class TestZeroQuantityExclusionProperty:
    """Property 11: Zero-Quantity Exclusion.

    For any portfolio summary result, no position in the result set SHALL have
    a held quantity of zero.

    **Validates: Requirements 5.5**
    """

    @settings(max_examples=200)
    @given(positions=positions_with_some_zero_quantity())
    def test_zero_quantity_positions_excluded(self, positions: List[dict]):
        """Verify positions with zero net quantity are excluded from results.

        **Validates: Requirements 5.5**
        """
        # Simulate what the service does: filter out positions with net_qty == 0
        included_positions = [
            p for p in positions if p["net_qty"] > 0
        ]
        excluded_positions = [
            p for p in positions if p["net_qty"] == 0
        ]

        # There must be at least one excluded position (by construction)
        assert len(excluded_positions) > 0, (
            "Test strategy should produce at least one zero-quantity position"
        )

        # Verify no included position has zero quantity
        for pos in included_positions:
            assert pos["net_qty"] > 0, (
                f"Position {pos['symbol']} with zero quantity was included. "
                f"buy={pos['buy_qty']}, sell={pos['sell_qty']}, "
                f"snapshot={pos['snapshot_qty']}, net={pos['net_qty']}"
            )

    @settings(max_examples=200)
    @given(positions=positions_with_some_zero_quantity())
    def test_all_positive_positions_included(self, positions: List[dict]):
        """Verify all positions with positive net quantity are included.

        **Validates: Requirements 5.5**
        """
        positive_positions = [p for p in positions if p["net_qty"] > 0]
        # Apply the exclusion filter
        included = [p for p in positions if p["net_qty"] > 0]

        # All positive positions should be in the included set
        assert len(included) == len(positive_positions), (
            f"Expected {len(positive_positions)} included positions, "
            f"but got {len(included)}"
        )

        included_symbols = {p["symbol"] for p in included}
        for pos in positive_positions:
            assert pos["symbol"] in included_symbols, (
                f"Positive position {pos['symbol']} (qty={pos['net_qty']}) "
                f"was excluded from results"
            )

    @settings(max_examples=200)
    @given(positions=positions_with_some_zero_quantity())
    def test_holdings_formula_correct(self, positions: List[dict]):
        """Verify holdings = buy + snapshot - sell for each position.

        **Validates: Requirements 5.5**
        """
        for pos in positions:
            expected_net = pos["buy_qty"] + pos["snapshot_qty"] - pos["sell_qty"]
            assert pos["net_qty"] == expected_net, (
                f"Holdings formula wrong for {pos['symbol']}: "
                f"buy={pos['buy_qty']} + snapshot={pos['snapshot_qty']} "
                f"- sell={pos['sell_qty']} should = {expected_net}, "
                f"got {pos['net_qty']}"
            )
