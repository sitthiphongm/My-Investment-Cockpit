"""FMP (Financial Modeling Prep) adapter for stock screening.

Primary screener provider — supports server-side filtering by:
- Sector, Industry, Market Cap, P/E, Dividend Yield, Beta, Price, Volume, Country
- Returns up to 1000 results per query

Free tier: 250 requests/day
Cache TTL: 1 hour
"""

import logging
from decimal import Decimal
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
FMP_CACHE_TTL = 3600  # 1 hour


class FMPScreenerAdapter:
    """Adapter for FMP stock screener API."""

    def __init__(self, redis_client=None):
        self.api_key = settings.fmp_api_key
        self.redis = redis_client
        self.base_url = FMP_BASE_URL

    async def screen_stocks(self, filters: dict) -> list[dict]:
        """Execute a stock screener query against FMP.

        Supported filters:
        - market_cap_min / market_cap_max (in USD)
        - pe_min / pe_max
        - dividend_yield_min / dividend_yield_max (percentage, e.g. 3 = 3%)
        - beta_min / beta_max
        - sector (string)
        - industry (string)
        - country (default: US)
        - price_min / price_max
        - volume_min

        Returns list of stock dicts with enriched fundamental data.
        """
        if not self.api_key:
            logger.warning("FMP API key not configured")
            return []

        # Check cache first
        cache_key = f"fmp_screen:{_hash_filters(filters)}"
        if self.redis:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return cached

        # Build FMP query params
        params = self._build_params(filters)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/stock-screener",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, list):
                logger.warning("FMP screener returned non-list: %s", type(data))
                return []

            # Parse results
            results = [self._parse_stock(stock) for stock in data[:100]]

            # Cache results
            if self.redis:
                await self._set_cache(cache_key, results, FMP_CACHE_TTL)

            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("FMP rate limited")
            else:
                logger.error("FMP HTTP error: %s", e.response.status_code)
            return []
        except Exception as e:
            logger.error("FMP screener error: %s", str(e))
            return []

    async def get_profile(self, symbol: str) -> Optional[dict]:
        """Get enriched company profile from FMP."""
        if not self.api_key:
            return None

        cache_key = f"fmp_profile:{symbol}"
        if self.redis:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return cached

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/profile/{symbol}",
                    params={"apikey": self.api_key},
                )
                response.raise_for_status()
                data = response.json()

            if not data or not isinstance(data, list) or len(data) == 0:
                return None

            profile = data[0]
            result = {
                "symbol": profile.get("symbol"),
                "company_name": profile.get("companyName"),
                "sector": profile.get("sector"),
                "industry": profile.get("industry"),
                "market_cap": profile.get("mktCap"),
                "price": profile.get("price"),
                "beta": profile.get("beta"),
                "volume_avg": profile.get("volAvg"),
                "last_dividend": profile.get("lastDiv"),
                "country": profile.get("country"),
                "exchange": profile.get("exchangeShortName"),
                "description": profile.get("description", "")[:500],
            }

            if self.redis:
                await self._set_cache(cache_key, result, FMP_CACHE_TTL)

            return result

        except Exception as e:
            logger.error("FMP profile error for %s: %s", symbol, str(e))
            return None

    def _build_params(self, filters: dict) -> dict:
        """Build FMP API query parameters from filter dict."""
        params: dict[str, Any] = {
            "apikey": self.api_key,
            "limit": 100,
            "country": filters.get("country", "US"),
            "isActivelyTrading": True,
        }

        # Market cap
        if filters.get("market_cap_min"):
            params["marketCapMoreThan"] = int(filters["market_cap_min"])
        if filters.get("market_cap_max"):
            params["marketCapLowerThan"] = int(filters["market_cap_max"])

        # P/E ratio
        if filters.get("pe_min"):
            params["priceEarningsRatioMoreThan"] = float(filters["pe_min"])
        if filters.get("pe_max"):
            params["priceEarningsRatioLowerThan"] = float(filters["pe_max"])

        # Dividend yield (FMP expects percentage: 3 = 3%)
        if filters.get("dividend_yield_min"):
            params["dividendMoreThan"] = float(filters["dividend_yield_min"])
        if filters.get("dividend_yield_max"):
            params["dividendLowerThan"] = float(filters["dividend_yield_max"])

        # Beta
        if filters.get("beta_min"):
            params["betaMoreThan"] = float(filters["beta_min"])
        if filters.get("beta_max"):
            params["betaLowerThan"] = float(filters["beta_max"])

        # Price
        if filters.get("price_min"):
            params["priceMoreThan"] = float(filters["price_min"])
        if filters.get("price_max"):
            params["priceLowerThan"] = float(filters["price_max"])

        # Volume
        if filters.get("volume_min"):
            params["volumeMoreThan"] = int(filters["volume_min"])

        # Sector / Industry
        if filters.get("sector"):
            params["sector"] = filters["sector"]
        if filters.get("industry"):
            params["industry"] = filters["industry"]

        # Exchange filter for major US exchanges
        params["exchange"] = "NYSE,NASDAQ,AMEX"

        return params

    def _parse_stock(self, stock: dict) -> dict:
        """Parse an FMP screener result into our standard format."""
        return {
            "symbol": stock.get("symbol", ""),
            "company_name": stock.get("companyName", ""),
            "sector": stock.get("sector"),
            "industry": stock.get("industry"),
            "market_cap": stock.get("marketCap"),
            "price": stock.get("price"),
            "beta": stock.get("beta"),
            "volume": stock.get("volume"),
            "dividend_yield": stock.get("lastAnnualDividend"),
            "pe_trailing": None,  # Not in screener response, needs enrichment
            "exchange": stock.get("exchangeShortName"),
            "country": stock.get("country"),
            "data_source": "fmp",
        }

    async def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached data from Redis."""
        if not self.redis:
            return None
        try:
            import json
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None

    async def _set_cache(self, key: str, data: Any, ttl: int) -> None:
        """Set data in Redis cache."""
        if not self.redis:
            return
        try:
            import json
            await self.redis.set(key, json.dumps(data), ex=ttl)
        except Exception:
            pass


def _hash_filters(filters: dict) -> str:
    """Create a simple hash key from filters for caching."""
    import hashlib
    import json
    raw = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]
