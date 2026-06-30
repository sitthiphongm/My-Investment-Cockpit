"""Tests for the portfolio API router."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_id
from app.redis import get_redis
from app.schemas.enums import SentimentType
from app.schemas.market_data import TickerInfo
from app.schemas.portfolio import (
    PortfolioPositionResponse,
    PortfolioSummaryResponse,
)
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


def _make_summary(positions=None) -> PortfolioSummaryResponse:
    """Create a mock portfolio summary response."""
    if positions is None:
        positions = [
            PortfolioPositionResponse(
                stock_symbol="KBANK",
                quantity=100,
                avg_cost=Decimal("150.00"),
                total_cost=Decimal("15000.00"),
                market_value=Decimal("16000.00"),
                unrealized_pl=Decimal("1000.00"),
                roi_percent=Decimal("6.67"),
                allocation_percent=Decimal("100.00"),
                sentiment=SentimentType.BULL,
                company_name="Kasikornbank",
                current_price=Decimal("160.00"),
                last_refresh=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ]
    return PortfolioSummaryResponse(
        positions=positions,
        total_cost=Decimal("15000.00"),
        total_market_value=Decimal("16000.00"),
        total_unrealized_pl=Decimal("1000.00"),
        overall_roi_percent=Decimal("6.67"),
        market_data_complete=True,
    )


@pytest.mark.asyncio
class TestGetPortfolioSummary:
    async def test_unauthenticated_returns_401(self):
        """Requests without auth should return 401."""
        app.dependency_overrides.pop(get_current_user_id, None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/portfolio/summary")
        assert response.status_code == 401

    async def test_returns_portfolio_summary(self, user_id, override_deps):
        """GET /api/portfolio/summary returns aggregated portfolio data."""
        summary = _make_summary()

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=["KBANK"])
            mock_portfolio.get_summary = AsyncMock(return_value=summary)

            mock_market = MockMarketSvc.return_value
            mock_market.get_ticker_info = AsyncMock(
                return_value=TickerInfo(symbol="KBANK", current_price=Decimal("160.00"))
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/summary")

        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert len(data["positions"]) == 1
        assert data["positions"][0]["stock_symbol"] == "KBANK"
        assert data["total_cost"] == "15000.00"
        assert data["market_data_complete"] is True

    async def test_empty_portfolio(self, user_id, override_deps):
        """GET /api/portfolio/summary with no holdings returns empty portfolio."""
        empty_summary = PortfolioSummaryResponse(
            positions=[],
            total_cost=Decimal("0.00"),
            total_market_value=None,
            total_unrealized_pl=None,
            overall_roi_percent=None,
            market_data_complete=False,
        )

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=[])
            mock_portfolio.get_summary = AsyncMock(return_value=empty_summary)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/portfolio/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["positions"] == []
        assert data["total_cost"] == "0.00"
        assert data["market_data_complete"] is False


@pytest.mark.asyncio
class TestRefreshPortfolio:
    async def test_unauthenticated_returns_401(self):
        """Requests without auth should return 401."""
        app.dependency_overrides.pop(get_current_user_id, None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/portfolio/refresh")
        assert response.status_code == 401

    async def test_refresh_forces_market_data_update(self, user_id, override_deps):
        """POST /api/portfolio/refresh should call refresh_all and return updated summary."""
        summary = _make_summary()
        ticker = TickerInfo(symbol="KBANK", current_price=Decimal("160.00"))

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=["KBANK"])
            mock_portfolio.get_summary = AsyncMock(return_value=summary)

            mock_market = MockMarketSvc.return_value
            mock_market.refresh_all = AsyncMock(return_value={"KBANK": ticker})

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/portfolio/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["positions"][0]["stock_symbol"] == "KBANK"
        # Verify refresh_all was called with correct symbols
        mock_market.refresh_all.assert_called_once_with(["KBANK"])

    async def test_refresh_with_no_holdings(self, user_id, override_deps):
        """POST /api/portfolio/refresh with no holdings still returns valid response."""
        empty_summary = PortfolioSummaryResponse(
            positions=[],
            total_cost=Decimal("0.00"),
            market_data_complete=False,
        )

        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc, \
             patch("app.routers.portfolio.MarketDataService") as MockMarketSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.get_held_symbols = AsyncMock(return_value=[])
            mock_portfolio.get_summary = AsyncMock(return_value=empty_summary)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/portfolio/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["positions"] == []


@pytest.mark.asyncio
class TestSetSentiment:
    async def test_unauthenticated_returns_401(self):
        """Requests without auth should return 401."""
        app.dependency_overrides.pop(get_current_user_id, None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                "/api/portfolio/KBANK/sentiment",
                json={"sentiment": "Bull"},
            )
        assert response.status_code == 401

    async def test_set_sentiment_bull(self, user_id, override_deps):
        """PUT /api/portfolio/{symbol}/sentiment with Bull should succeed."""
        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.set_sentiment = AsyncMock(return_value=None)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/portfolio/KBANK/sentiment",
                    json={"sentiment": "Bull"},
                )

        assert response.status_code == 204
        mock_portfolio.set_sentiment.assert_called_once_with(
            user_id, "KBANK", SentimentType.BULL
        )

    async def test_set_sentiment_bear(self, user_id, override_deps):
        """PUT /api/portfolio/{symbol}/sentiment with Bear should succeed."""
        with patch("app.routers.portfolio.PortfolioService") as MockPortfolioSvc:
            mock_portfolio = MockPortfolioSvc.return_value
            mock_portfolio.set_sentiment = AsyncMock(return_value=None)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/portfolio/SCB/sentiment",
                    json={"sentiment": "Bear"},
                )

        assert response.status_code == 204
        mock_portfolio.set_sentiment.assert_called_once_with(
            user_id, "SCB", SentimentType.BEAR
        )

    async def test_invalid_sentiment_returns_422(self, user_id, override_deps):
        """PUT /api/portfolio/{symbol}/sentiment with invalid value should return 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                "/api/portfolio/KBANK/sentiment",
                json={"sentiment": "Neutral"},
            )
        assert response.status_code == 422

    async def test_missing_sentiment_field_returns_422(self, user_id, override_deps):
        """PUT /api/portfolio/{symbol}/sentiment without body returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                "/api/portfolio/KBANK/sentiment",
                json={},
            )
        assert response.status_code == 422
