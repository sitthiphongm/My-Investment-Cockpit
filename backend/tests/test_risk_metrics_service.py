"""Unit tests for RiskMetricsService."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.market_data import TickerInfo
from app.schemas.risk_metrics import RiskMetricsResponse
from app.services.risk_metrics_service import RiskMetricsService


class FakeRow:
    """Fake SQLAlchemy row for snapshot queries."""

    def __init__(self, value: Decimal):
        self._value = value

    def __getitem__(self, idx):
        return self._value


class FakeResult:
    """Fake SQLAlchemy result for execute()."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def make_ticker_info(symbol: str, beta=None, sector=None) -> TickerInfo:
    """Helper to create TickerInfo with specific fields."""
    return TickerInfo(
        symbol=symbol,
        beta=Decimal(str(beta)) if beta is not None else None,
        sector=sector,
    )


class TestPortfolioBeta:
    """Test portfolio beta calculation (weighted average by allocation)."""

    @pytest.mark.asyncio
    async def test_single_position_beta(self):
        """Single position: portfolio beta equals its beta."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {"AAPL": Decimal("100.00")}
        market_data = {"AAPL": make_ticker_info("AAPL", beta=1.2, sector="Technology")}

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        assert result.portfolio_beta == Decimal("1.20")

    @pytest.mark.asyncio
    async def test_two_positions_equal_weight(self):
        """Two equally weighted positions: beta is average of both betas."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("50.00"),
            "META": Decimal("50.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", beta=1.0, sector="Technology"),
            "META": make_ticker_info("META", beta=1.4, sector="Technology"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        # (0.5 * 1.0 + 0.5 * 1.4) / (0.5 + 0.5) = 1.2
        assert result.portfolio_beta == Decimal("1.20")

    @pytest.mark.asyncio
    async def test_weighted_beta_unequal_allocations(self):
        """Unequal allocations produce correctly weighted beta."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("70.00"),
            "META": Decimal("30.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", beta=1.0, sector="Technology"),
            "META": make_ticker_info("META", beta=2.0, sector="Technology"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        # (0.7 * 1.0 + 0.3 * 2.0) / (0.7 + 0.3) = 1.3
        assert result.portfolio_beta == Decimal("1.30")

    @pytest.mark.asyncio
    async def test_no_beta_data_returns_none(self):
        """If no positions have beta data, portfolio beta is None."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {"AAPL": Decimal("100.00")}
        market_data = {"AAPL": make_ticker_info("AAPL", beta=None, sector="Technology")}

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        assert result.portfolio_beta is None

    @pytest.mark.asyncio
    async def test_partial_beta_data_normalizes(self):
        """When only some positions have beta, result is normalized by their weight."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("60.00"),
            "XYZ": Decimal("40.00"),  # no beta
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", beta=1.5, sector="Technology"),
            "XYZ": make_ticker_info("XYZ", beta=None, sector="Unknown"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        # Only AAPL has beta. weight = 0.6, weighted_beta = 0.6 * 1.5 = 0.9
        # Normalized: 0.9 / 0.6 = 1.5
        assert result.portfolio_beta == Decimal("1.50")

    @pytest.mark.asyncio
    async def test_empty_portfolio_returns_none(self):
        """Empty portfolio returns None for beta."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.portfolio_beta is None


class TestSectorConcentration:
    """Test sector concentration calculation."""

    @pytest.mark.asyncio
    async def test_single_sector(self):
        """All positions in one sector = 100% concentration."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("60.00"),
            "MSFT": Decimal("40.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", beta=1.0, sector="Technology"),
            "MSFT": make_ticker_info("MSFT", beta=0.9, sector="Technology"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        assert len(result.sector_concentrations) == 1
        assert result.sector_concentrations[0].sector == "Technology"
        assert result.sector_concentrations[0].allocation_percent == Decimal("100.00")
        assert result.sector_concentrations[0].position_count == 2

    @pytest.mark.asyncio
    async def test_multiple_sectors(self):
        """Positions across sectors are grouped correctly."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("40.00"),
            "JNJ": Decimal("35.00"),
            "META": Decimal("25.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", beta=1.0, sector="Technology"),
            "JNJ": make_ticker_info("JNJ", beta=0.7, sector="Healthcare"),
            "META": make_ticker_info("META", beta=1.2, sector="Technology"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        assert len(result.sector_concentrations) == 2

        tech = next(s for s in result.sector_concentrations if s.sector == "Technology")
        health = next(s for s in result.sector_concentrations if s.sector == "Healthcare")

        assert tech.allocation_percent == Decimal("65.00")
        assert tech.position_count == 2
        assert health.allocation_percent == Decimal("35.00")
        assert health.position_count == 1

    @pytest.mark.asyncio
    async def test_unknown_sector_for_missing_data(self):
        """Positions without sector data are grouped under 'Unknown'."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {"XYZ": Decimal("100.00")}
        market_data = {"XYZ": make_ticker_info("XYZ", beta=None, sector=None)}

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        assert len(result.sector_concentrations) == 1
        assert result.sector_concentrations[0].sector == "Unknown"

    @pytest.mark.asyncio
    async def test_sector_concentration_sorted_descending(self):
        """Sector concentrations are sorted by allocation descending."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("20.00"),
            "JNJ": Decimal("50.00"),
            "XOM": Decimal("30.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", sector="Technology"),
            "JNJ": make_ticker_info("JNJ", sector="Healthcare"),
            "XOM": make_ticker_info("XOM", sector="Energy"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        allocs = [s.allocation_percent for s in result.sector_concentrations]
        assert allocs == sorted(allocs, reverse=True)


class TestConcentrationWarnings:
    """Test concentration warning generation."""

    @pytest.mark.asyncio
    async def test_sector_over_50_generates_warning(self):
        """Sector > 50% triggers a sector concentration warning."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("40.00"),
            "MSFT": Decimal("20.00"),
            "JNJ": Decimal("40.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", sector="Technology"),
            "MSFT": make_ticker_info("MSFT", sector="Technology"),
            "JNJ": make_ticker_info("JNJ", sector="Healthcare"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)

        sector_warnings = [w for w in result.warnings if w.warning_type == "sector"]
        assert len(sector_warnings) == 1
        assert sector_warnings[0].name == "Technology"
        assert sector_warnings[0].allocation_percent == Decimal("60.00")
        assert sector_warnings[0].threshold_percent == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_sector_at_50_no_warning(self):
        """Sector at exactly 50% does NOT trigger a warning (must be > 50%)."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("50.00"),
            "JNJ": Decimal("50.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", sector="Technology"),
            "JNJ": make_ticker_info("JNJ", sector="Healthcare"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        sector_warnings = [w for w in result.warnings if w.warning_type == "sector"]
        assert len(sector_warnings) == 0

    @pytest.mark.asyncio
    async def test_position_over_25_generates_warning(self):
        """Stock > 25% triggers a position concentration warning."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("30.00"),
            "META": Decimal("30.00"),
            "JNJ": Decimal("20.00"),
            "XOM": Decimal("20.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", sector="Technology"),
            "META": make_ticker_info("META", sector="Technology"),
            "JNJ": make_ticker_info("JNJ", sector="Healthcare"),
            "XOM": make_ticker_info("XOM", sector="Energy"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        position_warnings = [w for w in result.warnings if w.warning_type == "position"]
        assert len(position_warnings) == 2
        warning_names = {w.name for w in position_warnings}
        assert "AAPL" in warning_names
        assert "META" in warning_names

    @pytest.mark.asyncio
    async def test_position_at_25_no_warning(self):
        """Stock at exactly 25% does NOT trigger a warning (must be > 25%)."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("25.00"),
            "META": Decimal("25.00"),
            "JNJ": Decimal("25.00"),
            "XOM": Decimal("25.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", sector="Technology"),
            "META": make_ticker_info("META", sector="Technology"),
            "JNJ": make_ticker_info("JNJ", sector="Healthcare"),
            "XOM": make_ticker_info("XOM", sector="Energy"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        position_warnings = [w for w in result.warnings if w.warning_type == "position"]
        assert len(position_warnings) == 0

    @pytest.mark.asyncio
    async def test_no_warnings_balanced_portfolio(self):
        """Well-balanced portfolio has no warnings."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        allocations = {
            "AAPL": Decimal("20.00"),
            "META": Decimal("20.00"),
            "JNJ": Decimal("20.00"),
            "XOM": Decimal("20.00"),
            "BAC": Decimal("20.00"),
        }
        market_data = {
            "AAPL": make_ticker_info("AAPL", sector="Technology"),
            "META": make_ticker_info("META", sector="Communication"),
            "JNJ": make_ticker_info("JNJ", sector="Healthcare"),
            "XOM": make_ticker_info("XOM", sector="Energy"),
            "BAC": make_ticker_info("BAC", sector="Financial"),
        }

        result = await service.get_risk_metrics(user_id, allocations, market_data)
        assert len(result.warnings) == 0


class TestMaxDrawdown:
    """Test maximum drawdown calculation."""

    @pytest.mark.asyncio
    async def test_simple_drawdown(self):
        """A clear peak-to-trough decline is captured."""
        # Values: 100, 120, 90 => peak=120, trough=90, drawdown = (120-90)/120*100 = 25%
        values = [Decimal("100"), Decimal("120"), Decimal("90")]
        rows = [FakeRow(v) for v in values]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(rows))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.max_drawdown_percent == Decimal("25.00")

    @pytest.mark.asyncio
    async def test_no_drawdown_monotonic_increase(self):
        """Monotonically increasing values have zero drawdown."""
        values = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130")]
        rows = [FakeRow(v) for v in values]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(rows))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.max_drawdown_percent == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_multiple_drawdowns_returns_largest(self):
        """Multiple drawdowns: returns the largest one."""
        # Values: 100, 90, 110, 80
        # First drawdown: peak=100, trough=90 => 10%
        # Second drawdown: peak=110, trough=80 => (110-80)/110*100 = 27.27%
        values = [Decimal("100"), Decimal("90"), Decimal("110"), Decimal("80")]
        rows = [FakeRow(v) for v in values]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(rows))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.max_drawdown_percent == Decimal("27.27")

    @pytest.mark.asyncio
    async def test_fewer_than_2_snapshots_returns_none(self):
        """Fewer than 2 snapshots returns None for max drawdown."""
        rows = [FakeRow(Decimal("100"))]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(rows))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.max_drawdown_percent is None

    @pytest.mark.asyncio
    async def test_no_snapshots_returns_none(self):
        """No snapshots returns None for max drawdown."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.max_drawdown_percent is None

    @pytest.mark.asyncio
    async def test_full_decline_100_percent(self):
        """A decline to zero gives 100% drawdown."""
        values = [Decimal("100"), Decimal("0")]
        rows = [FakeRow(v) for v in values]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(rows))

        service = RiskMetricsService(db)
        user_id = uuid.uuid4()

        result = await service.get_risk_metrics(user_id, {}, {})
        assert result.max_drawdown_percent == Decimal("100.00")


class TestComputeMaxDrawdownStatic:
    """Test the static _compute_max_drawdown method directly."""

    def test_recovery_after_drawdown(self):
        """Peak is updated after recovery, then new drawdown measured from new peak."""
        # 100 -> 80 (20% dd) -> 150 (new peak) -> 120 (20% dd from 150)
        values = [Decimal("100"), Decimal("80"), Decimal("150"), Decimal("120")]
        result = RiskMetricsService._compute_max_drawdown(values)
        assert result == Decimal("20.00")

    def test_drawdown_at_end(self):
        """Drawdown that occurs at the very end of the series."""
        values = [Decimal("200"), Decimal("250"), Decimal("100")]
        # Peak=250, trough=100, drawdown = (250-100)/250*100 = 60%
        result = RiskMetricsService._compute_max_drawdown(values)
        assert result == Decimal("60.00")

    def test_single_value_returns_none(self):
        """Single value returns None."""
        result = RiskMetricsService._compute_max_drawdown([Decimal("100")])
        assert result is None

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        result = RiskMetricsService._compute_max_drawdown([])
        assert result is None
