"""Financial Modeling Prep (FMP) adapter — primary market data provider for MVP."""

from datetime import date, datetime
from decimal import Decimal

import httpx

from app.infrastructure.providers.base import (
    CompanyProfile,
    MarketDataAdapter,
    PriceBar,
    QuoteData,
)


class FMPAdapter:
    """Market data adapter using Financial Modeling Prep API."""

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def provider_name(self) -> str:
        return "fmp"

    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Fetch real-time quote from FMP."""
        if not self._api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/quote/{symbol}",
                    params={"apikey": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    return None
                item = data[0]
                return QuoteData(
                    symbol=symbol,
                    current_price=Decimal(str(item.get("price", 0))) if item.get("price") else None,
                    previous_close=Decimal(str(item.get("previousClose", 0))) if item.get("previousClose") else None,
                    day_high=Decimal(str(item.get("dayHigh", 0))) if item.get("dayHigh") else None,
                    day_low=Decimal(str(item.get("dayLow", 0))) if item.get("dayLow") else None,
                    volume=item.get("volume"),
                    average_volume=item.get("avgVolume"),
                    fifty_two_week_low=Decimal(str(item.get("yearLow", 0))) if item.get("yearLow") else None,
                    fifty_two_week_high=Decimal(str(item.get("yearHigh", 0))) if item.get("yearHigh") else None,
                    market_cap=item.get("marketCap"),
                    pe_trailing=Decimal(str(item.get("pe", 0))) if item.get("pe") else None,
                    pe_forward=None,  # FMP quote doesn't include forward PE directly
                    beta=None,  # Available in profile endpoint
                    dividend_yield=None,  # Available in profile endpoint
                    price_to_book=None,
                    provider_name="fmp",
                    last_fetched=datetime.utcnow(),
                )
        except Exception:
            return None

    async def get_historical(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        """Fetch historical daily prices from FMP."""
        if not self._api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/historical-price-full/{symbol}",
                    params={
                        "apikey": self._api_key,
                        "from": start.isoformat(),
                        "to": end.isoformat(),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                historical = data.get("historical", [])
                bars = []
                for item in historical:
                    bars.append(PriceBar(
                        date=date.fromisoformat(item["date"]),
                        open=Decimal(str(item["open"])),
                        high=Decimal(str(item["high"])),
                        low=Decimal(str(item["low"])),
                        close=Decimal(str(item["close"])),
                        volume=int(item.get("volume", 0)),
                    ))
                return sorted(bars, key=lambda b: b.date)
        except Exception:
            return []

    async def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        """Fetch company profile from FMP."""
        if not self._api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/profile/{symbol}",
                    params={"apikey": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    return None
                item = data[0]
                return CompanyProfile(
                    symbol=symbol,
                    company_name=item.get("companyName"),
                    sector=item.get("sector"),
                    industry=item.get("industry"),
                    description=item.get("description"),
                    website=item.get("website"),
                    market_cap=item.get("mktCap"),
                    provider_name="fmp",
                )
        except Exception:
            return None

    async def get_batch_quotes(self, symbols: list[str]) -> dict[str, QuoteData]:
        """Fetch batch quotes from FMP (comma-separated symbols)."""
        if not self._api_key or not symbols:
            return {}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                symbol_str = ",".join(symbols[:50])  # FMP limits batch size
                resp = await client.get(
                    f"{self.BASE_URL}/quote/{symbol_str}",
                    params={"apikey": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                results = {}
                for item in data:
                    sym = item.get("symbol", "")
                    results[sym] = QuoteData(
                        symbol=sym,
                        current_price=Decimal(str(item.get("price", 0))) if item.get("price") else None,
                        previous_close=Decimal(str(item.get("previousClose", 0))) if item.get("previousClose") else None,
                        day_high=Decimal(str(item.get("dayHigh", 0))) if item.get("dayHigh") else None,
                        day_low=Decimal(str(item.get("dayLow", 0))) if item.get("dayLow") else None,
                        volume=item.get("volume"),
                        average_volume=item.get("avgVolume"),
                        fifty_two_week_low=Decimal(str(item.get("yearLow", 0))) if item.get("yearLow") else None,
                        fifty_two_week_high=Decimal(str(item.get("yearHigh", 0))) if item.get("yearHigh") else None,
                        market_cap=item.get("marketCap"),
                        pe_trailing=Decimal(str(item.get("pe", 0))) if item.get("pe") else None,
                        provider_name="fmp",
                        last_fetched=datetime.utcnow(),
                    )
                return results
        except Exception:
            return {}
