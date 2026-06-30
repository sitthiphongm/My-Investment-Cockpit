"""Unit tests for MarketDataService.

Tests cover:
- Cache hit/miss behavior
- Staleness detection
- Error handling (symbol not found, network failure, rate limiting)
- Exponential backoff in refresh_all
- N/A field handling for missing yfinance data
- Trending data caching
"""

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.market_data import TickerInfo, TrendingData, TrendingStock
from app.services.market_data_service import (
    MARKET_DATA_KEY_PREFIX,
    TRENDING_DATA_KEY,
    MarketDataService,
    NetworkError,
    RateLimitError,
    SymbolNotFoundError,
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    return client


@pytest.fixture
def service(mock_redis):
    """Create a MarketDataService with mock Redis."""
    return MarketDataService(redis_client=mock_redis)


def _make_cached_ticker_data(symbol: str, cached_at: float = None) -> str:
    """Helper to create cached ticker JSON data."""
    if cached_at is None:
        cached_at = time.time()
    data = {
        "symbol": symbol,
        "long_name": "Apple Inc.",
        "current_price": "150.0",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "previous_close": "149.0",
        "day_high": "151.0",
        "day_low": "148.0",
        "fifty_two_week_low": "120.0",
        "fifty_two_week_high": "180.0",
        "market_cap": 2500000000000,
        "trailing_pe": "25.5",
        "forward_pe": "22.0",
        "average_volume": 80000000,
        "beta": "1.2",
        "dividend_yield": "0.005",
        "price_to_book": "45.0",
        "last_refresh": datetime.now(timezone.utc).isoformat(),
        "is_stale": False,
        "_cached_at": cached_at,
    }
    return json.dumps(data)


def _make_yfinance_info(
    symbol: str = "AAPL",
    include_all: bool = True,
    missing_fields: list[str] = None,
) -> dict:
    """Helper to create a mock yfinance Ticker.info dict."""
    info = {
        "longName": "Apple Inc.",
        "currentPrice": 150.0,
        "regularMarketPrice": 150.0,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "previousClose": 149.0,
        "dayHigh": 151.0,
        "dayLow": 148.0,
        "fiftyTwoWeekLow": 120.0,
        "fiftyTwoWeekHigh": 180.0,
        "marketCap": 2500000000000,
        "trailingPE": 25.5,
        "forwardPE": 22.0,
        "averageVolume": 80000000,
        "beta": 1.2,
        "dividendYield": 0.005,
        "priceToBook": 45.0,
    }
    if missing_fields:
        for field in missing_fields:
            info[field] = None
    return info


class TestGetTickerInfo:
    """Tests for get_ticker_info method."""

    @pytest.mark.asyncio
    async def test_returns_cached_data_when_fresh(self, service, mock_redis):
        """Fresh cached data should be returned without calling yfinance."""
        cached_data = _make_cached_ticker_data("AAPL", cached_at=time.time())
        mock_redis.get = AsyncMock(return_value=cached_data)

        result = await service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        assert result.long_name == "Apple Inc."
        assert result.current_price == Decimal("150.0")
        assert result.sector == "Technology"
        assert result.is_stale is False

    @pytest.mark.asyncio
    async def test_fetches_from_yfinance_when_cache_miss(self, service, mock_redis):
        """Missing cache should trigger yfinance fetch."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info()
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        assert result.long_name == "Apple Inc."
        assert result.current_price == Decimal("150.0")
        assert result.sector == "Technology"
        assert result.industry == "Consumer Electronics"
        # Verify it was cached
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetches_from_yfinance_when_cache_stale(self, service, mock_redis):
        """Stale cached data should trigger a fresh fetch."""
        # Cached data from 2 hours ago (stale for 1 hour TTL)
        stale_time = time.time() - 7200
        stale_data = _make_cached_ticker_data("AAPL", cached_at=stale_time)
        mock_redis.get = AsyncMock(return_value=stale_data)

        mock_info = _make_yfinance_info()
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        assert result.is_stale is False
        # Should have cached the fresh data
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_regular_market_price_as_fallback(self, service, mock_redis):
        """When currentPrice is None, regularMarketPrice should be used."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info()
        mock_info["currentPrice"] = None
        mock_info["regularMarketPrice"] = 148.5
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.get_ticker_info("AAPL")

        assert result.current_price == Decimal("148.5")

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_fields(self, service, mock_redis):
        """Fields that are None from yfinance should be None in the result."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info(
            missing_fields=["dividendYield", "forwardPE", "beta"]
        )
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.get_ticker_info("AAPL")

        assert result.dividend_yield is None
        assert result.forward_pe is None
        assert result.beta is None
        # Other fields should still be populated
        assert result.current_price == Decimal("150.0")
        assert result.long_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_symbol_not_found_returns_empty_ticker_info(
        self, service, mock_redis
    ):
        """Unknown symbol should return empty TickerInfo with is_stale=True."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_ticker = MagicMock()
        mock_ticker.info = {}  # Empty dict means not found

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.get_ticker_info("XXXYZ")

        assert result.symbol == "XXXYZ"
        assert result.is_stale is True
        assert result.current_price is None
        assert result.long_name is None

    @pytest.mark.asyncio
    async def test_network_error_returns_stale_cached_data(
        self, service, mock_redis
    ):
        """Network failure should return stale cached data with warning."""
        stale_time = time.time() - 7200
        stale_data = _make_cached_ticker_data("AAPL", cached_at=stale_time)
        mock_redis.get = AsyncMock(return_value=stale_data)

        with patch(
            "yfinance.Ticker",
            side_effect=Exception("Connection timeout"),
        ):
            result = await service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        assert result.is_stale is True
        assert result.long_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_network_error_no_cache_returns_empty(self, service, mock_redis):
        """Network failure with no cache should return empty stale TickerInfo."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "yfinance.Ticker",
            side_effect=Exception("Connection timeout"),
        ):
            result = await service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        assert result.is_stale is True
        assert result.current_price is None

    @pytest.mark.asyncio
    async def test_symbol_uppercased(self, service, mock_redis):
        """Symbol should be uppercased regardless of input."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info()
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.get_ticker_info("aapl")

        assert result.symbol == "AAPL"


class TestIsCacheStale:
    """Tests for is_cache_stale method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_no_cache(self, service, mock_redis):
        """No cached data should be considered stale."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await service.is_cache_stale("AAPL", 3600)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_fresh(self, service, mock_redis):
        """Recently cached data should not be stale."""
        fresh_data = _make_cached_ticker_data("AAPL", cached_at=time.time())
        mock_redis.get = AsyncMock(return_value=fresh_data)

        result = await service.is_cache_stale("AAPL", 3600)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_old(self, service, mock_redis):
        """Data older than max_age_seconds should be stale."""
        old_time = time.time() - 7200  # 2 hours ago
        old_data = _make_cached_ticker_data("AAPL", cached_at=old_time)
        mock_redis.get = AsyncMock(return_value=old_data)

        result = await service.is_cache_stale("AAPL", 3600)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_invalid_json(self, service, mock_redis):
        """Invalid JSON in cache should be considered stale."""
        mock_redis.get = AsyncMock(return_value="not valid json")

        result = await service.is_cache_stale("AAPL", 3600)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_cached_at_missing(self, service, mock_redis):
        """Cache entry without _cached_at should be considered stale."""
        data = json.dumps({"symbol": "AAPL", "current_price": "150.0"})
        mock_redis.get = AsyncMock(return_value=data)

        result = await service.is_cache_stale("AAPL", 3600)

        assert result is True


class TestRefreshAll:
    """Tests for refresh_all method."""

    @pytest.mark.asyncio
    async def test_refreshes_multiple_symbols(self, service, mock_redis):
        """Should fetch and cache data for all symbols."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info()
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await service.refresh_all(["AAPL", "GOOG"])

        assert "AAPL" in result
        assert "GOOG" in result
        assert result["AAPL"].long_name == "Apple Inc."
        assert result["GOOG"].long_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_handles_rate_limiting_with_backoff(self, service, mock_redis):
        """Rate limiting should trigger exponential backoff and retries."""
        mock_redis.get = AsyncMock(return_value=None)

        call_count = 0

        def mock_ticker_side_effect(symbol):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("429 Too Many Requests")
            mock_t = MagicMock()
            mock_t.info = _make_yfinance_info()
            return mock_t

        with patch("yfinance.Ticker", side_effect=mock_ticker_side_effect):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.refresh_all(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"].long_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_returns_stale_cache_on_max_retries_exceeded(
        self, service, mock_redis
    ):
        """When max retries exceeded, should return stale cache if available."""
        stale_data = _make_cached_ticker_data("AAPL", cached_at=time.time() - 7200)

        # First call returns None (for get_ticker_info cache check)
        # Subsequent calls return stale data (for fallback after max retries)
        mock_redis.get = AsyncMock(return_value=stale_data)

        with patch(
            "yfinance.Ticker",
            side_effect=Exception("429 Too Many Requests"),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.refresh_all(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"].is_stale is True

    @pytest.mark.asyncio
    async def test_handles_symbol_not_found_in_batch(self, service, mock_redis):
        """Symbol not found in batch should not stop other symbols."""
        mock_redis.get = AsyncMock(return_value=None)

        call_count = 0

        def mock_ticker_side_effect(symbol):
            nonlocal call_count
            call_count += 1
            mock_t = MagicMock()
            if symbol == "XXXYZ":
                mock_t.info = {}
            else:
                mock_t.info = _make_yfinance_info()
            return mock_t

        with patch("yfinance.Ticker", side_effect=mock_ticker_side_effect):
            result = await service.refresh_all(["AAPL", "XXXYZ"])

        assert result["AAPL"].long_name == "Apple Inc."
        assert result["XXXYZ"].is_stale is True


class TestGetTrending:
    """Tests for get_trending method."""

    @pytest.mark.asyncio
    async def test_returns_cached_trending_when_fresh(self, service, mock_redis):
        """Fresh cached trending data should be returned."""
        cached_data = {
            "gainers": [
                {
                    "symbol": "AAPL",
                    "company_name": "Apple",
                    "current_price": "150.0",
                    "day_change_percent": "2.5",
                    "volume": 80000000,
                }
            ],
            "losers": [],
            "most_active": [],
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "is_stale": False,
            "_cached_at": time.time(),
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        result = await service.get_trending()

        assert len(result.gainers) == 1
        assert result.gainers[0].symbol == "AAPL"
        assert result.is_stale is False

    @pytest.mark.asyncio
    async def test_fetches_trending_when_cache_stale(self, service, mock_redis):
        """Stale trending cache should trigger fresh fetch."""
        stale_data = {
            "gainers": [],
            "losers": [],
            "most_active": [],
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "is_stale": False,
            "_cached_at": time.time() - 1800,  # 30 min ago (stale for 15 min TTL)
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(stale_data))

        mock_screen_response = {
            "quotes": [
                {
                    "symbol": "TSLA",
                    "longName": "Tesla Inc.",
                    "regularMarketPrice": 250.0,
                    "regularMarketChangePercent": 5.0,
                    "regularMarketVolume": 100000000,
                }
            ]
        }

        with patch("yfinance.screen", return_value=mock_screen_response):
            result = await service.get_trending()

        assert result.is_stale is False
        # Verify cache was updated
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_returns_stale_trending_on_network_error(
        self, service, mock_redis
    ):
        """Network failure should return stale trending data."""
        stale_data = {
            "gainers": [
                {
                    "symbol": "AAPL",
                    "company_name": "Apple",
                    "current_price": "150.0",
                    "day_change_percent": "2.5",
                    "volume": 80000000,
                }
            ],
            "losers": [],
            "most_active": [],
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "is_stale": False,
            "_cached_at": time.time() - 1800,  # stale
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(stale_data))

        with patch(
            "yfinance.screen",
            side_effect=Exception("Connection timeout"),
        ):
            result = await service.get_trending()

        assert result.is_stale is True
        assert len(result.gainers) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_trending_on_error_no_cache(
        self, service, mock_redis
    ):
        """Network failure with no cache should return empty TrendingData."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "yfinance.screen",
            side_effect=Exception("Connection timeout"),
        ):
            result = await service.get_trending()

        assert result.is_stale is True
        assert len(result.gainers) == 0
        assert len(result.losers) == 0


class TestTickerInfoModel:
    """Tests for TickerInfo schema."""

    def test_all_fields_optional_except_symbol(self):
        """All fields except symbol should be optional."""
        info = TickerInfo(symbol="AAPL")
        assert info.symbol == "AAPL"
        assert info.long_name is None
        assert info.current_price is None
        assert info.sector is None
        assert info.industry is None
        assert info.is_stale is False

    def test_full_ticker_info(self):
        """Should accept all 16 fields plus metadata."""
        info = TickerInfo(
            symbol="AAPL",
            long_name="Apple Inc.",
            current_price=Decimal("150.0"),
            sector="Technology",
            industry="Consumer Electronics",
            previous_close=Decimal("149.0"),
            day_high=Decimal("151.0"),
            day_low=Decimal("148.0"),
            fifty_two_week_low=Decimal("120.0"),
            fifty_two_week_high=Decimal("180.0"),
            market_cap=2500000000000,
            trailing_pe=Decimal("25.5"),
            forward_pe=Decimal("22.0"),
            average_volume=80000000,
            beta=Decimal("1.2"),
            dividend_yield=Decimal("0.005"),
            price_to_book=Decimal("45.0"),
            last_refresh=datetime.now(timezone.utc),
            is_stale=False,
        )
        assert info.long_name == "Apple Inc."
        assert info.market_cap == 2500000000000


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_detection(self, service, mock_redis):
        """Rate limit errors from yfinance should be properly detected."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "yfinance.Ticker",
            side_effect=Exception("429 Too Many Requests"),
        ):
            result = await service.get_ticker_info("AAPL")

        assert result.is_stale is True

    @pytest.mark.asyncio
    async def test_cache_key_format(self, service, mock_redis):
        """Cache key should use correct format: market_data:{SYMBOL}."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info()
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            await service.get_ticker_info("AAPL")

        # Check that get was called with the right key
        mock_redis.get.assert_called_with("market_data:AAPL")

    @pytest.mark.asyncio
    async def test_ttl_passed_to_redis_set(self, service, mock_redis):
        """Redis set should use the configured portfolio TTL."""
        mock_redis.get = AsyncMock(return_value=None)

        mock_info = _make_yfinance_info()
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            await service.get_ticker_info("AAPL")

        # Verify TTL is passed
        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get("ex") == 3600  # Default portfolio_cache_ttl
