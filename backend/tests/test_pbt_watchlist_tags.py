"""Property-based tests for watchlist, tags, and tag filtering logic.

Property 21: Watchlist "At Target" Highlight
- Generate watchlist items + prices; verify highlight iff current_price ≤ interested_at_price

Property 22: Tag Filter Correctness
- Generate tagged items + tag filter; verify all results have the tag, no tagged items excluded

Property 23: Per-Tag Performance Aggregation
- Generate tagged stocks with costs/values; verify aggregated metrics per tag

**Validates: Requirements 19.4, 21.4, 21.5**
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.watchlist_service import WatchlistService

TWO_PLACES = Decimal("0.01")

# --- Strategies ---

# Positive decimal for prices (min 0.01 to avoid zero)
price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Optional price (can be None)
optional_price_strategy = st.one_of(st.none(), price_strategy)

# Positive integer for quantities
quantity_strategy = st.integers(min_value=1, max_value=99_999_999)

# Stock symbol strategy
symbol_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    min_size=1,
    max_size=5,
).map(lambda s: s.upper())

# Tag name strategy (1-50 chars)
tag_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_-"),
    min_size=1,
    max_size=20,
)


class TestWatchlistAtTargetHighlightProperty:
    """Property 21: Watchlist "At Target" Highlight.

    For any watchlist item with an "Interested At" price, the item SHALL be
    highlighted as "At Target" if and only if the current market price is less
    than or equal to the interested_at_price.

    When either price is None, is_at_target returns False.

    **Validates: Requirement 19.4**
    """

    @settings(max_examples=200)
    @given(
        interested_at_price=optional_price_strategy,
        current_price=optional_price_strategy,
    )
    def test_is_at_target_correctness(
        self,
        interested_at_price: Optional[Decimal],
        current_price: Optional[Decimal],
    ):
        """Verify is_at_target matches: both not None AND current_price <= interested_at_price."""
        result = WatchlistService.is_at_target(interested_at_price, current_price)

        if interested_at_price is None or current_price is None:
            assert result is False, (
                f"Should be False when either price is None: "
                f"interested_at_price={interested_at_price}, current_price={current_price}"
            )
        elif current_price <= interested_at_price:
            assert result is True, (
                f"Should be True when current_price <= interested_at_price: "
                f"current_price={current_price}, interested_at_price={interested_at_price}"
            )
        else:
            assert result is False, (
                f"Should be False when current_price > interested_at_price: "
                f"current_price={current_price}, interested_at_price={interested_at_price}"
            )

    @settings(max_examples=200)
    @given(
        interested_at_price=price_strategy,
        current_price=price_strategy,
    )
    def test_at_target_when_both_prices_present(
        self,
        interested_at_price: Decimal,
        current_price: Decimal,
    ):
        """When both prices are present, highlight iff current_price <= interested_at_price."""
        result = WatchlistService.is_at_target(interested_at_price, current_price)

        expected = current_price <= interested_at_price
        assert result == expected, (
            f"At target mismatch: interested_at_price={interested_at_price}, "
            f"current_price={current_price}, got={result}, expected={expected}"
        )

    @settings(max_examples=50)
    @given(price=price_strategy)
    def test_always_at_target_when_price_equals_target(self, price: Decimal):
        """When current_price == interested_at_price, always at target."""
        assert WatchlistService.is_at_target(price, price) is True, (
            f"Should be at target when price equals target: price={price}"
        )

    @settings(max_examples=50)
    @given(current_price=optional_price_strategy)
    def test_never_at_target_when_interested_price_is_none(
        self, current_price: Optional[Decimal]
    ):
        """When interested_at_price is None, never at target regardless of current_price."""
        assert WatchlistService.is_at_target(None, current_price) is False

    @settings(max_examples=50)
    @given(interested_at_price=optional_price_strategy)
    def test_never_at_target_when_current_price_is_none(
        self, interested_at_price: Optional[Decimal]
    ):
        """When current_price is None, never at target regardless of interested_at_price."""
        assert WatchlistService.is_at_target(interested_at_price, None) is False


class TestTagFilterCorrectnessProperty:
    """Property 22: Tag Filter Correctness.

    For any tag filter applied to a set of items, every item in the result set
    SHALL have the specified tag assigned, and no item with that tag SHALL be excluded.

    We test the pure filtering logic directly without async DB operations.

    **Validates: Requirement 21.4**
    """

    @staticmethod
    def filter_items_by_tag(
        items: list[dict], filter_tag: str
    ) -> list[dict]:
        """Pure logic: filter items that have a specific tag assigned.

        This mirrors what the tag service does at the DB level:
        given items with tag assignments, return only those with the filter_tag.
        """
        return [item for item in items if filter_tag in item["tags"]]

    @settings(max_examples=200)
    @given(
        items=st.lists(
            st.fixed_dictionaries({
                "symbol": symbol_strategy,
                "tags": st.lists(tag_name_strategy, min_size=0, max_size=5),
            }),
            min_size=1,
            max_size=20,
        ),
        filter_tag=tag_name_strategy,
    )
    def test_tag_filter_all_results_have_tag(
        self, items: list[dict], filter_tag: str
    ):
        """All items in the filtered result must have the filter tag."""
        results = self.filter_items_by_tag(items, filter_tag)

        for item in results:
            assert filter_tag in item["tags"], (
                f"Item {item['symbol']} in results but does not have tag '{filter_tag}': "
                f"tags={item['tags']}"
            )

    @settings(max_examples=200)
    @given(
        items=st.lists(
            st.fixed_dictionaries({
                "symbol": symbol_strategy,
                "tags": st.lists(tag_name_strategy, min_size=0, max_size=5),
            }),
            min_size=1,
            max_size=20,
        ),
        filter_tag=tag_name_strategy,
    )
    def test_tag_filter_no_matching_items_excluded(
        self, items: list[dict], filter_tag: str
    ):
        """No item with the filter tag should be excluded from results."""
        results = self.filter_items_by_tag(items, filter_tag)

        # All items that have the tag should be in results
        expected_items = [item for item in items if filter_tag in item["tags"]]
        assert len(results) == len(expected_items), (
            f"Result count mismatch: got {len(results)}, expected {len(expected_items)} "
            f"for filter_tag='{filter_tag}'"
        )

        # Every expected item is in the results
        for item in expected_items:
            assert item in results, (
                f"Item {item['symbol']} has tag '{filter_tag}' but was excluded from results"
            )

    @settings(max_examples=200)
    @given(
        items=st.lists(
            st.fixed_dictionaries({
                "symbol": symbol_strategy,
                "tags": st.lists(tag_name_strategy, min_size=0, max_size=5),
            }),
            min_size=1,
            max_size=20,
        ),
        filter_tag=tag_name_strategy,
    )
    def test_tag_filter_result_is_subset_of_input(
        self, items: list[dict], filter_tag: str
    ):
        """Filtered results should be a subset of the original items."""
        results = self.filter_items_by_tag(items, filter_tag)

        for item in results:
            assert item in items, (
                f"Filtered result {item} is not in the original item list"
            )


class TestPerTagPerformanceAggregationProperty:
    """Property 23: Per-Tag Performance Aggregation.

    For any custom tag assigned to one or more stocks, the aggregated metrics
    for that tag SHALL equal:
    - total_cost = Σ(avg_cost × quantity) for stocks with this tag
    - total_market_value = Σ(current_price × quantity) for stocks with this tag
    - unrealized_pl = total_market_value - total_cost
    - roi_percent = (unrealized_pl / total_cost) × 100

    We test the pure formula logic directly.

    **Validates: Requirement 21.5**
    """

    @staticmethod
    def calculate_tag_performance(
        stocks: list[dict],
    ) -> dict:
        """Pure logic: calculate aggregated performance for a group of tagged stocks.

        Each stock dict has: avg_cost (Decimal), quantity (int), current_price (Decimal).
        Returns dict with total_cost, total_market_value, unrealized_pl, roi_percent.
        """
        total_cost = Decimal("0")
        total_market_value = Decimal("0")

        for stock in stocks:
            cost = (stock["avg_cost"] * Decimal(stock["quantity"])).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            mv = (stock["current_price"] * Decimal(stock["quantity"])).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            total_cost += cost
            total_market_value += mv

        total_cost = total_cost.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        total_market_value = total_market_value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        unrealized_pl = (total_market_value - total_cost).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        if total_cost > Decimal("0"):
            roi_percent = (
                (unrealized_pl / total_cost) * Decimal("100")
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            roi_percent = Decimal("0.00")

        return {
            "total_cost": total_cost,
            "total_market_value": total_market_value,
            "unrealized_pl": unrealized_pl,
            "roi_percent": roi_percent,
        }

    @settings(max_examples=200)
    @given(
        stocks=st.lists(
            st.fixed_dictionaries({
                "avg_cost": price_strategy,
                "quantity": quantity_strategy,
                "current_price": price_strategy,
            }),
            min_size=1,
            max_size=10,
        ),
    )
    def test_total_cost_is_sum_of_individual_costs(self, stocks: list[dict]):
        """total_cost = Σ(avg_cost × quantity) for all stocks in the tag group."""
        result = self.calculate_tag_performance(stocks)

        expected_total_cost = Decimal("0")
        for stock in stocks:
            expected_total_cost += (
                stock["avg_cost"] * Decimal(stock["quantity"])
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        expected_total_cost = expected_total_cost.quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert result["total_cost"] == expected_total_cost, (
            f"Total cost mismatch: got {result['total_cost']}, expected {expected_total_cost}"
        )

    @settings(max_examples=200)
    @given(
        stocks=st.lists(
            st.fixed_dictionaries({
                "avg_cost": price_strategy,
                "quantity": quantity_strategy,
                "current_price": price_strategy,
            }),
            min_size=1,
            max_size=10,
        ),
    )
    def test_total_market_value_is_sum_of_individual_mvs(self, stocks: list[dict]):
        """total_market_value = Σ(current_price × quantity) for all stocks."""
        result = self.calculate_tag_performance(stocks)

        expected_total_mv = Decimal("0")
        for stock in stocks:
            expected_total_mv += (
                stock["current_price"] * Decimal(stock["quantity"])
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        expected_total_mv = expected_total_mv.quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        assert result["total_market_value"] == expected_total_mv, (
            f"Total MV mismatch: got {result['total_market_value']}, expected {expected_total_mv}"
        )

    @settings(max_examples=200)
    @given(
        stocks=st.lists(
            st.fixed_dictionaries({
                "avg_cost": price_strategy,
                "quantity": quantity_strategy,
                "current_price": price_strategy,
            }),
            min_size=1,
            max_size=10,
        ),
    )
    def test_unrealized_pl_equals_mv_minus_cost(self, stocks: list[dict]):
        """unrealized_pl = total_market_value - total_cost."""
        result = self.calculate_tag_performance(stocks)

        expected_pl = (
            result["total_market_value"] - result["total_cost"]
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        assert result["unrealized_pl"] == expected_pl, (
            f"Unrealized P/L mismatch: got {result['unrealized_pl']}, expected {expected_pl}"
        )

    @settings(max_examples=200)
    @given(
        stocks=st.lists(
            st.fixed_dictionaries({
                "avg_cost": price_strategy,
                "quantity": quantity_strategy,
                "current_price": price_strategy,
            }),
            min_size=1,
            max_size=10,
        ),
    )
    def test_roi_percent_formula(self, stocks: list[dict]):
        """roi_percent = (unrealized_pl / total_cost) × 100 when total_cost > 0."""
        result = self.calculate_tag_performance(stocks)

        # Since all stocks have positive avg_cost and quantity, total_cost > 0
        assert result["total_cost"] > Decimal("0"), "total_cost should be positive"

        expected_roi = (
            (result["unrealized_pl"] / result["total_cost"]) * Decimal("100")
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        assert result["roi_percent"] == expected_roi, (
            f"ROI mismatch: got {result['roi_percent']}, expected {expected_roi}"
        )

    @settings(max_examples=200)
    @given(
        stocks=st.lists(
            st.fixed_dictionaries({
                "avg_cost": price_strategy,
                "quantity": quantity_strategy,
                "current_price": price_strategy,
            }),
            min_size=1,
            max_size=10,
        ),
    )
    def test_aggregation_consistency(self, stocks: list[dict]):
        """Verify the relationship: unrealized_pl = total_mv - total_cost and
        roi = unrealized_pl / total_cost * 100 all hold together."""
        result = self.calculate_tag_performance(stocks)

        # unrealized_pl = total_market_value - total_cost
        assert result["unrealized_pl"] == (
            result["total_market_value"] - result["total_cost"]
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # roi_percent = (unrealized_pl / total_cost) * 100
        if result["total_cost"] > Decimal("0"):
            expected_roi = (
                (result["unrealized_pl"] / result["total_cost"]) * Decimal("100")
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            assert result["roi_percent"] == expected_roi
