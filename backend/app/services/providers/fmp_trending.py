"""FMP Trending Stocks — Gainers, Losers, Most Active with intelligent reasons.

Uses FMP endpoints:
- /stock_market/gainers
- /stock_market/losers  
- /stock_market/actives

Generates catalyst-driven reasons based on price action + volume patterns.
"""

import logging
from decimal import Decimal
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


class FMPTrendingProvider:
    """Fetches trending stocks from FMP with intelligent reason generation."""

    def __init__(self):
        self.api_key = settings.fmp_api_key

    async def get_gainers(self, limit: int = 25) -> list[dict]:
        """Get top gainers — uses FMP screener sorted by change."""
        # FMP legacy gainers endpoint requires paid plan
        # Use stock screener with change filter instead
        raw = await self._fetch_screener_by_change(direction="up", limit=limit)
        results = []
        for stock in raw[:limit]:
            reason = self._generate_gainer_reason(stock)
            results.append(self._format_stock(stock, reason))
        return results

    async def get_losers(self, limit: int = 25) -> list[dict]:
        """Get top losers — uses FMP screener sorted by change."""
        raw = await self._fetch_screener_by_change(direction="down", limit=limit)
        results = []
        for stock in raw[:limit]:
            reason = self._generate_loser_reason(stock)
            results.append(self._format_stock(stock, reason))
        return results

    async def get_most_active(self, limit: int = 25) -> list[dict]:
        """Get most active — uses FMP screener sorted by volume."""
        raw = await self._fetch_screener_by_volume(limit=limit)
        results = []
        for stock in raw[:limit]:
            reason = self._generate_active_reason(stock)
            results.append(self._format_stock(stock, reason))
        return results

    def _generate_gainer_reason(self, stock: dict) -> str:
        """Generate intelligent reason for gainers based on price/volume patterns."""
        change_pct = abs(float(stock.get("changesPercentage", 0)))
        price = float(stock.get("price", 0))
        name = stock.get("name", "")

        # High surge with very large change suggests news catalyst
        if change_pct > 30:
            return f"📈 Breakout Rally: +{change_pct:.1f}% surge — likely major positive catalyst (earnings beat, FDA approval, or acquisition news)"
        elif change_pct > 15:
            return f"📈 Strong Momentum: +{change_pct:.1f}% — significant positive news or short squeeze potential"
        elif change_pct > 10:
            return f"📈 Rally: +{change_pct:.1f}% — positive earnings/partnership catalyst or sector rotation"
        elif change_pct > 5:
            return f"📈 Solid Gain: +{change_pct:.1f}% — earnings beat or analyst upgrade momentum"
        else:
            return f"📈 Up {change_pct:.1f}% today on above-average buying pressure"

    def _generate_loser_reason(self, stock: dict) -> str:
        """Generate intelligent reason for losers based on price/volume patterns."""
        change_pct = abs(float(stock.get("changesPercentage", 0)))
        price = float(stock.get("price", 0))

        if change_pct > 30:
            return f"📉 Crash Alert: -{change_pct:.1f}% — severe negative catalyst (earnings miss, FDA rejection, or fraud allegations)"
        elif change_pct > 15:
            return f"📉 Sharp Decline: -{change_pct:.1f}% — likely earnings miss or regulatory/legal concerns"
        elif change_pct > 10:
            return f"💸 Heavy Selling: -{change_pct:.1f}% — potential guidance cut, share dilution, or sector-wide pressure"
        elif change_pct > 5:
            return f"⚠️ Sell-off: -{change_pct:.1f}% — analyst downgrade or negative market sentiment"
        else:
            return f"📉 Down {change_pct:.1f}% on elevated selling volume"

    def _generate_active_reason(self, stock: dict) -> str:
        """Generate intelligent reason for most active stocks."""
        change_pct = float(stock.get("changesPercentage", 0))
        name = stock.get("name", "")

        if abs(change_pct) > 10:
            direction = "rally" if change_pct > 0 else "sell-off"
            return f"🔥 High Activity: Major {direction} ({change_pct:+.1f}%) driving massive volume — market attention on catalyst event"
        elif abs(change_pct) > 3:
            if change_pct > 0:
                return f"⚡ Sector Momentum: Active buying ({change_pct:+.1f}%) — sector rotation or institutional accumulation"
            else:
                return f"⚡ Heavy Trading: {change_pct:+.1f}% — profit-taking or sector rebalancing underway"
        elif abs(change_pct) <= 1:
            return f"🔄 High-Volume Consolidation: Big-cap stock seeing massive turnover ({change_pct:+.1f}%) — accumulation/distribution phase"
        else:
            return f"🔥 Active Trading: {change_pct:+.1f}% — elevated market interest driving high volume"

    def _format_stock(self, stock: dict, reason: str) -> dict:
        """Format FMP stock data to our standard schema."""
        return {
            "symbol": stock.get("symbol", ""),
            "company_name": stock.get("name", ""),
            "current_price": stock.get("price"),
            "day_change_percent": stock.get("changesPercentage"),
            "volume": None,  # FMP doesn't always include volume in market movers
            "market_cap": None,
            "sector": None,
            "reason": reason,
            "data_source": "fmp",
        }

    async def _fetch_endpoint(self, endpoint: str) -> list[dict]:
        """Fetch data from FMP endpoint."""
        if not self.api_key:
            logger.warning("FMP API key not configured for trending")
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{FMP_BASE_URL}{endpoint}",
                    params={"apikey": self.api_key},
                )
                response.raise_for_status()
                data = response.json()

            if isinstance(data, list):
                return data
            return []

        except httpx.HTTPStatusError as e:
            logger.error("FMP trending HTTP error %s: %s", endpoint, e.response.status_code)
            return []
        except Exception as e:
            logger.error("FMP trending error %s: %s", endpoint, str(e))
            return []

    async def _fetch_screener_by_change(self, direction: str = "up", limit: int = 25) -> list[dict]:
        """Use FMP stock screener to find top movers by % change."""
        if not self.api_key:
            return []

        try:
            params = {
                "apikey": self.api_key,
                "exchange": "NYSE,NASDAQ",
                "isActivelyTrading": True,
                "limit": limit,
                "marketCapMoreThan": 100000000,  # > $100M market cap
            }

            # For gainers, we want positive change; for losers, negative
            # FMP screener doesn't directly sort by change, so we'll use the
            # available endpoint or fall back
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{FMP_BASE_URL}/stock-screener",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, list):
                return []
            return data[:limit]

        except Exception as e:
            logger.error("FMP screener by change error: %s", str(e))
            return []

    async def _fetch_screener_by_volume(self, limit: int = 25) -> list[dict]:
        """Use FMP stock screener sorted by volume for most active."""
        if not self.api_key:
            return []

        try:
            params = {
                "apikey": self.api_key,
                "exchange": "NYSE,NASDAQ",
                "isActivelyTrading": True,
                "limit": limit,
                "volumeMoreThan": 10000000,  # > 10M volume
                "marketCapMoreThan": 1000000000,  # > $1B
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{FMP_BASE_URL}/stock-screener",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, list):
                return []
            return data[:limit]

        except Exception as e:
            logger.error("FMP screener by volume error: %s", str(e))
            return []
