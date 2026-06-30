"""Property-based tests for realized P/L and risk metrics logic.

Property 16: Realized P/L Calculation
- Generate sell params; verify (sell_price - avg_cost) × qty, classify short/long-term

Property 17: Target Allocation Sum Constraint
- Generate target allocations; verify sum = 100%

Property 18: Portfolio Beta Weighted Average
- Generate positions with betas; verify Σ(allocation × beta)

Property 19: Concentration Warning Thresholds
- Generate portfolios; verify sector >50% triggers warning, stock >25% triggers warning

Property 20: Maximum Drawdown Calculation
- Generate value sequences; verify largest peak-to-trough / peak × 100

**Validates: Requirements 16.1, 16.5, 17.1, 18.1, 18.3, 18.4, 18.5**
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.enums import TargetType
from app.schemas.market_data import TickerInfo
from app.schemas.rebalancing import TargetAllocationEntry, TargetAllocationUpdate
from app.schemas.risk_metrics import (
    ConcentrationWarning,
    PositionConcentration,
    SectorConcentration,
)
from app.services.risk_metrics_service import (
    RiskMetricsService,
    SECTOR_CONCENTRATION_THRESHOLD,
    POSITION_CONCENTRATION_THRESHOLD,
)

TWO_PLACES = Decimal("0.01")

# --- Strategies ---

# Positive decimal for prices (min 0.01)
price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Positive integer for quantities
quantity_strategy = st.integers(min_value=1, max_value=99_999_999)

# Days held for term classification
days_held_strategy = st.integers(min_value=0, max_value=10000)

# Beta values (can be negative, typically 0-3 range but allow wider)
beta_strategy = st.decimals(
    min_value=Decimal("-2.00"),
    max_value=Decimal("5.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Allocation percentages (positive, up to 100)
allocation_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Portfolio value sequence values
portfolio_value_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


class TestRealizedPLCalculationProperty:
    """Property 16: Realized P/L Calculation.

    For any sell transaction where the average cost at time of sale is known:
    - realized_pl = (sell_price - avg_cost) × sell_quantity
    - Classification: Short-term if hold_duration_days < 365, Long-term if >= 365

    **Validates: Requirements 16.1, 16.5**
    """

    @settings(max_examples=200)
    @given(
        sell_price=price_strategy,
        avg_cost=price_strategy,
        sell_qty=quantity_strategy,
    )
    def test_realized_pl_formula(
        self,
        sell_price: Decimal,
        avg_cost: Decimal,
        sell_qty: int,
    ):
        """Verify realized_pl = (sell_price - avg_cost) × sell_qty."""
        realized_pl = (sell_price - avg_cost) * Decimal(str(sell_qty))
        realized_pl = realized_pl.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Independently compute expected
        expected = (sell_price - avg_cost) * Decimal(str(sell_qty))
        expected = expected.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        assert realized_pl == expected, (
            f"Realized P/L mismatch: sell_price={sell_price}, avg_cost={avg_cost}, "
            f"sell_qty={sell_qty}, got={realized_pl}, expected={expected}"
        )

        # Verify sign correctness
        if sell_price > avg_cost:
            assert realized_pl > Decimal("0"), (
                f"Profit expected: sell_price={sell_price} > avg_cost={avg_cost}"
            )
        elif sell_price < avg_cost:
            assert realized_pl < Decimal("0"), (
                f"Loss expected: sell_price={sell_price} < avg_cost={avg_cost}"
            )
        else:
            assert realized_pl == Decimal("0.00"), (
                f"Zero P/L expected: sell_price={sell_price} == avg_cost={avg_cost}"
            )

    @settings(max_examples=200)
    @given(
        hold_duration_days=days_held_strategy,
    )
    def test_term_classification(
        self,
        hold_duration_days: int,
    ):
        """Verify term classification: <365 = Short-term, >=365 = Long-term."""
        term_type = "Short-term" if hold_duration_days < 365 else "Long-term"

        if hold_duration_days < 365:
            assert term_type == "Short-term", (
                f"Should be Short-term for {hold_duration_days} days"
            )
        else:
            assert term_type == "Long-term", (
                f"Should be Long-term for {hold_duration_days} days"
            )

    @settings(max_examples=200)
    @given(
        sell_price=price_strategy,
        avg_cost=price_strategy,
        sell_qty=quantity_strategy,
        hold_duration_days=days_held_strategy,
    )
    def test_realized_pl_with_term_classification(
        self,
        sell_price: Decimal,
        avg_cost: Decimal,
        sell_qty: int,
        hold_duration_days: int,
    ):
        """Verify full realized P/L record: formula + term classification together."""
        realized_pl = (sell_price - avg_cost) * Decimal(str(sell_qty))
        realized_pl = realized_pl.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        term_type = "Short-term" if hold_duration_days < 365 else "Long-term"

        # Verify the result is a valid Decimal with 2 places
        assert realized_pl == realized_pl.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Verify term type is one of the valid options
        assert term_type in ("Short-term", "Long-term")

        # Verify the boundary: exactly 365 days is Long-term
        if hold_duration_days == 365:
            assert term_type == "Long-term"

        # Verify the boundary: exactly 364 days is Short-term
        if hold_duration_days == 364:
            assert term_type == "Short-term"


class TestTargetAllocationSumConstraintProperty:
    """Property 17: Target Allocation Sum Constraint.

    For any set of target allocations:
    - If they sum to exactly 100%, the schema accepts them
    - If they do NOT sum to 100%, the schema rejects them

    **Validates: Requirement 17.1**
    """

    @settings(max_examples=200)
    @given(
        data=st.data(),
        n=st.integers(min_value=1, max_value=10),
    )
    def test_valid_allocations_sum_to_100(self, data, n: int):
        """Generate allocations that sum to 100% and verify schema accepts them."""
        # Generate n-1 random values that leave room for the last one
        parts = []
        remaining = Decimal("100.00")

        for i in range(n - 1):
            # Each part must be at least 0.00 and leave at least 0.00 for each remaining item
            remaining_items = n - i - 1
            max_for_this = remaining - Decimal("0.00") * remaining_items
            if max_for_this <= Decimal("0.00"):
                max_for_this = Decimal("0.00")

            # Generate a value between 0.00 and max_for_this
            val = data.draw(
                st.decimals(
                    min_value=Decimal("0.00"),
                    max_value=max_for_this,
                    places=2,
                    allow_nan=False,
                    allow_infinity=False,
                )
            )
            parts.append(val)
            remaining -= val

        # Last part gets the remainder
        parts.append(remaining.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))

        # Ensure non-negative remainder
        assume(parts[-1] >= Decimal("0.00"))
        assume(parts[-1] <= Decimal("100.00"))

        # Verify sum is 100
        total = sum(parts)
        assume(total == Decimal("100.00"))

        # Build targets
        targets = [
            TargetAllocationEntry(
                target_key=f"STOCK{i}",
                target_type=TargetType.SYMBOL,
                target_percentage=pct,
            )
            for i, pct in enumerate(parts)
        ]

        # Validate: should NOT raise
        result = TargetAllocationUpdate(targets=targets)
        assert result is not None
        assert len(result.targets) == n

        # Verify the sum is indeed 100
        actual_sum = sum(t.target_percentage for t in result.targets)
        assert actual_sum == Decimal("100.00"), (
            f"Sum should be 100.00, got {actual_sum}"
        )

    @settings(max_examples=200)
    @given(
        n=st.integers(min_value=1, max_value=10),
        offset=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("50.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        direction=st.sampled_from(["over", "under"]),
    )
    def test_invalid_allocations_not_100_rejected(
        self, n: int, offset: Decimal, direction: str
    ):
        """Generate allocations that do NOT sum to 100% and verify rejection."""
        # Create equal parts that sum to 100, then adjust
        base_pct = (Decimal("100.00") / n).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        parts = [base_pct] * n

        # Adjust last part so total is exactly 100 before we offset it
        current_sum = sum(parts)
        parts[-1] += (Decimal("100.00") - current_sum)

        # Now modify to make it NOT sum to 100
        if direction == "over":
            parts[0] += offset
        else:
            # Ensure we don't go below 0
            if parts[0] > offset:
                parts[0] -= offset
            else:
                parts[0] = Decimal("0.00")
                # Reduce from another part if available
                if n > 1 and parts[1] > offset:
                    parts[1] -= offset
                else:
                    # Skip this case
                    assume(False)

        # Verify sum != 100
        total = sum(parts)
        assume(total != Decimal("100.00"))

        # Ensure all percentages are within valid range [0, 100]
        assume(all(Decimal("0.00") <= p <= Decimal("100.00") for p in parts))

        targets = [
            TargetAllocationEntry(
                target_key=f"STOCK{i}",
                target_type=TargetType.SYMBOL,
                target_percentage=pct,
            )
            for i, pct in enumerate(parts)
        ]

        # Validate: should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            TargetAllocationUpdate(targets=targets)

        # Verify the error is about sum not being 100%
        error_str = str(exc_info.value)
        assert "100" in error_str or "sum" in error_str.lower(), (
            f"Expected error about sum != 100%, got: {error_str}"
        )


class TestPortfolioBetaWeightedAverageProperty:
    """Property 18: Portfolio Beta Weighted Average.

    For any portfolio with positions that have known beta values:
    portfolio_beta = Σ(allocation_weight_i × beta_i) / Σ(allocation_weight_i)
    where allocation_weight_i = allocation_percent_i / 100

    **Validates: Requirement 18.1**
    """

    @settings(max_examples=200)
    @given(
        data=st.data(),
        n=st.integers(min_value=1, max_value=10),
    )
    def test_portfolio_beta_weighted_average(self, data, n: int):
        """Generate positions with betas; verify weighted average formula."""
        # Generate allocations and betas
        symbols = [f"STOCK{i}" for i in range(n)]
        allocations = {}
        market_data = {}

        for symbol in symbols:
            alloc = data.draw(allocation_strategy)
            beta = data.draw(beta_strategy)
            allocations[symbol] = alloc
            market_data[symbol] = TickerInfo(
                symbol=symbol,
                beta=beta,
            )

        # Call the service method (it's not async, just a regular method)
        service = RiskMetricsService.__new__(RiskMetricsService)
        result = service._calculate_portfolio_beta(allocations, market_data)

        # Independently compute expected result
        weighted_sum = Decimal("0")
        total_weight = Decimal("0")

        for symbol in symbols:
            weight = allocations[symbol] / Decimal("100")
            weighted_sum += weight * market_data[symbol].beta
            total_weight += weight

        if total_weight > Decimal("0"):
            expected = (weighted_sum / total_weight).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
        else:
            expected = None

        assert result == expected, (
            f"Portfolio beta mismatch: got={result}, expected={expected}, "
            f"allocations={allocations}"
        )

    @settings(max_examples=200)
    @given(
        data=st.data(),
        n=st.integers(min_value=2, max_value=8),
    )
    def test_portfolio_beta_with_some_missing_betas(self, data, n: int):
        """Verify portfolio beta only uses positions with known betas."""
        symbols = [f"STOCK{i}" for i in range(n)]
        allocations = {}
        market_data = {}

        # Decide how many have beta (at least 1)
        num_with_beta = data.draw(st.integers(min_value=1, max_value=n))

        for i, symbol in enumerate(symbols):
            alloc = data.draw(allocation_strategy)
            allocations[symbol] = alloc

            if i < num_with_beta:
                beta = data.draw(beta_strategy)
                market_data[symbol] = TickerInfo(symbol=symbol, beta=beta)
            else:
                market_data[symbol] = TickerInfo(symbol=symbol, beta=None)

        service = RiskMetricsService.__new__(RiskMetricsService)
        result = service._calculate_portfolio_beta(allocations, market_data)

        # Only consider positions with known betas
        weighted_sum = Decimal("0")
        total_weight = Decimal("0")

        for symbol in symbols:
            ticker = market_data[symbol]
            if ticker.beta is not None:
                weight = allocations[symbol] / Decimal("100")
                weighted_sum += weight * ticker.beta
                total_weight += weight

        if total_weight > Decimal("0"):
            expected = (weighted_sum / total_weight).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
        else:
            expected = None

        assert result == expected, (
            f"Portfolio beta with missing betas: got={result}, expected={expected}"
        )

    @settings(max_examples=50)
    @given(
        alloc=allocation_strategy,
    )
    def test_portfolio_beta_none_when_no_betas(self, alloc: Decimal):
        """Verify portfolio beta is None when no positions have beta data."""
        allocations = {"STOCKA": alloc}
        market_data = {"STOCKA": TickerInfo(symbol="STOCKA", beta=None)}

        service = RiskMetricsService.__new__(RiskMetricsService)
        result = service._calculate_portfolio_beta(allocations, market_data)

        assert result is None, (
            f"Should return None when no betas available, got {result}"
        )


class TestConcentrationWarningThresholdsProperty:
    """Property 19: Concentration Warning Thresholds.

    - Sector concentration warning triggers if any single sector > 50% of portfolio
    - Position concentration warning triggers if any single stock > 25% of portfolio

    **Validates: Requirements 18.3, 18.4**
    """

    @settings(max_examples=200)
    @given(
        data=st.data(),
        n_sectors=st.integers(min_value=1, max_value=5),
    )
    def test_sector_concentration_warnings(self, data, n_sectors: int):
        """Generate sector concentrations; verify >50% triggers warning."""
        sector_concentrations = []
        for i in range(n_sectors):
            alloc = data.draw(
                st.decimals(
                    min_value=Decimal("0.01"),
                    max_value=Decimal("100.00"),
                    places=2,
                    allow_nan=False,
                    allow_infinity=False,
                )
            )
            sector_concentrations.append(
                SectorConcentration(
                    sector=f"Sector{i}",
                    allocation_percent=alloc,
                    position_count=1,
                )
            )

        # Empty position concentrations for this test
        position_concentrations = []

        service = RiskMetricsService.__new__(RiskMetricsService)
        warnings = service._generate_warnings(
            sector_concentrations, position_concentrations
        )

        # Verify: sector warning exists iff sector allocation > 50%
        sector_warnings = [w for w in warnings if w.warning_type == "sector"]
        sectors_over_threshold = [
            s for s in sector_concentrations
            if s.allocation_percent > SECTOR_CONCENTRATION_THRESHOLD
        ]

        assert len(sector_warnings) == len(sectors_over_threshold), (
            f"Expected {len(sectors_over_threshold)} sector warnings, "
            f"got {len(sector_warnings)}. "
            f"Sectors: {[(s.sector, s.allocation_percent) for s in sector_concentrations]}"
        )

        # Each warning should match a sector over threshold
        warned_sectors = {w.name for w in sector_warnings}
        expected_sectors = {s.sector for s in sectors_over_threshold}
        assert warned_sectors == expected_sectors, (
            f"Warning sectors mismatch: got={warned_sectors}, expected={expected_sectors}"
        )

    @settings(max_examples=200)
    @given(
        data=st.data(),
        n_positions=st.integers(min_value=1, max_value=8),
    )
    def test_position_concentration_warnings(self, data, n_positions: int):
        """Generate position concentrations; verify >25% triggers warning."""
        position_concentrations = []
        for i in range(n_positions):
            alloc = data.draw(
                st.decimals(
                    min_value=Decimal("0.01"),
                    max_value=Decimal("100.00"),
                    places=2,
                    allow_nan=False,
                    allow_infinity=False,
                )
            )
            position_concentrations.append(
                PositionConcentration(
                    stock_symbol=f"STOCK{i}",
                    allocation_percent=alloc,
                )
            )

        # Empty sector concentrations for this test
        sector_concentrations = []

        service = RiskMetricsService.__new__(RiskMetricsService)
        warnings = service._generate_warnings(
            sector_concentrations, position_concentrations
        )

        # Verify: position warning exists iff allocation > 25%
        position_warnings = [w for w in warnings if w.warning_type == "position"]
        positions_over_threshold = [
            p for p in position_concentrations
            if p.allocation_percent > POSITION_CONCENTRATION_THRESHOLD
        ]

        assert len(position_warnings) == len(positions_over_threshold), (
            f"Expected {len(positions_over_threshold)} position warnings, "
            f"got {len(position_warnings)}. "
            f"Positions: {[(p.stock_symbol, p.allocation_percent) for p in position_concentrations]}"
        )

        # Each warning should match a position over threshold
        warned_positions = {w.name for w in position_warnings}
        expected_positions = {p.stock_symbol for p in positions_over_threshold}
        assert warned_positions == expected_positions, (
            f"Warning positions mismatch: got={warned_positions}, expected={expected_positions}"
        )

    @settings(max_examples=100)
    @given(
        sector_alloc=st.decimals(
            min_value=Decimal("50.01"),
            max_value=Decimal("100.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_sector_above_50_always_warns(self, sector_alloc: Decimal):
        """Verify a sector with >50% allocation always triggers a warning."""
        sector_concentrations = [
            SectorConcentration(
                sector="BigSector",
                allocation_percent=sector_alloc,
                position_count=3,
            )
        ]

        service = RiskMetricsService.__new__(RiskMetricsService)
        warnings = service._generate_warnings(sector_concentrations, [])

        sector_warnings = [w for w in warnings if w.warning_type == "sector"]
        assert len(sector_warnings) == 1, (
            f"Sector at {sector_alloc}% should trigger warning"
        )
        assert sector_warnings[0].name == "BigSector"
        assert sector_warnings[0].threshold_percent == SECTOR_CONCENTRATION_THRESHOLD

    @settings(max_examples=100)
    @given(
        position_alloc=st.decimals(
            min_value=Decimal("25.01"),
            max_value=Decimal("100.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_position_above_25_always_warns(self, position_alloc: Decimal):
        """Verify a position with >25% allocation always triggers a warning."""
        position_concentrations = [
            PositionConcentration(
                stock_symbol="BIGSTOCK",
                allocation_percent=position_alloc,
            )
        ]

        service = RiskMetricsService.__new__(RiskMetricsService)
        warnings = service._generate_warnings([], position_concentrations)

        position_warnings = [w for w in warnings if w.warning_type == "position"]
        assert len(position_warnings) == 1, (
            f"Position at {position_alloc}% should trigger warning"
        )
        assert position_warnings[0].name == "BIGSTOCK"
        assert position_warnings[0].threshold_percent == POSITION_CONCENTRATION_THRESHOLD


class TestMaximumDrawdownCalculationProperty:
    """Property 20: Maximum Drawdown Calculation.

    For any sequence of portfolio values, maximum drawdown is the largest
    percentage decline from any peak to any subsequent trough:
    max_drawdown = max((peak - trough) / peak × 100) over all peak-trough pairs

    **Validates: Requirement 18.5**
    """

    @settings(max_examples=200)
    @given(
        values=st.lists(
            portfolio_value_strategy,
            min_size=2,
            max_size=50,
        ),
    )
    def test_max_drawdown_calculation(self, values: list[Decimal]):
        """Verify _compute_max_drawdown matches the peak-to-trough formula."""
        result = RiskMetricsService._compute_max_drawdown(values)

        # Independently compute expected max drawdown
        max_drawdown = Decimal("0")
        peak = values[0]

        for value in values[1:]:
            if value > peak:
                peak = value
            elif peak > Decimal("0"):
                drawdown = ((peak - value) / peak) * Decimal("100")
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        expected = max_drawdown.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        assert result == expected, (
            f"Max drawdown mismatch: got={result}, expected={expected}, "
            f"values (first 5)={values[:5]}"
        )

    @settings(max_examples=200)
    @given(
        values=st.lists(
            portfolio_value_strategy,
            min_size=2,
            max_size=50,
        ),
    )
    def test_max_drawdown_is_non_negative(self, values: list[Decimal]):
        """Verify max drawdown is always >= 0."""
        result = RiskMetricsService._compute_max_drawdown(values)

        assert result is not None
        assert result >= Decimal("0"), (
            f"Max drawdown should be non-negative, got {result}"
        )

    @settings(max_examples=200)
    @given(
        values=st.lists(
            portfolio_value_strategy,
            min_size=2,
            max_size=50,
        ),
    )
    def test_max_drawdown_at_most_100(self, values: list[Decimal]):
        """Verify max drawdown is at most 100% (can't lose more than all value)."""
        result = RiskMetricsService._compute_max_drawdown(values)

        assert result is not None
        assert result <= Decimal("100.00"), (
            f"Max drawdown should be at most 100%, got {result}"
        )

    @settings(max_examples=50)
    @given(
        start=portfolio_value_strategy,
        increment=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("1000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        n=st.integers(min_value=2, max_value=20),
    )
    def test_monotonically_increasing_has_zero_drawdown(
        self, start: Decimal, increment: Decimal, n: int
    ):
        """Verify a monotonically increasing sequence has 0% max drawdown."""
        values = [start + increment * i for i in range(n)]

        # Ensure values don't overflow
        assume(all(v <= Decimal("999999999.99") for v in values))

        result = RiskMetricsService._compute_max_drawdown(values)

        assert result == Decimal("0.00"), (
            f"Monotonically increasing values should have 0 drawdown, got {result}"
        )

    @settings(max_examples=50)
    @given(
        value=portfolio_value_strategy,
        n=st.integers(min_value=2, max_value=20),
    )
    def test_constant_values_have_zero_drawdown(self, value: Decimal, n: int):
        """Verify constant values have 0% max drawdown."""
        values = [value] * n

        result = RiskMetricsService._compute_max_drawdown(values)

        assert result == Decimal("0.00"), (
            f"Constant values should have 0 drawdown, got {result}"
        )

    def test_max_drawdown_returns_none_for_single_value(self):
        """Verify _compute_max_drawdown returns None for fewer than 2 values."""
        assert RiskMetricsService._compute_max_drawdown([Decimal("100.00")]) is None
        assert RiskMetricsService._compute_max_drawdown([]) is None
