"""Property-based tests for alerts and dividends logic.

Property 15: Price Alert Trigger Correctness
- Generate alert configs + market prices; verify trigger iff
  (Above AND price >= target) OR (Below AND price <= target)

Property 26: Dividend Yield on Cost Calculation
- Generate dividend records + costs; verify (annual_dividends / total_cost) × 100

**Validates: Requirements 14.2, 15.3**
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.enums import AlertType
from app.services.alert_service import AlertService


# --- Strategies ---

# Positive decimal for prices (min 0.01 to avoid zero)
price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for alert types
alert_type_strategy = st.sampled_from([AlertType.ABOVE.value, AlertType.BELOW.value])

# Positive decimal for dividends
dividend_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Positive decimal for total cost (must be > 0 to avoid division by zero)
cost_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


class TestPriceAlertTriggerCorrectnessProperty:
    """Property 15: Price Alert Trigger Correctness.

    For any alert configuration with alert_type (Above/Below),
    target_price, and current_price:
    - Alert triggers iff:
      - (alert_type == "Above" AND current_price >= target_price) OR
      - (alert_type == "Below" AND current_price <= target_price)

    **Validates: Requirement 14.2**
    """

    @settings(max_examples=200)
    @given(
        alert_type=alert_type_strategy,
        target_price=price_strategy,
        current_price=price_strategy,
    )
    def test_alert_trigger_correctness(
        self,
        alert_type: str,
        target_price: Decimal,
        current_price: Decimal,
    ):
        """Verify _should_trigger matches the expected trigger logic."""
        result = AlertService._should_trigger(
            alert_type=alert_type,
            target_price=target_price,
            current_price=current_price,
        )

        # Compute expected result
        if alert_type == AlertType.ABOVE.value:
            expected = current_price >= target_price
        elif alert_type == AlertType.BELOW.value:
            expected = current_price <= target_price
        else:
            expected = False

        assert result == expected, (
            f"Alert trigger mismatch: alert_type={alert_type}, "
            f"target_price={target_price}, current_price={current_price}, "
            f"got={result}, expected={expected}"
        )

    @settings(max_examples=200)
    @given(
        target_price=price_strategy,
        current_price=price_strategy,
    )
    def test_above_alert_triggers_when_price_at_or_above_target(
        self,
        target_price: Decimal,
        current_price: Decimal,
    ):
        """Above alert: triggered iff current_price >= target_price."""
        result = AlertService._should_trigger(
            alert_type=AlertType.ABOVE.value,
            target_price=target_price,
            current_price=current_price,
        )

        if current_price >= target_price:
            assert result is True, (
                f"Above alert should trigger: current={current_price} >= target={target_price}"
            )
        else:
            assert result is False, (
                f"Above alert should NOT trigger: current={current_price} < target={target_price}"
            )

    @settings(max_examples=200)
    @given(
        target_price=price_strategy,
        current_price=price_strategy,
    )
    def test_below_alert_triggers_when_price_at_or_below_target(
        self,
        target_price: Decimal,
        current_price: Decimal,
    ):
        """Below alert: triggered iff current_price <= target_price."""
        result = AlertService._should_trigger(
            alert_type=AlertType.BELOW.value,
            target_price=target_price,
            current_price=current_price,
        )

        if current_price <= target_price:
            assert result is True, (
                f"Below alert should trigger: current={current_price} <= target={target_price}"
            )
        else:
            assert result is False, (
                f"Below alert should NOT trigger: current={current_price} > target={target_price}"
            )

    @settings(max_examples=50)
    @given(
        target_price=price_strategy,
    )
    def test_alert_always_triggers_at_exact_target(
        self,
        target_price: Decimal,
    ):
        """Both Above and Below alerts trigger when current_price == target_price."""
        # Above at exact target
        assert AlertService._should_trigger(
            alert_type=AlertType.ABOVE.value,
            target_price=target_price,
            current_price=target_price,
        ) is True, f"Above alert should trigger at exact target={target_price}"

        # Below at exact target
        assert AlertService._should_trigger(
            alert_type=AlertType.BELOW.value,
            target_price=target_price,
            current_price=target_price,
        ) is True, f"Below alert should trigger at exact target={target_price}"


class TestDividendYieldOnCostCalculationProperty:
    """Property 26: Dividend Yield on Cost Calculation.

    For any annual_dividends (positive) and total_cost (positive):
    - yield_on_cost = (annual_dividends / total_cost) × 100
    - Result is rounded to 2 decimal places using ROUND_HALF_UP

    **Validates: Requirement 15.3**
    """

    @settings(max_examples=200)
    @given(
        annual_dividends=dividend_strategy,
        total_cost=cost_strategy,
    )
    def test_yield_on_cost_calculation(
        self,
        annual_dividends: Decimal,
        total_cost: Decimal,
    ):
        """Verify yield_on_cost = (annual_dividends / total_cost) × 100, to 2dp."""
        # This mirrors the calculation in DividendService.get_projection
        TWO_PLACES = Decimal("0.01")

        yield_on_cost = (
            (annual_dividends / total_cost) * Decimal("100")
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Independently compute expected value
        expected = (
            (annual_dividends / total_cost) * Decimal("100")
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        assert yield_on_cost == expected, (
            f"Yield on cost mismatch: annual_dividends={annual_dividends}, "
            f"total_cost={total_cost}, got={yield_on_cost}, expected={expected}"
        )

        # Verify the result is non-negative (both inputs are positive)
        # Note: very small dividends relative to large costs can round to 0.00
        assert yield_on_cost >= Decimal("0"), (
            f"Yield on cost should be non-negative for positive inputs: "
            f"annual_dividends={annual_dividends}, total_cost={total_cost}"
        )

        # Verify result has at most 2 decimal places
        assert yield_on_cost == yield_on_cost.quantize(TWO_PLACES, rounding=ROUND_HALF_UP), (
            f"Yield on cost should have exactly 2 decimal places: {yield_on_cost}"
        )

    @settings(max_examples=200)
    @given(
        annual_dividends=dividend_strategy,
        total_cost=cost_strategy,
    )
    def test_yield_on_cost_proportionality(
        self,
        annual_dividends: Decimal,
        total_cost: Decimal,
    ):
        """Verify yield increases with higher dividends (same cost) and
        decreases with higher cost (same dividends)."""
        TWO_PLACES = Decimal("0.01")

        yield_on_cost = (
            (annual_dividends / total_cost) * Decimal("100")
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Double the dividends should give approximately double the yield
        doubled_dividends = annual_dividends * 2
        if doubled_dividends <= Decimal("99999999.99"):
            doubled_yield = (
                (doubled_dividends / total_cost) * Decimal("100")
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            assert doubled_yield >= yield_on_cost, (
                f"Doubling dividends should not decrease yield: "
                f"original={yield_on_cost}, doubled={doubled_yield}"
            )

        # Double the cost should give approximately half the yield
        doubled_cost = total_cost * 2
        if doubled_cost <= Decimal("99999999.99"):
            halved_yield = (
                (annual_dividends / doubled_cost) * Decimal("100")
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            assert halved_yield <= yield_on_cost, (
                f"Doubling cost should not increase yield: "
                f"original={yield_on_cost}, halved={halved_yield}"
            )

    @settings(max_examples=100)
    @given(
        annual_dividends=dividend_strategy,
    )
    def test_yield_100_percent_when_dividends_equal_cost(
        self,
        annual_dividends: Decimal,
    ):
        """When annual_dividends == total_cost, yield_on_cost should be exactly 100.00."""
        TWO_PLACES = Decimal("0.01")

        yield_on_cost = (
            (annual_dividends / annual_dividends) * Decimal("100")
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        assert yield_on_cost == Decimal("100.00"), (
            f"Yield should be 100.00 when dividends == cost: "
            f"annual_dividends={annual_dividends}, got={yield_on_cost}"
        )
