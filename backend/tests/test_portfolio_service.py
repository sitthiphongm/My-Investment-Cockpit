"""Unit tests for PortfolioService."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.enums import SentimentType
from app.schemas.market_data import TickerInfo
from app.services.portfolio_service import PortfolioService


class FakeRow:
    """Fake SQLAlchemy row for aggregate queries."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name):
        return None


class FakeResult:
    """Fake SQLAlchemy result wrapper."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def one(self):
        return self._value

    def all(self):
        return self._value

    def scalars(self):
        return self


class FakeMarketDataService:
    """Fake MarketDataService that returns configurable prices."""

    def __init__(self, prices: dict[str, Decimal]):
        self.prices = prices

    async def get_ticker_info(self, symbol: str) -> TickerInfo:
        price = self.prices.get(symbol.upper())
        return TickerInfo(
            symbol=symbol.upper(),
            current_price=price,
            long_name=f"{symbol} Inc.",
            sector="Technology",
            industry="Software",
            last_refresh=datetime.now(timezone.utc) if price else None,
            is_stale=price is None,
        )


class TestCalculateAvgCost:
    """Test avg_cost = Σ(qty × price) / Σ(qty) for Buy + Snapshot."""

    @pytest.mark.asyncio
    async def test_simple_avg_cost(self):
        """Average cost with single buy: avg_cost = price."""
        db = AsyncMock()
        # total_cost = 100 * 25.00 = 2500, total_qty = 100
        row = FakeRow(total_cost=Decimal("2500.00"), total_qty=100)
        db.execute = AsyncMock(return_value=FakeResult(row))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_avg_cost(uuid.uuid4(), "AAPL")
        assert result == Decimal("25.00")

    @pytest.mark.asyncio
    async def test_weighted_avg_cost_multiple_buys(self):
        """Average cost with multiple buys at different prices."""
        db = AsyncMock()
        # Buy 100 @ 20.00 = 2000, Buy 200 @ 30.00 = 6000
        # Total cost = 8000, Total qty = 300
        # Avg = 8000/300 = 26.67
        row = FakeRow(total_cost=Decimal("8000.00"), total_qty=300)
        db.execute = AsyncMock(return_value=FakeResult(row))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_avg_cost(uuid.uuid4(), "META")
        assert result == Decimal("26.67")

    @pytest.mark.asyncio
    async def test_avg_cost_with_snapshots(self):
        """Snapshot entries contribute to avg cost calculation."""
        db = AsyncMock()
        # Buy 50 @ 10.00 = 500, Snapshot 150 @ 12.00 = 1800
        # Total cost = 2300, Total qty = 200
        # Avg = 2300/200 = 11.50
        row = FakeRow(total_cost=Decimal("2300.00"), total_qty=200)
        db.execute = AsyncMock(return_value=FakeResult(row))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_avg_cost(uuid.uuid4(), "DRAM")
        assert result == Decimal("11.50")

    @pytest.mark.asyncio
    async def test_avg_cost_no_entries_returns_zero(self):
        """If no buy/snapshot entries, avg_cost = 0."""
        db = AsyncMock()
        row = FakeRow(total_cost=None, total_qty=None)
        db.execute = AsyncMock(return_value=FakeResult(row))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_avg_cost(uuid.uuid4(), "XYZ")
        assert result == Decimal("0.00")


class TestCalculateAllocation:
    """Test allocation = (position_cost / total_cost) × 100."""

    @pytest.mark.asyncio
    async def test_single_position_100_percent(self):
        """Single position gets 100% allocation."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # Mock _get_positions_with_holdings: one stock with 100 shares
        positions_result = [FakeRow(stock_symbol="AAPL", holdings=100)]
        # Mock calculate_avg_cost: avg_cost = 50.00
        avg_cost_row = FakeRow(total_cost=Decimal("5000.00"), total_qty=100)

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            return FakeResult(avg_cost_row)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"AAPL": Decimal("55.00")})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_allocation(user_id)
        assert result == {"AAPL": Decimal("100.00")}

    @pytest.mark.asyncio
    async def test_two_equal_positions_50_each(self):
        """Two equal-cost positions get 50% each."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # Both positions have total_cost = 1000 (qty=100, avg=10)
        positions_result = [
            FakeRow(stock_symbol="AAPL", holdings=100),
            FakeRow(stock_symbol="META", holdings=100),
        ]
        avg_cost_row = FakeRow(total_cost=Decimal("1000.00"), total_qty=100)

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            return FakeResult(avg_cost_row)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"AAPL": Decimal("15.00"), "META": Decimal("12.00")})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_allocation(user_id)
        assert result["AAPL"] == Decimal("50.00")
        assert result["META"] == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_empty_portfolio_returns_empty(self):
        """Empty portfolio returns empty allocation dict."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.calculate_allocation(uuid.uuid4())
        assert result == {}


class TestUnrealizedPL:
    """Test unrealized P/L = market_value - total_cost."""

    @pytest.mark.asyncio
    async def test_positive_pl(self):
        """Positive unrealized P/L when market price > avg cost."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # Position: 100 shares, avg_cost=20.00, current_price=25.00
        positions_result = [FakeRow(stock_symbol="AAPL", holdings=100)]
        avg_cost_row = FakeRow(total_cost=Decimal("2000.00"), total_qty=100)
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                return FakeResult(avg_cost_row)
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"AAPL": Decimal("25.00")})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)

        assert len(summary.positions) == 1
        pos = summary.positions[0]
        # market_value = 100 * 25 = 2500
        assert pos.market_value == Decimal("2500.00")
        # total_cost = 100 * 20 = 2000
        assert pos.total_cost == Decimal("2000.00")
        # unrealized_pl = 2500 - 2000 = 500
        assert pos.unrealized_pl == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_negative_pl(self):
        """Negative unrealized P/L when market price < avg cost."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # Position: 200 shares, avg_cost=30.00, current_price=25.00
        positions_result = [FakeRow(stock_symbol="META", holdings=200)]
        avg_cost_row = FakeRow(total_cost=Decimal("6000.00"), total_qty=200)
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                return FakeResult(avg_cost_row)
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"META": Decimal("25.00")})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)

        pos = summary.positions[0]
        # market_value = 200 * 25 = 5000
        assert pos.market_value == Decimal("5000.00")
        # total_cost = 200 * 30 = 6000
        assert pos.total_cost == Decimal("6000.00")
        # unrealized_pl = 5000 - 6000 = -1000
        assert pos.unrealized_pl == Decimal("-1000.00")


class TestROIPercent:
    """Test ROI% = (unrealized_pl / total_cost) × 100."""

    @pytest.mark.asyncio
    async def test_positive_roi(self):
        """Positive ROI when stock is up."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # 100 shares, avg_cost=10, current_price=15
        # total_cost=1000, market_value=1500, unrealized_pl=500
        # roi = (500/1000) * 100 = 50.00%
        positions_result = [FakeRow(stock_symbol="DRAM", holdings=100)]
        avg_cost_row = FakeRow(total_cost=Decimal("1000.00"), total_qty=100)
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                return FakeResult(avg_cost_row)
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"DRAM": Decimal("15.00")})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)
        pos = summary.positions[0]

        assert pos.roi_percent == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_negative_roi(self):
        """Negative ROI when stock is down."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # 100 shares, avg_cost=20, current_price=15
        # total_cost=2000, market_value=1500, unrealized_pl=-500
        # roi = (-500/2000) * 100 = -25.00%
        positions_result = [FakeRow(stock_symbol="RGNX", holdings=100)]
        avg_cost_row = FakeRow(total_cost=Decimal("2000.00"), total_qty=100)
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                return FakeResult(avg_cost_row)
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"RGNX": Decimal("15.00")})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)
        pos = summary.positions[0]

        assert pos.roi_percent == Decimal("-25.00")


class TestAggregateTotals:
    """Test that totals row aggregates all positions correctly."""

    @pytest.mark.asyncio
    async def test_totals_two_positions(self):
        """Total cost, market value, and P/L aggregate across positions."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # AAPL: 100 shares, avg=20, price=25 → cost=2000, mv=2500, pl=500
        # META: 200 shares, avg=10, price=12 → cost=2000, mv=2400, pl=400
        # Totals: cost=4000, mv=4900, pl=900, roi=22.50%
        positions_result = [
            FakeRow(stock_symbol="AAPL", holdings=100),
            FakeRow(stock_symbol="META", holdings=200),
        ]
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                # avg_cost for AAPL: 2000/100 = 20
                return FakeResult(FakeRow(total_cost=Decimal("2000.00"), total_qty=100))
            elif call_count[0] == 3:
                # avg_cost for META: 2000/200 = 10
                return FakeResult(FakeRow(total_cost=Decimal("2000.00"), total_qty=200))
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({
            "AAPL": Decimal("25.00"),
            "META": Decimal("12.00"),
        })
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)

        assert summary.total_cost == Decimal("4000.00")
        assert summary.total_market_value == Decimal("4900.00")
        assert summary.total_unrealized_pl == Decimal("900.00")
        assert summary.overall_roi_percent == Decimal("22.50")
        assert summary.market_data_complete is True


class TestZeroQuantityExclusion:
    """Test that zero-quantity positions are excluded from the summary."""

    @pytest.mark.asyncio
    async def test_zero_quantity_excluded(self):
        """Positions with zero holdings don't appear in summary."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        # Only AAPL has holdings > 0 (the HAVING clause excludes zeros)
        positions_result = [FakeRow(stock_symbol="AAPL", holdings=50)]
        avg_cost_row = FakeRow(total_cost=Decimal("500.00"), total_qty=50)
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                return FakeResult(avg_cost_row)
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        market_svc = FakeMarketDataService({"AAPL": Decimal("12.00")})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)

        # Only one position returned (zero-quantity filtered out by SQL HAVING)
        assert len(summary.positions) == 1
        assert summary.positions[0].stock_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_all_zero_returns_empty(self):
        """If all positions are zero, returns empty portfolio."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(uuid.uuid4())

        assert summary.positions == []
        assert summary.total_cost == Decimal("0.00")


class TestSentiment:
    """Test set/get sentiment per stock."""

    @pytest.mark.asyncio
    async def test_set_sentiment_new(self):
        """Setting sentiment on a new stock creates a record."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))
        db.add = MagicMock()
        db.flush = AsyncMock()

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        await service.set_sentiment(uuid.uuid4(), "AAPL", "Bull")

        assert db.add.called
        added_obj = db.add.call_args[0][0]
        assert added_obj.sentiment == "Bull"
        assert added_obj.stock_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_set_sentiment_update_existing(self):
        """Updating sentiment on existing record modifies it."""
        db = AsyncMock()
        existing = MagicMock()
        existing.sentiment = "Bear"
        db.execute = AsyncMock(return_value=FakeResult(existing))
        db.flush = AsyncMock()

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        await service.set_sentiment(uuid.uuid4(), "AAPL", "Bull")

        assert existing.sentiment == "Bull"

    @pytest.mark.asyncio
    async def test_set_invalid_sentiment_rejected(self):
        """Setting invalid sentiment raises HTTPException."""
        db = AsyncMock()
        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        with pytest.raises(HTTPException) as exc_info:
            await service.set_sentiment(uuid.uuid4(), "AAPL", "Neutral")

        assert exc_info.value.status_code == 400
        assert "Invalid sentiment" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_sentiment_returns_value(self):
        """Getting sentiment returns the stored value."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult("Bull"))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.get_sentiment(uuid.uuid4(), "AAPL")
        assert result == SentimentType.BULL

    @pytest.mark.asyncio
    async def test_get_sentiment_not_set_returns_none(self):
        """Getting sentiment when not set returns None."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))

        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        result = await service.get_sentiment(uuid.uuid4(), "AAPL")
        assert result is None


class TestMissingMarketData:
    """Test behavior when market data is unavailable."""

    @pytest.mark.asyncio
    async def test_no_price_leaves_mv_pl_none(self):
        """When current_price is None, market_value and P/L are None."""
        db = AsyncMock()
        user_id = uuid.uuid4()

        positions_result = [FakeRow(stock_symbol="XYZ", holdings=50)]
        avg_cost_row = FakeRow(total_cost=Decimal("500.00"), total_qty=50)
        sentiment_result = []

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResult(positions_result)
            elif call_count[0] == 2:
                return FakeResult(avg_cost_row)
            else:
                return FakeResult(sentiment_result)

        db.execute = mock_execute

        # No price for XYZ
        market_svc = FakeMarketDataService({})
        service = PortfolioService(db, market_svc)

        summary = await service.get_summary(user_id)

        pos = summary.positions[0]
        assert pos.market_value is None
        assert pos.unrealized_pl is None
        assert pos.roi_percent is None
        assert summary.market_data_complete is False
        assert summary.total_market_value is None
