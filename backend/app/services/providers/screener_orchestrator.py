"""Advanced Stock Screener Orchestrator.

Coordinates multiple providers to deliver enriched screening results:
1. FMP — Primary bulk screener (server-side filtering)
2. EODHD — Market signals enrichment (50d/200d new hi/lo)
3. yfinance — Fallback + historical financials

Provider chain: FMP → EODHD signals → yfinance fallback
"""

import logging
from typing import Any, Optional

import redis.asyncio as redis

from app.services.providers.fmp_adapter import FMPScreenerAdapter
from app.services.providers.eodhd_adapter import EODHDSignalAdapter

logger = logging.getLogger(__name__)

# System presets with their filter configurations
SYSTEM_PRESETS = {
    "garp": {
        "name": "GARP (Growth At Reasonable Price)",
        "description": "หุ้นเติบโตในราคาที่เหมาะสม — PEG ต่ำ + P/E สมเหตุสมผล",
        "filters": {
            "peg_ratio_min": 0.1, "peg_ratio_max": 1.2,
            "pe_min": 5, "pe_max": 25,
        },
    },
    "deep_value": {
        "name": "Deep Value",
        "description": "หุ้นราคาถูกกว่ามูลค่าทางบัญชี — P/B ต่ำ + P/E ต่ำมาก",
        "filters": {
            "pe_max": 10,
            "price_to_book_max": 1.0,
            "dividend_yield_min": 2.0,
        },
    },
    "turnaround": {
        "name": "Turnaround (หุ้นฟื้นตัว)",
        "description": "หุ้นพลิกจากขาดทุน กำลังกลับมาเติบโต — Beta สูง + P/E เริ่มเป็นบวก",
        "filters": {
            "pe_min": 0, "pe_max": 30,
            "beta_min": 1.0,
        },
    },
    "cash_cow": {
        "name": "Cash Cow (หุ้นผลิตเงินสด)",
        "description": "บริษัทมั่นคง กระแสเงินสดแข็ง ปันผลสม่ำเสมอ",
        "filters": {
            "pe_max": 15,
            "dividend_yield_min": 3.5,
            "market_cap_min": 1000000000,
        },
    },
    "wall_street_consensus": {
        "name": "Wall Street Consensus",
        "description": "หุ้นที่นักวิเคราะห์แนะนำตรงกัน — Large Cap + Analyst Buy/Strong Buy",
        "filters": {
            "market_cap_min": 2000000000,
            "analyst_rating": "buy",
        },
    },
    "high_dividend": {
        "name": "High Dividend",
        "description": "หุ้นปันผลสูง ผันผวนต่ำ — Yield > 5% + Beta ต่ำ",
        "filters": {
            "dividend_yield_min": 5.0,
            "pe_max": 12,
            "beta_max": 0.8,
        },
    },
    "low_pe_value": {
        "name": "Low P/E Value",
        "description": "หุ้น P/E ต่ำ ราคาถูกเชิงปริมาณ",
        "filters": {
            "pe_min": 1, "pe_max": 12,
            "price_to_book_max": 1.5,
        },
    },
    "mega_cap_growth": {
        "name": "Mega Cap Growth",
        "description": "หุ้นยักษ์ใหญ่เติบโตสูง (Magnificent 7 style) — Market Cap > $200B",
        "filters": {
            "market_cap_min": 200000000000,
            "pe_min": 20,
            "beta_min": 1.0,
        },
    },
    "magic_formula": {
        "name": "Magic Formula (Greenblatt)",
        "description": "สูตรมหัศจรรย์ — หุ้นดีราคาถูก (ROC สูง + Earnings Yield สูง) — P/E ต่ำ + ROE สูง",
        "filters": {
            "pe_max": 15,
            "roe_min": 15,
        },
    },
    "can_slim": {
        "name": "CAN SLIM (O'Neil)",
        "description": "หุ้นผู้นำเติบโตแรง + Momentum — EPS Growth > 20% + Beta สูง",
        "filters": {
            "beta_min": 1.2,
            "market_cap_min": 500000000,
            "eps_growth_min": 20,
        },
    },
    "dividend_aristocrats": {
        "name": "Dividend Aristocrats",
        "description": "ราชาปันผลสม่ำเสมอ — Large Cap + จ่ายปันผลต่อเนื่องยาวนาน",
        "filters": {
            "market_cap_min": 10000000000,
            "dividend_yield_min": 2.5,
        },
    },
    "defensive_moat": {
        "name": "Defensive Moat (Buffett Style)",
        "description": "หุ้นปลอดภัยมีป้อมปราการ — Beta ต่ำ + Net Profit Margin > 15%",
        "filters": {
            "beta_max": 0.75,
            "price_to_book_max": 3.0,
            "net_margin_min": 15,
        },
    },
    "high_momentum": {
        "name": "High Momentum",
        "description": "หุ้นขาขึ้นรุนแรง — Beta สูง + ราคาเหนือ 50d & 200d SMA",
        "filters": {
            "beta_min": 1.3,
            "price_above_50d_ma": True,
            "price_above_200d_ma": True,
        },
    },
    "net_net_graham": {
        "name": "Net-Net (Benjamin Graham)",
        "description": "หุ้นก้นบุหรี่ — ราคาต่ำกว่าครึ่งของ Book Value",
        "filters": {
            "price_to_book_max": 0.5,
            "pe_max": 8,
        },
    },
    "quality_growth": {
        "name": "Quality Growth",
        "description": "หุ้นเติบโตเชิงคุณภาพ — หนี้ต่ำ (D/E < 0.5) + ROE > 18% + PEG ดี",
        "filters": {
            "peg_ratio_max": 1.5,
            "debt_to_equity_max": 0.5,
            "roe_min": 18,
        },
    },
    "small_cap_gems": {
        "name": "Small Cap Gems",
        "description": "หุ้นเล็กพริกขี้หนู — โอกาสเป็น Multi-bagger",
        "filters": {
            "market_cap_min": 100000000,
            "market_cap_max": 2000000000,
            "pe_max": 20,
        },
    },
    "under_followed": {
        "name": "Under-Followed Small Caps",
        "description": "หุ้นดีที่ตลาดมองข้าม — สถาบันยังไม่เข้าเก็บ",
        "filters": {
            "market_cap_max": 1000000000,
            "pe_max": 12,
            "price_to_book_max": 1.2,
        },
    },
    "short_squeeze": {
        "name": "Short Squeeze Candidate",
        "description": "หุ้นมีโอกาส Short Squeeze — Beta สูงมาก + Short Interest > 15%",
        "filters": {
            "beta_min": 1.4,
            "short_interest_min": 15,
        },
    },
}

# Available filter metrics with metadata
AVAILABLE_FILTERS = [
    {"key": "pe_min", "label": "P/E Ratio Min", "type": "number", "min": 0, "max": 200, "step": 1, "group": "Valuation"},
    {"key": "pe_max", "label": "P/E Ratio Max", "type": "number", "min": 0, "max": 200, "step": 1, "group": "Valuation"},
    {"key": "peg_ratio_min", "label": "PEG Ratio Min", "type": "number", "min": 0, "max": 10, "step": 0.1, "group": "Valuation"},
    {"key": "peg_ratio_max", "label": "PEG Ratio Max", "type": "number", "min": 0, "max": 10, "step": 0.1, "group": "Valuation"},
    {"key": "price_to_book_min", "label": "Price/Book Min", "type": "number", "min": 0, "max": 50, "step": 0.1, "group": "Valuation"},
    {"key": "price_to_book_max", "label": "Price/Book Max", "type": "number", "min": 0, "max": 50, "step": 0.1, "group": "Valuation"},
    {"key": "dividend_yield_min", "label": "Dividend Yield Min (%)", "type": "number", "min": 0, "max": 20, "step": 0.1, "group": "Income"},
    {"key": "dividend_yield_max", "label": "Dividend Yield Max (%)", "type": "number", "min": 0, "max": 20, "step": 0.1, "group": "Income"},
    {"key": "market_cap_min", "label": "Market Cap Min ($)", "type": "number", "min": 0, "max": 5000000000000, "step": 1000000000, "group": "Size"},
    {"key": "market_cap_max", "label": "Market Cap Max ($)", "type": "number", "min": 0, "max": 5000000000000, "step": 1000000000, "group": "Size"},
    {"key": "beta_min", "label": "Beta Min", "type": "number", "min": -2, "max": 5, "step": 0.1, "group": "Risk"},
    {"key": "beta_max", "label": "Beta Max", "type": "number", "min": -2, "max": 5, "step": 0.1, "group": "Risk"},
    {"key": "price_min", "label": "Price Min ($)", "type": "number", "min": 0, "max": 10000, "step": 1, "group": "Price"},
    {"key": "price_max", "label": "Price Max ($)", "type": "number", "min": 0, "max": 10000, "step": 1, "group": "Price"},
    {"key": "volume_min", "label": "Volume Min", "type": "number", "min": 0, "max": 500000000, "step": 100000, "group": "Liquidity"},
    {"key": "sector", "label": "Sector", "type": "select", "options": ["Technology", "Healthcare", "Financial Services", "Consumer Cyclical", "Communication Services", "Industrials", "Consumer Defensive", "Energy", "Utilities", "Real Estate", "Basic Materials"], "group": "Classification"},
    {"key": "industry", "label": "Industry", "type": "text", "group": "Classification"},
    {"key": "roe_min", "label": "ROE Min (%)", "type": "number", "min": 0, "max": 100, "step": 1, "group": "Profitability"},
    {"key": "roe_max", "label": "ROE Max (%)", "type": "number", "min": 0, "max": 100, "step": 1, "group": "Profitability"},
    {"key": "net_margin_min", "label": "Net Profit Margin Min (%)", "type": "number", "min": 0, "max": 100, "step": 1, "group": "Profitability"},
    {"key": "eps_growth_min", "label": "EPS Growth Min (%)", "type": "number", "min": -100, "max": 500, "step": 5, "group": "Growth"},
    {"key": "debt_to_equity_max", "label": "Debt/Equity Max", "type": "number", "min": 0, "max": 10, "step": 0.1, "group": "Risk"},
    {"key": "short_interest_min", "label": "Short Interest Min (%)", "type": "number", "min": 0, "max": 100, "step": 1, "group": "Risk"},
    {"key": "analyst_rating", "label": "Analyst Consensus", "type": "select", "options": ["strong_buy", "buy", "hold", "sell"], "group": "Analyst"},
    {"key": "price_above_50d_ma", "label": "Price Above 50-Day MA", "type": "select", "options": ["true", "false"], "group": "Technical"},
    {"key": "price_above_200d_ma", "label": "Price Above 200-Day MA", "type": "select", "options": ["true", "false"], "group": "Technical"},
]


class ScreenerOrchestrator:
    """Orchestrates multi-provider stock screening."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.fmp = FMPScreenerAdapter(redis_client)
        self.eodhd = EODHDSignalAdapter(redis_client)

    async def execute_screen(self, filters: dict, signals: list[str] = None) -> dict:
        """Execute advanced screening with provider chain.

        Pipeline (ลำดับถูกต้อง):
        1. ดึงข้อมูลหลักจาก FMP (หรือ yfinance fallback)
        2. เอาพวก N/A ไปเติมข้อมูลก่อน (Enrich FIRST) 
        3. กรองเข้มงวดเป็นขั้นตอนสุดท้าย (Filter LAST)
        4. EODHD signals (optional)
        """
        providers_used = []
        provider_status = {}
        results = []

        # Step 1: ดึงข้อมูลหลัก — FMP primary screen
        try:
            fmp_results = await self.fmp.screen_stocks(filters)
            if fmp_results:
                results = fmp_results
                providers_used.append("fmp")
                provider_status["fmp"] = "success"
            else:
                provider_status["fmp"] = "empty"
        except Exception as e:
            provider_status["fmp"] = f"error: {str(e)[:50]}"
            logger.warning("FMP failed, falling back to yfinance: %s", str(e))

        # Fallback to yfinance if FMP returned nothing
        if not results:
            try:
                results = await self._yfinance_fallback(filters)
                if results:
                    providers_used.append("yfinance")
                    provider_status["yfinance"] = "success"
                else:
                    provider_status["yfinance"] = "empty"
            except Exception as e:
                provider_status["yfinance"] = f"error: {str(e)[:50]}"

        # Step 2: เติมข้อมูลก่อน (Enrich FIRST) — อุด N/A ด้วย yfinance
        if results:
            try:
                results = await self._enrich_missing_data(results[:100])
                if "yfinance" not in providers_used:
                    providers_used.append("yfinance")
                provider_status["yfinance_enrich"] = "success"
            except Exception as e:
                provider_status["yfinance_enrich"] = f"error: {str(e)[:50]}"

        # Step 3: กรองเข้มเป็นขั้นตอนสุดท้าย (Filter LAST) — หลังจากเติมข้อมูลเต็มแล้ว
        if results and filters:
            results = self._strict_post_filter(results, filters)

        # Step 4: EODHD signal enrichment (optional)
        if signals and results:
            try:
                results = await self._enrich_with_signals(results, signals)
                providers_used.append("eodhd")
                provider_status["eodhd"] = "success"
            except Exception as e:
                provider_status["eodhd"] = f"error: {str(e)[:50]}"

        return {
            "results": results,
            "total_matches": len(results),
            "providers_used": providers_used,
            "provider_status": provider_status,
        }

    async def get_system_presets(self) -> list[dict]:
        """Return all system preset definitions."""
        return [
            {"id": key, **value}
            for key, value in SYSTEM_PRESETS.items()
        ]

    async def get_available_filters(self) -> list[dict]:
        """Return metadata for all available filter metrics."""
        return AVAILABLE_FILTERS

    async def _enrich_missing_data(self, results: list[dict]) -> list[dict]:
        """Enrich stocks with missing data (N/A) using yfinance Ticker.info.
        
        For each stock with missing key metrics, fetches from yfinance to fill gaps.
        Limited to first 20 stocks to avoid rate limiting.
        """
        import asyncio
        import yfinance as yf

        enrichment_fields = {
            "pe_trailing": "trailingPE",
            "price_to_book": "priceToBook",
            "peg_ratio": "pegRatio",
            "dividend_yield": "dividendYield",
            "beta": "beta",
            "roe": "returnOnEquity",
            "net_margin": "profitMargins",
            "market_cap": "marketCap",
            "sector": "sector",
            "short_interest": "shortPercentOfFloat",
            "debt_to_equity": "debtToEquity",
        }

        # Only enrich stocks that have N/A values
        stocks_to_enrich = []
        for stock in results[:100]:
            has_missing = any(stock.get(k) is None for k in ["pe_trailing", "price_to_book", "beta", "sector", "peg_ratio", "roe", "short_interest", "debt_to_equity"])
            if has_missing:
                stocks_to_enrich.append(stock)

        if not stocks_to_enrich:
            return results

        loop = asyncio.get_event_loop()

        async def enrich_one(stock: dict) -> None:
            sym = stock.get("symbol", "")
            if not sym:
                return
            try:
                info = await loop.run_in_executor(None, lambda: yf.Ticker(sym).info)
                if not info:
                    return
                for our_key, yf_key in enrichment_fields.items():
                    if stock.get(our_key) is None and info.get(yf_key) is not None:
                        val = info[yf_key]
                        if our_key in ("roe", "net_margin") and val is not None:
                            stock[our_key] = round(float(val) * 100, 2)  # Convert ratio to %
                        elif our_key == "short_interest" and val is not None:
                            stock[our_key] = round(float(val) * 100, 2)  # Convert ratio to %
                        elif our_key == "debt_to_equity" and val is not None:
                            stock[our_key] = round(float(val), 2)
                        else:
                            stock[our_key] = val
                # Update data source
                stock["data_source"] = "yfi+enriched"
            except Exception:
                pass

        # Enrich in parallel (max 10 concurrent)
        sem = asyncio.Semaphore(10)
        async def bounded_enrich(stock):
            async with sem:
                await enrich_one(stock)

        await asyncio.gather(*[bounded_enrich(s) for s in stocks_to_enrich])
        return results

    def _strict_post_filter(self, results: list[dict], filters: dict) -> list[dict]:
        """Remove stocks that have N/A for metrics that are actively being filtered.
        
        Only applies to metrics that the system CAN reliably provide data for.
        Soft filters (metrics that are rarely available) don't cause exclusion.
        """
        # Hard filters: these metrics CAN be reliably enriched via yfinance
        # If user sets these AND the stock still has N/A after enrichment → exclude
        HARD_FILTER_KEYS = {
            "pe_min": "pe_trailing", "pe_max": "pe_trailing",
            "peg_ratio_min": "peg_ratio", "peg_ratio_max": "peg_ratio",
            "price_to_book_min": "price_to_book", "price_to_book_max": "price_to_book",
            "dividend_yield_min": "dividend_yield", "dividend_yield_max": "dividend_yield",
            "beta_min": "beta", "beta_max": "beta",
            "market_cap_min": "market_cap", "market_cap_max": "market_cap",
            "roe_min": "roe", "roe_max": "roe",
            "short_interest_min": "short_interest", "short_interest_max": "short_interest",
            "debt_to_equity_max": "debt_to_equity",
            "net_margin_min": "net_margin",
        }

        # Soft filters: these metrics are NOT reliably available from screener/enrichment
        # They show in UI but don't cause exclusion if N/A
        # Examples: short_interest, debt_to_equity, price_above_50d_ma, eps_growth, net_margin, analyst_rating

        # Find which data keys MUST have values (only hard filters)
        required_keys = set()
        for fk, dk in HARD_FILTER_KEYS.items():
            if filters.get(fk) is not None:
                required_keys.add(dk)

        if not required_keys:
            return results

        # Also apply numeric range checks for hard filters
        filtered = []
        for stock in results:
            passes = True
            for key in required_keys:
                val = stock.get(key)
                if val is None:
                    passes = False
                    break
                # Apply range check
                num_val = float(val)
                # Check min constraints
                min_key = f"{key}_min" if not key.endswith("_trailing") else f"pe_min"
                max_key = f"{key}_max" if not key.endswith("_trailing") else f"pe_max"
                
                # Map back to filter keys
                for fk, dk in HARD_FILTER_KEYS.items():
                    if dk == key and fk.endswith("_min") and filters.get(fk) is not None:
                        if num_val < float(filters[fk]):
                            passes = False
                            break
                    elif dk == key and fk.endswith("_max") and filters.get(fk) is not None:
                        if num_val > float(filters[fk]):
                            passes = False
                            break
                if not passes:
                    break
            if passes:
                filtered.append(stock)

        return filtered

    async def _enrich_with_signals(self, results: list[dict], signals: list[str]) -> list[dict]:
        """Filter/enrich results using EODHD signals."""
        # Collect signal data
        signal_symbols: dict[str, set[str]] = {}

        for signal in signals:
            if signal == "wallstreet_hi":
                signal_symbols["wallstreet_hi"] = await self.eodhd.get_wall_street_consensus()
            elif signal == "not_200d_new_lo":
                new_lows = await self.eodhd.get_new_low_symbols(200)
                signal_symbols["not_200d_new_lo"] = new_lows
            elif signal == "50d_new_hi":
                signal_symbols["50d_new_hi"] = await self.eodhd.get_new_high_symbols(50)

        # Apply signal filters
        filtered = []
        for stock in results:
            sym = stock.get("symbol", "")
            include = True

            if "wallstreet_hi" in signal_symbols:
                if sym not in signal_symbols["wallstreet_hi"]:
                    include = False

            if "not_200d_new_lo" in signal_symbols:
                if sym in signal_symbols["not_200d_new_lo"]:
                    include = False  # Exclude stocks at 200d new lows

            if "50d_new_hi" in signal_symbols:
                if sym not in signal_symbols["50d_new_hi"]:
                    include = False

            if include:
                filtered.append(stock)

        return filtered

    async def _yfinance_fallback(self, filters: dict) -> list[dict]:
        """Fallback to existing yfinance screener when FMP fails."""
        from app.services.screener_service import ScreenerService
        from app.schemas.screener import ScreenerFilterCreate

        # Map our filters to the existing ScreenerFilterCreate schema
        screener_filters = ScreenerFilterCreate(
            pe_min=filters.get("pe_min"),
            pe_max=filters.get("pe_max"),
            dividend_yield_min=filters.get("dividend_yield_min"),
            dividend_yield_max=filters.get("dividend_yield_max"),
            market_cap_min=filters.get("market_cap_min"),
            market_cap_max=filters.get("market_cap_max"),
            sector=filters.get("sector"),
            industry=filters.get("industry"),
            peg_ratio_min=filters.get("peg_ratio_min"),
            peg_ratio_max=filters.get("peg_ratio_max"),
            price_to_book_min=filters.get("price_to_book_min"),
            price_to_book_max=filters.get("price_to_book_max"),
            beta_min=filters.get("beta_min"),
            beta_max=filters.get("beta_max"),
        )

        # Use existing screener service (yfinance-based)
        # This requires a db session which we don't have here, so create minimal service
        from sqlalchemy.ext.asyncio import AsyncSession
        service = ScreenerService.__new__(ScreenerService)
        service.db = None  # Not needed for search

        try:
            response = await service.search(screener_filters)
            return [
                {
                    "symbol": r.stock_symbol,
                    "company_name": r.company_name,
                    "sector": r.sector,
                    "industry": r.industry,
                    "market_cap": r.market_cap,
                    "price": float(r.current_price) if r.current_price else None,
                    "pe_trailing": float(r.pe_trailing) if r.pe_trailing else None,
                    "dividend_yield": float(r.dividend_yield) if r.dividend_yield else None,
                    "beta": float(r.beta) if r.beta else None,
                    "price_to_book": float(r.price_to_book) if r.price_to_book else None,
                    "data_source": "yfinance",
                }
                for r in response.results
            ]
        except Exception as e:
            logger.error("yfinance fallback failed: %s", str(e))
            return []
