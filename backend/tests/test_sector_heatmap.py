"""Tests for the sector heatmap backend endpoint."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_id
from app.redis import get_redis
from app.schemas.market_data import TickerInfo
from main import app


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


@pytest.fixture
def override_deps(user_id, mock_redis):
    """Override auth and redis dependencies."""
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_redis, None)


def _make_ticker(symbol: str, sector: str, current_price: Decimal) -> TickerInfo:
    """Create a TickerInfo with sector and price."""
    return TickerInfo(
        symbol=symbol,
        sector=sector,
        current_price=current_price,
    )


@pytest.mark.asyncio
class TestSectorHeatmapEndpoint:
    async def test_empty_portfolio_returns_empty_sectors(self, user_id, override_deps):
        """GET /api/portfolio/sector-heatmap with no holdings returns empty list."""
        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=[])

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/sector-heatmap")

        assert response.status_code == 200
        data = response.json()
        assert data["sectors"] == []

    async def test_single_sector_single_stock(self, user_id, override_deps):
        """Single stock results in one sector entry with 100% allocation."""
        ticker = _make_ticker("KBANK", "Financial Services", Decimal("160.00"))

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=["KBANK"])
            mock_portfolio._get_positions_with_holdings = AsyncMock(
                return_value={"KBANK": 100}
            )
            mock_portfolio.calculate_avg_cost = AsyncMock(
                return_value=Decimal("150.00")
            )

            mock_market = MockMarketSvc.return_value
            mock_market.get_ticker_info = AsyncMock(return_value=ticker)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/sector-heatmap")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sectors"]) == 1

        sector = data["sectors"][0]
        assert sector["sector"] == "Financial Services"
        assert Decimal(sector["total_cost"]) == Decimal("15000.00")
        assert Decimal(sector["total_market_value"]) == Decimal("16000.00")
        # ROI = (16000 - 15000) / 15000 * 100 = 6.67%
        assert Decimal(sector["roi_percent"]) == Decimal("6.67")
        assert Decimal(sector["allocation_percent"]) == Decimal("100.00")
        assert sector["position_count"] == 1

    async def test_multiple_sectors_aggregation(self, user_id, override_deps):
        """Multiple stocks in different sectors are aggregated correctly."""
        tickers = {
            "KBANK": _make_ticker("KBANK", "Financial Services", Decimal("160.00")),
            "SCB": _make_ticker("SCB", "Financial Services", Decimal("110.00")),
            "PTT": _make_ticker("PTT", "Energy", Decimal("38.00")),
        }

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(
                return_value=["KBANK", "SCB", "PTT"]
            )
            mock_portfolio._get_positions_with_holdings = AsyncMock(
                return_value={"KBANK": 100, "SCB": 200, "PTT": 500}
            )

            async def mock_avg_cost(user_id, symbol):
                costs = {"KBANK": Decimal("150.00"), "SCB": Decimal("100.00"), "PTT": Decimal("35.00")}
                return costs[symbol]

            mock_portfolio.calculate_avg_cost = AsyncMock(side_effect=mock_avg_cost)

            mock_market = MockMarketSvc.return_value
            mock_market.get_ticker_info = AsyncMock(side_effect=lambda s: tickers[s])

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/sector-heatmap")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sectors"]) == 2

        # Financial Services: KBANK cost=15000, MV=16000; SCB cost=20000, MV=22000
        # Total cost = 35000, MV = 38000
        # Energy: PTT cost=17500, MV=19000
        # Grand total cost = 52500
        # Financial allocation = 35000/52500 * 100 = 66.67%
        # Energy allocation = 17500/52500 * 100 = 33.33%

        # Sorted by allocation desc
        financial = data["sectors"][0]
        energy = data["sectors"][1]

        assert financial["sector"] == "Financial Services"
        assert Decimal(financial["total_cost"]) == Decimal("35000.00")
        assert Decimal(financial["total_market_value"]) == Decimal("38000.00")
        # ROI = (38000 - 35000) / 35000 * 100 = 8.57%
        assert Decimal(financial["roi_percent"]) == Decimal("8.57")
        assert Decimal(financial["allocation_percent"]) == Decimal("66.67")
        assert financial["position_count"] == 2

        assert energy["sector"] == "Energy"
        assert Decimal(energy["total_cost"]) == Decimal("17500.00")
        assert Decimal(energy["total_market_value"]) == Decimal("19000.00")
        # ROI = (19000 - 17500) / 17500 * 100 = 8.57%
        assert Decimal(energy["roi_percent"]) == Decimal("8.57")
        assert Decimal(energy["allocation_percent"]) == Decimal("33.33")
        assert energy["position_count"] == 1

    async def test_unknown_sector_for_missing_sector_data(self, user_id, override_deps):
        """Stocks without sector info from yfinance are grouped under 'Unknown'."""
        ticker_no_sector = TickerInfo(
            symbol="XYZ", sector=None, current_price=Decimal("50.00")
        )

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=["XYZ"])
            mock_portfolio._get_positions_with_holdings = AsyncMock(
                return_value={"XYZ": 100}
            )
            mock_portfolio.calculate_avg_cost = AsyncMock(
                return_value=Decimal("40.00")
            )

            mock_market = MockMarketSvc.return_value
            mock_market.get_ticker_info = AsyncMock(return_value=ticker_no_sector)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/sector-heatmap")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sectors"]) == 1
        assert data["sectors"][0]["sector"] == "Unknown"
        assert data["sectors"][0]["position_count"] == 1

    async def test_missing_market_price_results_in_null_values(self, user_id, override_deps):
        """When market price is None, total_market_value and roi_percent are null."""
        ticker_no_price = TickerInfo(
            symbol="ABC", sector="Technology", current_price=None
        )

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=["ABC"])
            mock_portfolio._get_positions_with_holdings = AsyncMock(
                return_value={"ABC": 50}
            )
            mock_portfolio.calculate_avg_cost = AsyncMock(
                return_value=Decimal("200.00")
            )

            mock_market = MockMarketSvc.return_value
            mock_market.get_ticker_info = AsyncMock(return_value=ticker_no_price)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/sector-heatmap")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sectors"]) == 1
        sector = data["sectors"][0]
        assert sector["sector"] == "Technology"
        assert Decimal(sector["total_cost"]) == Decimal("10000.00")
        assert sector["total_market_value"] is None
        assert sector["roi_percent"] is None
        assert Decimal(sector["allocation_percent"]) == Decimal("100.00")

    async def test_negative_roi_percent(self, user_id, override_deps):
        """Sectors with negative ROI show negative roi_percent."""
        ticker = _make_ticker("DELTA", "Industrials", Decimal("80.00"))

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=["DELTA"])
            mock_portfolio._get_positions_with_holdings = AsyncMock(
                return_value={"DELTA": 100}
            )
            mock_portfolio.calculate_avg_cost = AsyncMock(
                return_value=Decimal("100.00")
            )

            mock_market = MockMarketSvc.return_value
            mock_market.get_ticker_info = AsyncMock(return_value=ticker)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/sector-heatmap")

        assert response.status_code == 200
        data = response.json()
        sector = data["sectors"][0]
        # Cost = 100*100 = 10000, MV = 80*100 = 8000
        # ROI = (8000 - 10000) / 10000 * 100 = -20.00%
        assert Decimal(sector["roi_percent"]) == Decimal("-20.00")

    async def test_unauthenticated_returns_401(self):
        """Requests without auth should return 401."""
        app.dependency_overrides.pop(get_current_user_id, None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/portfolio/sector-heatmap")
        assert response.status_code == 401
