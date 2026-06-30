"""Unit tests for the trending stocks endpoint (GET /api/trending).

Tests cover:
- Successful response with trending data (gainers, losers, most_active)
- Response schema correctness (symbol, company_name, current_price, day_change_percent, volume)
- Redis cache hit behavior (returns cached data within 15-min TTL)
- Redis cache miss triggers yfinance fetch and caches result
- Graceful degradation on network errors (returns stale cache or empty)
- 15-minute cache TTL is respected

Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for dependency override."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
async def client_with_mock_redis(mock_redis_client):
    """Provide an async test client with mocked Redis."""
    from app.redis import get_redis

    async def override_get_redis():
        return mock_redis_client

    app.dependency_overrides[get_redis] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _make_cached_trending(cached_at: float = None) -> str:
    """Create cached trending data JSON string."""
    if cached_at is None:
        cached_at = time.time()
    data = {
        "gainers": [
            {
                "symbol": "TSLA",
                "company_name": "Tesla Inc.",
                "current_price": "250.0",
                "day_change_percent": "5.2",
                "volume": 120000000,
            },
            {
                "symbol": "NVDA",
                "company_name": "NVIDIA Corporation",
                "current_price": "450.0",
                "day_change_percent": "3.8",
                "volume": 95000000,
            },
        ],
        "losers": [
            {
                "symbol": "META",
                "company_name": "Meta Platforms Inc.",
                "current_price": "300.0",
                "day_change_percent": "-4.1",
                "volume": 85000000,
            },
        ],
        "most_active": [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "current_price": "150.0",
                "day_change_percent": "0.5",
                "volume": 200000000,
            },
        ],
        "last_refresh": datetime.now(timezone.utc).isoformat(),
        "is_stale": False,
        "_cached_at": cached_at,
    }
    return json.dumps(data)


class TestGetTrendingEndpoint:
    """Tests for GET /api/trending endpoint."""

    @pytest.mark.asyncio
    async def test_returns_trending_data_from_fresh_cache(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Should return cached trending data when cache is fresh (within 15 min)."""
        cached_data = _make_cached_trending(cached_at=time.time())
        mock_redis_client.get = AsyncMock(return_value=cached_data)

        response = await client_with_mock_redis.get("/api/trending")

        assert response.status_code == 200
        data = response.json()
        assert "gainers" in data
        assert "losers" in data
        assert "most_active" in data
        assert data["is_stale"] is False

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Each trending stock should have symbol, company_name, current_price, day_change_percent, volume."""
        cached_data = _make_cached_trending(cached_at=time.time())
        mock_redis_client.get = AsyncMock(return_value=cached_data)

        response = await client_with_mock_redis.get("/api/trending")

        assert response.status_code == 200
        data = response.json()

        # Check gainers have all required fields
        for stock in data["gainers"]:
            assert "symbol" in stock
            assert "company_name" in stock
            assert "current_price" in stock
            assert "day_change_percent" in stock
            assert "volume" in stock

        # Check losers
        for stock in data["losers"]:
            assert "symbol" in stock
            assert "company_name" in stock
            assert "current_price" in stock
            assert "day_change_percent" in stock
            assert "volume" in stock

        # Check most_active
        for stock in data["most_active"]:
            assert "symbol" in stock
            assert "company_name" in stock
            assert "current_price" in stock
            assert "day_change_percent" in stock
            assert "volume" in stock

    @pytest.mark.asyncio
    async def test_gainers_data_values_correct(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Gainers should contain correct stock data from cache."""
        cached_data = _make_cached_trending(cached_at=time.time())
        mock_redis_client.get = AsyncMock(return_value=cached_data)

        response = await client_with_mock_redis.get("/api/trending")

        data = response.json()
        gainers = data["gainers"]
        assert len(gainers) == 2
        assert gainers[0]["symbol"] == "TSLA"
        assert gainers[0]["company_name"] == "Tesla Inc."
        assert float(gainers[0]["day_change_percent"]) > 0

    @pytest.mark.asyncio
    async def test_losers_have_negative_change(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Losers should have negative day_change_percent."""
        cached_data = _make_cached_trending(cached_at=time.time())
        mock_redis_client.get = AsyncMock(return_value=cached_data)

        response = await client_with_mock_redis.get("/api/trending")

        data = response.json()
        losers = data["losers"]
        assert len(losers) == 1
        assert losers[0]["symbol"] == "META"
        assert float(losers[0]["day_change_percent"]) < 0

    @pytest.mark.asyncio
    async def test_fetches_from_yfinance_when_cache_empty(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Should fetch from yfinance when no cached data exists."""
        mock_redis_client.get = AsyncMock(return_value=None)

        mock_screen_response = {
            "quotes": [
                {
                    "symbol": "TSLA",
                    "longName": "Tesla Inc.",
                    "regularMarketPrice": 250.0,
                    "regularMarketChangePercent": 5.2,
                    "regularMarketVolume": 120000000,
                }
            ]
        }

        with patch("yfinance.screen", return_value=mock_screen_response):
            response = await client_with_mock_redis.get("/api/trending")

        assert response.status_code == 200
        data = response.json()
        assert len(data["gainers"]) == 1
        assert data["gainers"][0]["symbol"] == "TSLA"
        # Should have cached the result
        mock_redis_client.set.assert_called()

    @pytest.mark.asyncio
    async def test_fetches_from_yfinance_when_cache_stale(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Should fetch from yfinance when cache is older than 15 minutes."""
        # Cache is 20 minutes old (stale for 15-minute TTL)
        stale_time = time.time() - 1200
        stale_cached = _make_cached_trending(cached_at=stale_time)
        mock_redis_client.get = AsyncMock(return_value=stale_cached)

        mock_screen_response = {
            "quotes": [
                {
                    "symbol": "AMZN",
                    "longName": "Amazon.com Inc.",
                    "regularMarketPrice": 180.0,
                    "regularMarketChangePercent": 2.1,
                    "regularMarketVolume": 60000000,
                }
            ]
        }

        with patch("yfinance.screen", return_value=mock_screen_response):
            response = await client_with_mock_redis.get("/api/trending")

        assert response.status_code == 200
        data = response.json()
        assert data["is_stale"] is False
        # Fresh data was fetched and cached
        mock_redis_client.set.assert_called()

    @pytest.mark.asyncio
    async def test_returns_stale_data_on_network_error(
        self, client_with_mock_redis, mock_redis_client
    ):
        """On network error, should return stale cached data with is_stale=True."""
        stale_time = time.time() - 1200
        stale_cached = _make_cached_trending(cached_at=stale_time)
        mock_redis_client.get = AsyncMock(return_value=stale_cached)

        with patch("yfinance.screen", side_effect=Exception("Connection timeout")):
            response = await client_with_mock_redis.get("/api/trending")

        assert response.status_code == 200
        data = response.json()
        assert data["is_stale"] is True
        # Should still have the stale data
        assert len(data["gainers"]) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_trending_on_error_no_cache(
        self, client_with_mock_redis, mock_redis_client
    ):
        """On error with no cache, should return empty trending data."""
        mock_redis_client.get = AsyncMock(return_value=None)

        with patch("yfinance.screen", side_effect=Exception("Connection timeout")):
            response = await client_with_mock_redis.get("/api/trending")

        assert response.status_code == 200
        data = response.json()
        assert data["is_stale"] is True
        assert data["gainers"] == []
        assert data["losers"] == []
        assert data["most_active"] == []

    @pytest.mark.asyncio
    async def test_cache_ttl_is_15_minutes(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Cache should use 15-minute (900 second) TTL for trending data."""
        mock_redis_client.get = AsyncMock(return_value=None)

        mock_screen_response = {
            "quotes": [
                {
                    "symbol": "TSLA",
                    "longName": "Tesla Inc.",
                    "regularMarketPrice": 250.0,
                    "regularMarketChangePercent": 5.2,
                    "regularMarketVolume": 120000000,
                }
            ]
        }

        with patch("yfinance.screen", return_value=mock_screen_response):
            await client_with_mock_redis.get("/api/trending")

        # Verify Redis set was called with 900s TTL
        set_call = mock_redis_client.set.call_args
        assert set_call.kwargs.get("ex") == 900

    @pytest.mark.asyncio
    async def test_no_authentication_required(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Trending endpoint should not require authentication (public data)."""
        cached_data = _make_cached_trending(cached_at=time.time())
        mock_redis_client.get = AsyncMock(return_value=cached_data)

        # No auth headers or cookies provided
        response = await client_with_mock_redis.get("/api/trending")

        # Should succeed without auth
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_categories(
        self, client_with_mock_redis, mock_redis_client
    ):
        """Response should contain three categories: gainers, losers, most_active."""
        cached_data = _make_cached_trending(cached_at=time.time())
        mock_redis_client.get = AsyncMock(return_value=cached_data)

        response = await client_with_mock_redis.get("/api/trending")

        data = response.json()
        assert "gainers" in data
        assert "losers" in data
        assert "most_active" in data
        assert isinstance(data["gainers"], list)
        assert isinstance(data["losers"], list)
        assert isinstance(data["most_active"], list)
