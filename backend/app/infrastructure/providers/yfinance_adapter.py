"""yfinance adapter — wraps the existing market_data_service for backward compatibility."""

from datetime import date, datetime
from decimal import Decimal

from app.infrastructure.providers.base import (
    CompanyProfile,
    MarketDataAdapter,
    PriceBar,
    QuoteData,
)


class YFinanceAdapter:
    """Market data adapter using yfinance (fallback/prototype provider)."""

    def provider_name(self) -> str:
        return "yfinance"

    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Fetch quote data from yfinance (runs in thread executor)."""
        import asyncio
        import yfinance as yf

        def _fetch():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                if not info or "regularMarketPrice" not in info:
                    return None
                return QuoteData(
                    symbol=symbol,
                    current_price=Decimal(str(info.get("regularMarketPrice", 0))) if info.get("regularMarketPrice") else None,
                    previous_close=Decimal(str(info.get("previousClose", 0))) if info.get("previousClose") else None,
                    day_high=Decimal(str(info.get("dayHigh", 0))) if info.get("dayHigh") else None,
                    day_low=Decimal(str(info.get("dayLow", 0))) if info.get("dayLow") else None,
                    volume=info.get("volume"),
                    average_volume=info.get("averageVolume"),
                    fifty_two_week_low=Decimal(str(info.get("fiftyTwoWeekLow", 0))) if info.get("fiftyTwoWeekLow") else None,
                    fifty_two_week_high=Decimal(str(info.get("fiftyTwoWeekHigh", 0))) if info.get("fiftyTwoWeekHigh") else None,
                    market_cap=info.get("marketCap"),
                    pe_trailing=Decimal(str(info.get("trailingPE", 0))) if info.get("trailingPE") else None,
                    pe_forward=Decimal(str(info.get("forwardPE", 0))) if info.get("forwardPE") else None,
                    beta=Decimal(str(info.get("beta", 0))) if info.get("beta") else None,
                    dividend_yield=Decimal(str(info.get("dividendYield", 0))) if info.get("dividendYield") else None,
                    price_to_book=Decimal(str(info.get("priceToBook", 0))) if info.get("priceToBook") else None,
                    provider_name="yfinance",
                    last_fetched=datetime.utcnow(),
                )
            except Exception:
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)

    async def get_historical(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        """Fetch historical price data from yfinance."""
        import asyncio
        import yfinance as yf

        def _fetch():
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start.isoformat(), end=end.isoformat())
                bars = []
                for idx, row in df.iterrows():
                    bars.append(PriceBar(
                        date=idx.date(),
                        open=Decimal(str(row["Open"])),
                        high=Decimal(str(row["High"])),
                        low=Decimal(str(row["Low"])),
                        close=Decimal(str(row["Close"])),
                        volume=int(row["Volume"]),
                    ))
                return bars
            except Exception:
                return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)

    async def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        """Fetch company profile from yfinance."""
        import asyncio
        import yfinance as yf

        def _fetch():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                if not info:
                    return None
                return CompanyProfile(
                    symbol=symbol,
                    company_name=info.get("longName") or info.get("shortName"),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    description=info.get("longBusinessSummary"),
                    website=info.get("website"),
                    market_cap=info.get("marketCap"),
                    provider_name="yfinance",
                )
            except Exception:
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)

    async def get_batch_quotes(self, symbols: list[str]) -> dict[str, QuoteData]:
        """Fetch quotes for multiple symbols."""
        results = {}
        for symbol in symbols:
            quote = await self.get_quote(symbol)
            if quote:
                results[symbol] = quote
        return results
