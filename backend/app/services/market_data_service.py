"""Market data service - Fetches and caches stock data from Yahoo Finance."""

import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import redis.asyncio as redis

from app.config import settings
from app.schemas.market_data import TickerInfo, TrendingData, TrendingStock

logger = logging.getLogger(__name__)

# Redis key prefixes
MARKET_DATA_KEY_PREFIX = "market_data:"
TRENDING_DATA_KEY = "trending_data"

# yfinance field mappings: yfinance_key -> our_field_name
YFINANCE_FIELD_MAP = {
    "longName": "long_name",
    "currentPrice": "current_price",
    "regularMarketPrice": "current_price",  # fallback for currentPrice
    "sector": "sector",
    "industry": "industry",
    "previousClose": "previous_close",
    "dayHigh": "day_high",
    "dayLow": "day_low",
    "fiftyTwoWeekLow": "fifty_two_week_low",
    "fiftyTwoWeekHigh": "fifty_two_week_high",
    "marketCap": "market_cap",
    "trailingPE": "trailing_pe",
    "forwardPE": "forward_pe",
    "averageVolume": "average_volume",
    "beta": "beta",
    "dividendYield": "dividend_yield",
    "priceToBook": "price_to_book",
}


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """Convert a value to Decimal safely, returning None for invalid values."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Convert a value to int safely, returning None for invalid values."""
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


class MarketDataService:
    """Service for fetching and caching market data from Yahoo Finance.

    Uses Redis for caching with configurable TTL:
    - Portfolio data: default 1 hour (portfolio_cache_ttl)
    - Trending data: default 15 minutes (trending_cache_ttl)
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.portfolio_ttl = settings.market_data_cache_ttl
        self.trending_ttl = settings.trending_cache_ttl

    async def get_ticker_info(self, symbol: str) -> TickerInfo:
        """Fetch ticker info for a symbol, using cache if fresh.

        1. Check Redis cache (key: market_data:{symbol})
        2. If cached and fresh (within TTL), return cached data
        3. If stale or missing, fetch from yfinance
        4. Cache the result in Redis with TTL
        5. On failure, return stale cached data with staleness warning
        6. Return None for any field that yfinance returns as None/missing

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "DRAM")

        Returns:
            TickerInfo with all available fields populated.
        """
        symbol = symbol.upper()
        cache_key = f"{MARKET_DATA_KEY_PREFIX}{symbol}"

        # Check cache first
        cached_data = await self._get_cached(cache_key)
        if cached_data is not None:
            if not await self.is_cache_stale(symbol, self.portfolio_ttl):
                return cached_data

        # Cache is stale or missing, fetch from yfinance
        try:
            ticker_info = await self._fetch_from_yfinance(symbol)
            # Cache the result
            await self._set_cached(cache_key, ticker_info, self.portfolio_ttl)
            return ticker_info
        except SymbolNotFoundError:
            logger.warning("Symbol not found on Yahoo Finance: %s", symbol)
            # Return empty TickerInfo with symbol set
            empty_info = TickerInfo(symbol=symbol, last_refresh=None, is_stale=True)
            return empty_info
        except (NetworkError, RateLimitError) as e:
            logger.warning(
                "Failed to fetch market data for %s: %s", symbol, str(e)
            )
            # Return stale cached data if available
            if cached_data is not None:
                cached_data.is_stale = True
                return cached_data
            # No cached data at all
            return TickerInfo(symbol=symbol, last_refresh=None, is_stale=True)

    async def refresh_all(self, symbols: list[str]) -> dict[str, TickerInfo]:
        """Force-refresh cache for all given symbols.

        Uses exponential backoff on rate limiting errors.

        Args:
            symbols: List of stock symbols to refresh.

        Returns:
            Dictionary mapping symbol -> TickerInfo.
        """
        results: dict[str, TickerInfo] = {}
        backoff_delay = 1.0  # Initial backoff delay in seconds
        max_backoff = 60.0  # Maximum backoff delay
        max_retries = 3  # Max retries per symbol

        for symbol in symbols:
            symbol = symbol.upper()
            retries = 0
            while retries <= max_retries:
                try:
                    ticker_info = await self._fetch_from_yfinance(symbol)
                    cache_key = f"{MARKET_DATA_KEY_PREFIX}{symbol}"
                    await self._set_cached(cache_key, ticker_info, self.portfolio_ttl)
                    results[symbol] = ticker_info
                    # Reset backoff on success
                    backoff_delay = 1.0
                    break
                except RateLimitError:
                    retries += 1
                    if retries > max_retries:
                        logger.warning(
                            "Rate limited fetching %s after %d retries",
                            symbol,
                            max_retries,
                        )
                        # Return stale cached data if available
                        cached = await self._get_cached(
                            f"{MARKET_DATA_KEY_PREFIX}{symbol}"
                        )
                        if cached is not None:
                            cached.is_stale = True
                            results[symbol] = cached
                        else:
                            results[symbol] = TickerInfo(
                                symbol=symbol, is_stale=True
                            )
                        break
                    # Exponential backoff
                    import asyncio

                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, max_backoff)
                except SymbolNotFoundError:
                    logger.warning("Symbol not found: %s", symbol)
                    results[symbol] = TickerInfo(symbol=symbol, is_stale=True)
                    break
                except NetworkError as e:
                    logger.warning("Network error for %s: %s", symbol, str(e))
                    cached = await self._get_cached(
                        f"{MARKET_DATA_KEY_PREFIX}{symbol}"
                    )
                    if cached is not None:
                        cached.is_stale = True
                        results[symbol] = cached
                    else:
                        results[symbol] = TickerInfo(symbol=symbol, is_stale=True)
                    break

        return results

    async def is_cache_stale(self, symbol: str, max_age_seconds: int) -> bool:
        """Check if cached data is older than max_age_seconds.

        Args:
            symbol: Stock ticker symbol.
            max_age_seconds: Maximum acceptable age in seconds.

        Returns:
            True if cache is stale or missing, False if fresh.
        """
        symbol = symbol.upper()
        cache_key = f"{MARKET_DATA_KEY_PREFIX}{symbol}"

        cached_raw = await self.redis.get(cache_key)
        if cached_raw is None:
            return True

        try:
            data = json.loads(cached_raw)
            cached_at = data.get("_cached_at")
            if cached_at is None:
                return True
            age = time.time() - cached_at
            return age > max_age_seconds
        except (json.JSONDecodeError, TypeError):
            return True

    async def get_trending(self) -> TrendingData:
        """Fetch trending/gainers/losers from yfinance.

        Caches with 15-minute TTL.

        Returns:
            TrendingData with gainers, losers, and most_active lists.
        """
        # Check cache first
        cached_raw = await self.redis.get(TRENDING_DATA_KEY)
        if cached_raw is not None:
            try:
                data = json.loads(cached_raw)
                cached_at = data.get("_cached_at", 0)
                age = time.time() - cached_at
                if age <= self.trending_ttl:
                    return self._deserialize_trending(data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Fetch from yfinance
        try:
            trending = await self._fetch_trending_from_yfinance()
            # Enrich with sector data (top 10 per category to limit API calls)
            trending.gainers = await self._enrich_sectors(trending.gainers[:15])
            trending.losers = await self._enrich_sectors(trending.losers[:15])
            trending.most_active = await self._enrich_sectors(trending.most_active[:15])
            # Cache the result
            await self._set_trending_cached(trending)
            return trending
        except (NetworkError, RateLimitError) as e:
            logger.warning("Failed to fetch trending data: %s", str(e))
            # Return stale cached data if available
            if cached_raw is not None:
                try:
                    data = json.loads(cached_raw)
                    result = self._deserialize_trending(data)
                    result.is_stale = True
                    return result
                except (json.JSONDecodeError, TypeError):
                    pass
            return TrendingData(is_stale=True)

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    async def _fetch_from_yfinance(self, symbol: str) -> TickerInfo:
        """Fetch ticker info from yfinance.

        Raises:
            SymbolNotFoundError: If the symbol is not found.
            NetworkError: If a network failure occurs.
            RateLimitError: If rate limited by Yahoo Finance.
        """
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # yfinance returns an empty dict or a dict with only certain keys
            # when a symbol is not found
            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                # Check if it's truly not found vs just missing price
                if not info or (
                    info.get("longName") is None
                    and info.get("sector") is None
                    and info.get("industry") is None
                ):
                    raise SymbolNotFoundError(f"Symbol not found: {symbol}")

        except SymbolNotFoundError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "rate" in error_msg or "429" in error_msg or "too many" in error_msg:
                raise RateLimitError(f"Rate limited: {e}")
            if (
                "connection" in error_msg
                or "timeout" in error_msg
                or "network" in error_msg
                or "resolve" in error_msg
            ):
                raise NetworkError(f"Network error: {e}")
            # For other exceptions (e.g., symbol not found patterns)
            raise NetworkError(f"Unexpected error fetching {symbol}: {e}")

        # Extract fields using the mapping
        now = datetime.now(timezone.utc)
        extracted: dict[str, Any] = {
            "symbol": symbol,
            "last_refresh": now,
            "is_stale": False,
        }

        # Handle currentPrice with fallback to regularMarketPrice
        current_price = info.get("currentPrice")
        if current_price is None:
            current_price = info.get("regularMarketPrice")
        extracted["current_price"] = _safe_decimal(current_price)

        # Extract other fields
        extracted["long_name"] = info.get("longName")
        extracted["sector"] = info.get("sector")
        extracted["industry"] = info.get("industry")
        extracted["previous_close"] = _safe_decimal(info.get("previousClose"))
        extracted["day_high"] = _safe_decimal(info.get("dayHigh"))
        extracted["day_low"] = _safe_decimal(info.get("dayLow"))
        extracted["fifty_two_week_low"] = _safe_decimal(info.get("fiftyTwoWeekLow"))
        extracted["fifty_two_week_high"] = _safe_decimal(info.get("fiftyTwoWeekHigh"))
        extracted["market_cap"] = _safe_int(info.get("marketCap"))
        extracted["trailing_pe"] = _safe_decimal(info.get("trailingPE"))
        extracted["forward_pe"] = _safe_decimal(info.get("forwardPE"))
        extracted["average_volume"] = _safe_int(info.get("averageVolume"))
        extracted["beta"] = _safe_decimal(info.get("beta"))
        extracted["dividend_yield"] = _safe_decimal(info.get("dividendYield"))
        extracted["price_to_book"] = _safe_decimal(info.get("priceToBook"))

        return TickerInfo(**extracted)

    async def _fetch_trending_from_yfinance(self) -> TrendingData:
        """Fetch trending stocks from yfinance.

        Uses yf.screen() with predefined screener queries for
        day_gainers, day_losers, and most_actives.

        Raises:
            NetworkError: If a network failure occurs.
            RateLimitError: If rate limited.
        """
        import yfinance as yf

        gainers: list[TrendingStock] = []
        losers: list[TrendingStock] = []
        most_active: list[TrendingStock] = []
        errors: list[Exception] = []

        try:
            gainer_data = yf.screen("day_gainers", count=25)
            if gainer_data and "quotes" in gainer_data:
                for quote in gainer_data["quotes"][:25]:
                    gainers.append(self._parse_trending_quote(quote, "gainer"))
        except Exception as e:
            errors.append(e)

        try:
            loser_data = yf.screen("day_losers", count=25)
            if loser_data and "quotes" in loser_data:
                for quote in loser_data["quotes"][:25]:
                    losers.append(self._parse_trending_quote(quote, "loser"))
        except Exception as e:
            errors.append(e)

        try:
            active_data = yf.screen("most_actives", count=25)
            if active_data and "quotes" in active_data:
                for quote in active_data["quotes"][:25]:
                    most_active.append(self._parse_trending_quote(quote, "most_active"))
        except Exception as e:
            errors.append(e)

        # If all three calls failed, propagate the error
        if len(errors) == 3:
            error_msg = str(errors[0]).lower()
            if "rate" in error_msg or "429" in error_msg:
                raise RateLimitError(f"Rate limited: {errors[0]}")
            raise NetworkError(f"Failed to fetch trending data: {errors[0]}")

        return TrendingData(
            gainers=gainers,
            losers=losers,
            most_active=most_active,
            last_refresh=datetime.now(timezone.utc),
            is_stale=False,
        )

    async def _enrich_sectors(self, stocks: list[TrendingStock]) -> list[TrendingStock]:
        """Enrich trending stocks with sector data from cache or quick lookup."""
        import yfinance as yf
        import asyncio

        for stock in stocks:
            if stock.sector:
                continue
            sym = stock.symbol
            # Try cache first
            cache_key = f"sector_cache:{sym}"
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    stock.sector = cached.decode() if isinstance(cached, bytes) else cached
                    continue
            except Exception:
                pass

            # Quick lookup (run in executor to not block)
            try:
                loop = asyncio.get_event_loop()
                sector = await loop.run_in_executor(
                    None, lambda s=sym: self._quick_sector_lookup(s)
                )
                if sector:
                    stock.sector = sector
                    # Cache for 24 hours
                    try:
                        await self.redis.set(cache_key, sector, ex=86400)
                    except Exception:
                        pass
            except Exception:
                pass

        return stocks

    @staticmethod
    def _quick_sector_lookup(symbol: str) -> Optional[str]:
        """Quick sector lookup using yfinance fast_info."""
        import yfinance as yf
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return info.get("sector")
        except Exception:
            return None

    def _parse_trending_quote(self, quote: dict, category: str = "") -> TrendingStock:
        """Parse a trending quote from yfinance screener response with intelligent reasons."""
        change_pct = _safe_decimal(quote.get("regularMarketChangePercent"))
        volume = _safe_int(quote.get("regularMarketVolume"))
        avg_volume = _safe_int(quote.get("averageDailyVolume3Month"))
        symbol = quote.get("symbol", "")
        name = quote.get("longName") or quote.get("shortName") or ""

        # Generate intelligent catalyst-driven reason
        reason = self._generate_intelligent_reason(category, change_pct, volume, avg_volume, name)

        return TrendingStock(
            symbol=symbol,
            company_name=name,
            current_price=_safe_decimal(quote.get("regularMarketPrice")),
            day_change_percent=change_pct,
            volume=volume,
            market_cap=_safe_int(quote.get("marketCap")),
            sector=quote.get("sector"),
            pe_trailing=_safe_decimal(quote.get("trailingPE")),
            reason=reason,
        )

    def _generate_intelligent_reason(self, category: str, change_pct, volume, avg_volume, name: str) -> str:
        """Generate intelligent catalyst-driven reason based on category and metrics."""
        pct = float(change_pct) if change_pct else 0
        vol_ratio = (volume / avg_volume) if volume and avg_volume and avg_volume > 0 else 1.0
        vol_text = f" on {vol_ratio:.1f}x avg volume" if vol_ratio > 2 else ""

        if category == "gainer":
            if pct > 30:
                return f"📈 Breakout Rally: +{pct:.1f}%{vol_text} — likely major catalyst (earnings beat, FDA approval, or acquisition)"
            elif pct > 15:
                return f"📈 Strong Momentum: +{pct:.1f}%{vol_text} — significant positive news or short squeeze potential"
            elif pct > 10:
                return f"📈 Rally: +{pct:.1f}%{vol_text} — positive earnings/partnership catalyst or sector rotation"
            elif pct > 5:
                return f"📈 Solid Gain: +{pct:.1f}%{vol_text} — earnings beat or analyst upgrade momentum"
            else:
                return f"📈 Up {pct:.1f}%{vol_text}"

        elif category == "loser":
            if pct < -30:
                return f"📉 Crash Alert: {pct:.1f}%{vol_text} — severe catalyst (earnings miss, FDA rejection, or fraud)"
            elif pct < -15:
                return f"📉 Sharp Decline: {pct:.1f}%{vol_text} — likely earnings miss or regulatory concerns"
            elif pct < -10:
                return f"💸 Heavy Selling: {pct:.1f}%{vol_text} — guidance cut, share dilution, or sector pressure"
            elif pct < -5:
                return f"⚠️ Sell-off: {pct:.1f}%{vol_text} — analyst downgrade or negative sentiment"
            else:
                return f"📉 Down {pct:.1f}%{vol_text}"

        else:  # most_active
            if abs(pct) > 10:
                direction = "rally" if pct > 0 else "sell-off"
                return f"🔥 High Activity: Major {direction} ({pct:+.1f}%){vol_text} — market attention on catalyst"
            elif abs(pct) > 3:
                if pct > 0:
                    return f"⚡ Sector Momentum: Active buying ({pct:+.1f}%){vol_text} — institutional accumulation"
                else:
                    return f"⚡ Heavy Trading: {pct:+.1f}%{vol_text} — profit-taking or rebalancing"
            elif abs(pct) <= 1:
                return f"🔄 High-Volume Consolidation: Massive turnover ({pct:+.1f}%) — accumulation/distribution phase"
            else:
                return f"🔥 Active: {pct:+.1f}%{vol_text} — elevated market interest"

    async def _get_cached(self, cache_key: str) -> Optional[TickerInfo]:
        """Get cached ticker info from Redis."""
        cached_raw = await self.redis.get(cache_key)
        if cached_raw is None:
            return None
        try:
            data = json.loads(cached_raw)
            # Remove internal cache metadata before parsing
            data.pop("_cached_at", None)
            return TickerInfo(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    async def _set_cached(
        self, cache_key: str, ticker_info: TickerInfo, ttl: int
    ) -> None:
        """Cache ticker info in Redis with TTL."""
        data = self._serialize_ticker_info(ticker_info)
        data["_cached_at"] = time.time()
        await self.redis.set(cache_key, json.dumps(data), ex=ttl)

    async def _set_trending_cached(self, trending: TrendingData) -> None:
        """Cache trending data in Redis with trending TTL."""
        data = self._serialize_trending(trending)
        data["_cached_at"] = time.time()
        await self.redis.set(TRENDING_DATA_KEY, json.dumps(data), ex=self.trending_ttl)

    def _serialize_ticker_info(self, ticker_info: TickerInfo) -> dict:
        """Serialize TickerInfo to a JSON-compatible dict."""
        data = ticker_info.model_dump()
        # Convert Decimal to str for JSON serialization
        for key, value in data.items():
            if isinstance(value, Decimal):
                data[key] = str(value)
            elif isinstance(value, datetime):
                data[key] = value.isoformat()
        return data

    def _serialize_trending(self, trending: TrendingData) -> dict:
        """Serialize TrendingData to a JSON-compatible dict."""
        data = trending.model_dump()
        # Convert Decimal to str recursively
        return self._convert_decimals(data)

    def _convert_decimals(self, obj: Any) -> Any:
        """Recursively convert Decimal values to strings for JSON."""
        if isinstance(obj, dict):
            return {k: self._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals(item) for item in obj]
        elif isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _deserialize_trending(self, data: dict) -> TrendingData:
        """Deserialize a cached trending data dict to TrendingData."""
        data.pop("_cached_at", None)
        return TrendingData(**data)


# -------------------------------------------------------------------------
# Custom exceptions for error handling
# -------------------------------------------------------------------------


class SymbolNotFoundError(Exception):
    """Raised when a stock symbol is not found on Yahoo Finance."""

    pass


class NetworkError(Exception):
    """Raised when a network failure occurs during data fetching."""

    pass


class RateLimitError(Exception):
    """Raised when Yahoo Finance rate limits the request."""

    pass
