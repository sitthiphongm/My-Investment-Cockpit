"""Unit tests for RebalancingService."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.enums import TargetType
from app.schemas.rebalancing import (
    RebalancingResponse,
    TargetAllocationEntry,
    TargetAllocationUpdate,
)
from app.services.rebalancing_service import RebalancingService


class FakeTargetAllocation:
    """Fake TargetAllocation ORM object."""

    def __init__(self, target_key: str, target_type: str, target_percentage: Decimal):
        self.id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.target_key = target_key
        self.target_type = target_type
        self.target_percentage = target_percentage


class FakeResult:
    """Fake SQLAlchemy result wrapper."""

    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value


class TestSetTargetAllocations:
    """Test setting target allocations (must sum to 100%)."""

    @pytest.mark.asyncio
    async def test_set_targets_replaces_existing(self):
        """Setting targets replaces all existing allocations."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=None)
        db.add = MagicMock()
        db.flush = AsyncMock()

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        data = TargetAllocationUpdate(
            targets=[
                TargetAllocationEntry(
                    target_key="AAPL",
                    target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("60.00"),
                ),
                TargetAllocationEntry(
                    target_key="META",
                    target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("40.00"),
                ),
            ]
        )

        result = await service.set_target_allocations(user_id, data)

        assert len(result) == 2
        # Verify db.execute called for delete, and db.add called twice
        assert db.execute.called
        assert db.add.call_count == 2
        assert db.flush.called

    @pytest.mark.asyncio
    async def test_set_single_target_100_percent(self):
        """Single target with 100% is valid."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=None)
        db.add = MagicMock()
        db.flush = AsyncMock()

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        data = TargetAllocationUpdate(
            targets=[
                TargetAllocationEntry(
                    target_key="AAPL",
                    target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("100.00"),
                ),
            ]
        )

        result = await service.set_target_allocations(user_id, data)
        assert len(result) == 1
        assert result[0].target_percentage == Decimal("100.00")


class TestTargetAllocationValidation:
    """Test that Pydantic schema validates targets sum to 100%."""

    def test_targets_sum_to_100_valid(self):
        """Targets that sum to exactly 100% pass validation."""
        data = TargetAllocationUpdate(
            targets=[
                TargetAllocationEntry(
                    target_key="AAPL",
                    target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("50.00"),
                ),
                TargetAllocationEntry(
                    target_key="META",
                    target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("50.00"),
                ),
            ]
        )
        assert sum(t.target_percentage for t in data.targets) == Decimal("100.00")

    def test_targets_not_summing_to_100_rejected(self):
        """Targets that don't sum to 100% are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            TargetAllocationUpdate(
                targets=[
                    TargetAllocationEntry(
                        target_key="AAPL",
                        target_type=TargetType.SYMBOL,
                        target_percentage=Decimal("60.00"),
                    ),
                    TargetAllocationEntry(
                        target_key="META",
                        target_type=TargetType.SYMBOL,
                        target_percentage=Decimal("30.00"),
                    ),
                ]
            )

        assert "100%" in str(exc_info.value)

    def test_targets_exceeding_100_rejected(self):
        """Targets summing to more than 100% are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TargetAllocationUpdate(
                targets=[
                    TargetAllocationEntry(
                        target_key="AAPL",
                        target_type=TargetType.SYMBOL,
                        target_percentage=Decimal("70.00"),
                    ),
                    TargetAllocationEntry(
                        target_key="META",
                        target_type=TargetType.SYMBOL,
                        target_percentage=Decimal("50.00"),
                    ),
                ]
            )


class TestGetRebalancingInsights:
    """Test rebalancing insights comparison logic."""

    @pytest.mark.asyncio
    async def test_no_targets_returns_empty(self):
        """When no targets are set, returns empty positions list."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={"AAPL": Decimal("100.00")},
            current_prices={"AAPL": Decimal("150.00")},
            position_quantities={"AAPL": 100},
            total_portfolio_value=Decimal("15000.00"),
        )

        assert result.positions == []
        assert result.deviation_threshold == Decimal("5.00")

    @pytest.mark.asyncio
    async def test_balanced_portfolio_no_flags(self):
        """Portfolio within threshold has no over/under-weight flags."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("50.00")),
            FakeTargetAllocation("META", "Symbol", Decimal("50.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "AAPL": Decimal("52.00"),
                "META": Decimal("48.00"),
            },
            current_prices={
                "AAPL": Decimal("150.00"),
                "META": Decimal("300.00"),
            },
            position_quantities={"AAPL": 100, "META": 50},
            total_portfolio_value=Decimal("30000.00"),
        )

        assert len(result.positions) == 2
        for pos in result.positions:
            assert pos.is_overweight is False
            assert pos.is_underweight is False
            assert pos.suggested_action is None

    @pytest.mark.asyncio
    async def test_overweight_position_flagged(self):
        """Position over threshold is flagged as overweight."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("40.00")),
            FakeTargetAllocation("META", "Symbol", Decimal("60.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # AAPL current=50%, target=40%, difference=+10pp (> 5pp threshold)
        # META current=50%, target=60%, difference=-10pp (< -5pp threshold)
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "AAPL": Decimal("50.00"),
                "META": Decimal("50.00"),
            },
            current_prices={
                "AAPL": Decimal("100.00"),
                "META": Decimal("200.00"),
            },
            position_quantities={"AAPL": 100, "META": 50},
            total_portfolio_value=Decimal("20000.00"),
        )

        aapl = next(p for p in result.positions if p.target_key == "AAPL")
        meta = next(p for p in result.positions if p.target_key == "META")

        assert aapl.is_overweight is True
        assert aapl.is_underweight is False
        assert aapl.difference == Decimal("10.00")

        assert meta.is_overweight is False
        assert meta.is_underweight is True
        assert meta.difference == Decimal("-10.00")

    @pytest.mark.asyncio
    async def test_underweight_position_flagged(self):
        """Position below threshold is flagged as underweight."""
        targets = [
            FakeTargetAllocation("DRAM", "Symbol", Decimal("70.00")),
            FakeTargetAllocation("RGNX", "Symbol", Decimal("30.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # DRAM current=50%, target=70%, difference=-20pp (< -5pp threshold)
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "DRAM": Decimal("50.00"),
                "RGNX": Decimal("50.00"),
            },
            current_prices={
                "DRAM": Decimal("10.00"),
                "RGNX": Decimal("25.00"),
            },
            position_quantities={"DRAM": 500, "RGNX": 200},
            total_portfolio_value=Decimal("10000.00"),
        )

        dram = next(p for p in result.positions if p.target_key == "DRAM")
        assert dram.is_underweight is True
        assert dram.is_overweight is False
        assert dram.difference == Decimal("-20.00")

    @pytest.mark.asyncio
    async def test_custom_deviation_threshold(self):
        """Custom deviation threshold changes flagging behavior."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("50.00")),
            FakeTargetAllocation("META", "Symbol", Decimal("50.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # AAPL current=53%, difference=+3pp
        # With 5pp threshold: not flagged
        # With 2pp threshold: flagged as overweight
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "AAPL": Decimal("53.00"),
                "META": Decimal("47.00"),
            },
            current_prices={
                "AAPL": Decimal("150.00"),
                "META": Decimal("300.00"),
            },
            position_quantities={"AAPL": 100, "META": 50},
            total_portfolio_value=Decimal("30000.00"),
            deviation_threshold=Decimal("2.00"),
        )

        aapl = next(p for p in result.positions if p.target_key == "AAPL")
        meta = next(p for p in result.positions if p.target_key == "META")

        assert aapl.is_overweight is True
        assert meta.is_underweight is True


class TestBuySellSuggestions:
    """Test suggested buy/sell actions to reach target allocation."""

    @pytest.mark.asyncio
    async def test_buy_suggestion_for_underweight(self):
        """Underweight symbol gets a buy suggestion."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("60.00")),
            FakeTargetAllocation("META", "Symbol", Decimal("40.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # AAPL: current=40%, target=60%, diff=-20pp (underweight)
        # Portfolio value = 10000
        # Target value for AAPL = 60% * 10000 = 6000
        # Current value for AAPL = 40% * 10000 = 4000
        # Value diff = 6000 - 4000 = 2000
        # At price 100, need to buy 2000/100 = 20 shares
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "AAPL": Decimal("40.00"),
                "META": Decimal("60.00"),
            },
            current_prices={
                "AAPL": Decimal("100.00"),
                "META": Decimal("200.00"),
            },
            position_quantities={"AAPL": 40, "META": 30},
            total_portfolio_value=Decimal("10000.00"),
        )

        aapl = next(p for p in result.positions if p.target_key == "AAPL")
        assert aapl.suggested_action == "Buy 20 shares"

    @pytest.mark.asyncio
    async def test_sell_suggestion_for_overweight(self):
        """Overweight symbol gets a sell suggestion."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("30.00")),
            FakeTargetAllocation("META", "Symbol", Decimal("70.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # AAPL: current=50%, target=30%, diff=+20pp (overweight)
        # Portfolio value = 20000
        # Target value for AAPL = 30% * 20000 = 6000
        # Current value for AAPL = 50% * 20000 = 10000
        # Value diff = 6000 - 10000 = -4000
        # At price 100, need to sell abs(-4000)/100 = 40 shares
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "AAPL": Decimal("50.00"),
                "META": Decimal("50.00"),
            },
            current_prices={
                "AAPL": Decimal("100.00"),
                "META": Decimal("200.00"),
            },
            position_quantities={"AAPL": 100, "META": 50},
            total_portfolio_value=Decimal("20000.00"),
        )

        aapl = next(p for p in result.positions if p.target_key == "AAPL")
        assert aapl.suggested_action == "Sell 40 shares"

    @pytest.mark.asyncio
    async def test_no_suggestion_within_threshold(self):
        """Positions within threshold get no suggestion."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("50.00")),
            FakeTargetAllocation("META", "Symbol", Decimal("50.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "AAPL": Decimal("51.00"),
                "META": Decimal("49.00"),
            },
            current_prices={
                "AAPL": Decimal("150.00"),
                "META": Decimal("300.00"),
            },
            position_quantities={"AAPL": 100, "META": 50},
            total_portfolio_value=Decimal("30000.00"),
        )

        for pos in result.positions:
            assert pos.suggested_action is None

    @pytest.mark.asyncio
    async def test_suggestion_when_price_unavailable(self):
        """When price is unavailable, generic suggestion is given."""
        targets = [
            FakeTargetAllocation("XYZ", "Symbol", Decimal("100.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # XYZ: current=0% (not held), target=100%, difference=-100pp
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={},
            current_prices={"XYZ": None},
            position_quantities={},
            total_portfolio_value=Decimal("10000.00"),
        )

        xyz = result.positions[0]
        assert xyz.is_underweight is True
        assert "price unavailable" in xyz.suggested_action

    @pytest.mark.asyncio
    async def test_sector_target_suggestion(self):
        """Sector-based targets get sector-specific suggestions."""
        targets = [
            FakeTargetAllocation("Technology", "Sector", Decimal("60.00")),
            FakeTargetAllocation("Healthcare", "Sector", Decimal("40.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)
        user_id = uuid.uuid4()

        # Technology: current=80%, target=60%, diff=+20pp (overweight)
        result = await service.get_rebalancing_insights(
            user_id=user_id,
            current_allocations={
                "Technology": Decimal("80.00"),
                "Healthcare": Decimal("20.00"),
            },
            current_prices={},
            position_quantities={},
            total_portfolio_value=Decimal("50000.00"),
        )

        tech = next(p for p in result.positions if p.target_key == "Technology")
        assert tech.is_overweight is True
        assert "Reduce sector allocation" in tech.suggested_action
        assert "20.00" in tech.suggested_action


class TestDifferenceCalculation:
    """Test difference = current - target calculation."""

    @pytest.mark.asyncio
    async def test_positive_difference(self):
        """Positive difference when current > target."""
        targets = [
            FakeTargetAllocation("AAPL", "Symbol", Decimal("100.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)

        result = await service.get_rebalancing_insights(
            user_id=uuid.uuid4(),
            current_allocations={"AAPL": Decimal("100.00")},
            current_prices={"AAPL": Decimal("150.00")},
            position_quantities={"AAPL": 100},
            total_portfolio_value=Decimal("15000.00"),
        )

        assert result.positions[0].difference == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_missing_current_allocation_uses_zero(self):
        """If symbol has no current allocation, uses 0%."""
        targets = [
            FakeTargetAllocation("XYZ", "Symbol", Decimal("100.00")),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(targets))

        service = RebalancingService(db)

        result = await service.get_rebalancing_insights(
            user_id=uuid.uuid4(),
            current_allocations={},  # XYZ not in current portfolio
            current_prices={},
            position_quantities={},
            total_portfolio_value=Decimal("10000.00"),
        )

        pos = result.positions[0]
        assert pos.current_allocation == Decimal("0.00")
        assert pos.target_allocation == Decimal("100.00")
        assert pos.difference == Decimal("-100.00")
        assert pos.is_underweight is True
