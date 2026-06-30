"""EODHD adapter for market signals.

Provides technical market signals:
- 50-day / 200-day New High / New Low
- Wall Street consensus signals
- Volume anomalies

Free tier: 20 requests/day
Cache TTL: 6 hours
"""

import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EODHD_BASE_URL = "https://eodhistoricaldata.com/api"
EODHD_CACHE_TTL = 21600  # 6 hours


class EODHDSignalAdapter:
    """Adapter for EODHD market signals API."""

    def __init__(self, redis_client=None):
        self.api_key = settings.eodhd_api_key
        self.redis = redis_client
        self.base_url = EODHD_BASE_URL

    async def get_signals(self, signal_type: str = "50d_new_hi") -> list[dict]:
        """Get market signal data from EODHD.

        Signal types:
        - 50d_new_hi: Stocks making 50-day new highs
        - 50d_new_lo: Stocks making 50-day new lows
        - 200d_new_hi: Stocks making 200-day new highs
        - 200d_new_lo: Stocks making 200-day new lows
        - wallstreet_hi: Wall Street consensus buy signals

        Returns list of symbols matching the signal.
        """
        if not self.api_key:
            logger.warning("EODHD API key not configured")
            return []

        cache_key = f"eodhd_signal:{signal_type}"
        if self.redis:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                return cached

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.base_url}/screener",
                    params={
                        "api_token": self.api_key,
                        "sort": "market_capitalization.desc",
                        "filters": f'[["market_capitalization",">",1000000000],["exchange","=","us"]]',
                        "signals": signal_type,
                        "limit": 50,
                        "fmt": "json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, list):
                # EODHD might return {"data": [...]} format
                data = data.get("data", data.get("symbols", []))

            results = []
            for item in data[:50]:
                if isinstance(item, dict):
                    results.append({
                        "symbol": item.get("code", item.get("symbol", "")),
                        "name": item.get("name", ""),
                        "exchange": item.get("exchange", ""),
                        "signal": signal_type,
                        "market_cap": item.get("market_capitalization"),
                    })
                elif isinstance(item, str):
                    results.append({"symbol": item, "signal": signal_type})

            if self.redis:
                await self._set_cache(cache_key, results, EODHD_CACHE_TTL)

            return results

        except httpx.HTTPStatusError as e:
            logger.error("EODHD HTTP error: %s", e.response.status_code)
            return []
        except Exception as e:
            logger.error("EODHD signal error: %s", str(e))
            return []

    async def get_new_high_symbols(self, days: int = 50) -> set[str]:
        """Get set of symbols making new highs."""
        signal = f"{days}d_new_hi"
        results = await self.get_signals(signal)
        return {r["symbol"] for r in results if r.get("symbol")}

    async def get_new_low_symbols(self, days: int = 200) -> set[str]:
        """Get set of symbols making new lows."""
        signal = f"{days}d_new_lo"
        results = await self.get_signals(signal)
        return {r["symbol"] for r in results if r.get("symbol")}

    async def get_wall_street_consensus(self) -> set[str]:
        """Get symbols with Wall Street consensus buy signals."""
        results = await self.get_signals("wallstreet_hi")
        return {r["symbol"] for r in results if r.get("symbol")}

    async def _get_cache(self, key: str) -> Optional[Any]:
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
        if not self.redis:
            return
        try:
            import json
            await self.redis.set(key, json.dumps(data), ex=ttl)
        except Exception:
            pass
