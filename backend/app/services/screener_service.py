"""Stock Screener service - Business logic for stock screening and preset management."""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screener_preset import ScreenerPreset
from app.schemas.screener import (
    ScreenerFilterCreate,
    ScreenerPresetCreate,
    ScreenerResultEntry,
    ScreenerSearchResponse,
)

logger = logging.getLogger(__name__)

# Maximum results per screener query
MAX_SCREENER_RESULTS = 100


class ScreenerService:
    """Service for stock screening using yfinance and managing screener presets.

    Provides:
    - search: Execute a stock screener query against Yahoo Finance
    - list_presets: List saved presets for a user
    - create_preset: Save a new preset
    - delete_preset: Delete a saved preset

    All preset operations are scoped to a specific user_id for data isolation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, filters: ScreenerFilterCreate) -> ScreenerSearchResponse:
        """Execute a stock screener query using yfinance.

        Builds an EquityQuery from the provided filter criteria and executes
        it against Yahoo Finance's screener API.

        Args:
            filters: The screener filter criteria (PE range, dividend yield range,
                     market cap range, sector, industry, beta range, price_to_book range).

        Returns:
            ScreenerSearchResponse with matched stocks (limited to 50 results).
        """
        try:
            query = self._build_equity_query(filters)
            if query is None:
                # No filters specified, return empty results
                return ScreenerSearchResponse(results=[], total_matches=0)

            response = await self._execute_screen(query)
            results = self._parse_screen_results(response)

            # Post-filter for fields not supported by yfinance screener query
            results = self._apply_post_filters(results, filters)

            return results
        except Exception as e:
            logger.warning("Screener search failed: %s", str(e))
            raise HTTPException(
                status_code=502,
                detail=f"Failed to execute screener query: {str(e)}",
            )

    async def list_presets(self, user_id: uuid.UUID) -> list[ScreenerPreset]:
        """List all saved screener presets for a user.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            List of ScreenerPreset records sorted by created_at descending.
        """
        stmt = (
            select(ScreenerPreset)
            .where(ScreenerPreset.user_id == user_id)
            .order_by(ScreenerPreset.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_preset(
        self, user_id: uuid.UUID, data: ScreenerPresetCreate
    ) -> ScreenerPreset:
        """Save a new screener preset.

        Args:
            user_id: The authenticated user's ID.
            data: Validated preset data (name + filter criteria).

        Returns:
            The newly created ScreenerPreset record.
        """
        preset = ScreenerPreset(
            id=uuid.uuid4(),
            user_id=user_id,
            name=data.name,
            filter_criteria=data.filter_criteria.model_dump(mode="json"),
            created_at=datetime.utcnow(),
        )
        self.db.add(preset)
        await self.db.flush()
        await self.db.refresh(preset)
        return preset

    async def delete_preset(
        self, user_id: uuid.UUID, preset_id: uuid.UUID
    ) -> None:
        """Delete a screener preset.

        Args:
            user_id: The authenticated user's ID.
            preset_id: The preset ID to delete.

        Raises:
            HTTPException(404): If the preset does not exist or does not belong to the user.
        """
        preset = await self._get_preset_or_404(user_id, preset_id)
        await self.db.delete(preset)
        await self.db.flush()

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    def _build_equity_query(self, filters: ScreenerFilterCreate):
        """Build a yfinance EquityQuery from filter criteria.

        Returns None if no filters are specified.
        """
        from yfinance import EquityQuery

        conditions = []

        # P/E ratio range
        if filters.pe_min is not None and filters.pe_max is not None:
            conditions.append(
                EquityQuery("btwn", ["peratio.lasttwelvemonths", float(filters.pe_min), float(filters.pe_max)])
            )
        elif filters.pe_min is not None:
            conditions.append(
                EquityQuery("gte", ["peratio.lasttwelvemonths", float(filters.pe_min)])
            )
        elif filters.pe_max is not None:
            conditions.append(
                EquityQuery("lte", ["peratio.lasttwelvemonths", float(filters.pe_max)])
            )

        # Dividend yield range
        if filters.dividend_yield_min is not None and filters.dividend_yield_max is not None:
            conditions.append(
                EquityQuery("btwn", ["forward_dividend_yield", float(filters.dividend_yield_min), float(filters.dividend_yield_max)])
            )
        elif filters.dividend_yield_min is not None:
            conditions.append(
                EquityQuery("gte", ["forward_dividend_yield", float(filters.dividend_yield_min)])
            )
        elif filters.dividend_yield_max is not None:
            conditions.append(
                EquityQuery("lte", ["forward_dividend_yield", float(filters.dividend_yield_max)])
            )

        # Market cap range
        if filters.market_cap_min is not None and filters.market_cap_max is not None:
            conditions.append(
                EquityQuery("btwn", ["intradaymarketcap", filters.market_cap_min, filters.market_cap_max])
            )
        elif filters.market_cap_min is not None:
            conditions.append(
                EquityQuery("gte", ["intradaymarketcap", filters.market_cap_min])
            )
        elif filters.market_cap_max is not None:
            conditions.append(
                EquityQuery("lte", ["intradaymarketcap", filters.market_cap_max])
            )

        # Sector (eq field)
        if filters.sector is not None:
            conditions.append(
                EquityQuery("eq", ["sector", filters.sector])
            )

        # Industry (eq field)
        if filters.industry is not None:
            conditions.append(
                EquityQuery("eq", ["industry", filters.industry])
            )

        # Beta range
        if filters.beta_min is not None and filters.beta_max is not None:
            conditions.append(
                EquityQuery("btwn", ["beta", float(filters.beta_min), float(filters.beta_max)])
            )
        elif filters.beta_min is not None:
            conditions.append(
                EquityQuery("gte", ["beta", float(filters.beta_min)])
            )
        elif filters.beta_max is not None:
            conditions.append(
                EquityQuery("lte", ["beta", float(filters.beta_max)])
            )

        # Price to book range
        if filters.price_to_book_min is not None and filters.price_to_book_max is not None:
            conditions.append(
                EquityQuery("btwn", ["pricebookratio.quarterly", float(filters.price_to_book_min), float(filters.price_to_book_max)])
            )
        elif filters.price_to_book_min is not None:
            conditions.append(
                EquityQuery("gte", ["pricebookratio.quarterly", float(filters.price_to_book_min)])
            )
        elif filters.price_to_book_max is not None:
            conditions.append(
                EquityQuery("lte", ["pricebookratio.quarterly", float(filters.price_to_book_max)])
            )

        # PEG Ratio range
        if filters.peg_ratio_min is not None and filters.peg_ratio_max is not None:
            conditions.append(
                EquityQuery("btwn", ["pegratio_5y", float(filters.peg_ratio_min), float(filters.peg_ratio_max)])
            )
        elif filters.peg_ratio_min is not None:
            conditions.append(
                EquityQuery("gte", ["pegratio_5y", float(filters.peg_ratio_min)])
            )
        elif filters.peg_ratio_max is not None:
            conditions.append(
                EquityQuery("lte", ["pegratio_5y", float(filters.peg_ratio_max)])
            )

        # Price to Sales, Revenue Growth, Short % — not supported by yfinance screener query
        # These filters are applied as post-filters on results instead

        if not conditions:
            return None

        # Always filter to only tradeable stocks on major US exchanges
        # This excludes OTC, pink sheets, preferred shares, etc.
        # Use OR of eq conditions since yfinance doesn't support "is_in"
        from yfinance import EquityQuery as EQ
        exchange_conditions = EquityQuery("or", [
            EQ("eq", ["exchange", "NMS"]),
            EQ("eq", ["exchange", "NYQ"]),
            EQ("eq", ["exchange", "NGM"]),
            EQ("eq", ["exchange", "NCM"]),
            EQ("eq", ["exchange", "ASE"]),
            EQ("eq", ["exchange", "PCX"]),
        ])
        conditions.append(exchange_conditions)

        return EquityQuery("and", conditions)

    async def _execute_screen(self, query) -> dict:
        """Execute the yfinance screen query.

        Args:
            query: An EquityQuery instance.

        Returns:
            The raw response dict from yfinance.screen().
        """
        import asyncio

        import yfinance as yf

        # yfinance.screen() is synchronous, run in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: yf.screen(query, size=MAX_SCREENER_RESULTS, sortField="intradaymarketcap", sortAsc=False),
        )
        return response

    def _parse_screen_results(self, response: dict) -> ScreenerSearchResponse:
        """Parse the yfinance screener response into ScreenerSearchResponse.

        Args:
            response: Raw response from yfinance.screen().

        Returns:
            ScreenerSearchResponse with parsed results.
            Only includes tradeable common stocks on major exchanges.
        """
        # Major US exchanges (yfinance exchange codes)
        TRADEABLE_EXCHANGES = {"NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "NAS", "NYSE", "NASDAQ", "AMEX"}

        results: list[ScreenerResultEntry] = []
        quotes = response.get("quotes", [])
        total = response.get("total", len(quotes))

        for quote in quotes[:MAX_SCREENER_RESULTS]:
            symbol = quote.get("symbol", "")
            if not symbol:
                continue

            # Skip non-equity types (preferred shares, warrants, etc.)
            quote_type = quote.get("quoteType", "EQUITY")
            if quote_type != "EQUITY":
                continue

            # Skip OTC/pink sheet stocks
            exchange = quote.get("exchange", "")
            if exchange and exchange not in TRADEABLE_EXCHANGES:
                continue

            # Skip symbols with special characters (preferred shares like JPM-PC)
            if "-" in symbol or "." in symbol:
                # Allow BRK-A, BRK-B style but skip preferred (usually ends in -P*)
                parts = symbol.split("-")
                if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
                    pass  # Allow BRK-A, BRK-B
                elif "-P" in symbol or ".P" in symbol:
                    continue  # Skip preferred shares

            entry = ScreenerResultEntry(
                stock_symbol=symbol,
                company_name=quote.get("longName") or quote.get("shortName"),
                sector=quote.get("sector"),
                industry=quote.get("industry"),
                current_price=self._safe_decimal(quote.get("regularMarketPrice")),
                pe_trailing=self._safe_decimal(quote.get("trailingPE")),
                pe_forward=self._safe_decimal(quote.get("forwardPE")),
                peg_ratio=self._safe_decimal(quote.get("pegRatio")),
                dividend_yield=self._safe_decimal(quote.get("dividendYield")),
                market_cap=self._safe_int(quote.get("marketCap")),
                beta=self._safe_decimal(quote.get("beta")),
                price_to_book=self._safe_decimal(quote.get("priceToBook")),
                price_to_sales=self._safe_decimal(quote.get("priceToSalesTrailing12Months")),
                revenue_growth=self._safe_decimal(quote.get("revenueGrowth")),
                short_percent_of_float=self._safe_decimal(quote.get("shortPercentOfFloat")),
            )
            results.append(entry)

        return ScreenerSearchResponse(
            results=results,
            total_matches=min(len(results), MAX_SCREENER_RESULTS),
        )

    def _apply_post_filters(
        self, results: ScreenerSearchResponse, filters: ScreenerFilterCreate
    ) -> ScreenerSearchResponse:
        """Apply post-filters for fields not supported by yfinance screener query."""
        filtered = results.results

        if filters.price_to_sales_min is not None:
            filtered = [r for r in filtered if r.price_to_sales is not None and r.price_to_sales >= filters.price_to_sales_min]
        if filters.price_to_sales_max is not None:
            filtered = [r for r in filtered if r.price_to_sales is not None and r.price_to_sales <= filters.price_to_sales_max]

        if filters.revenue_growth_min is not None:
            min_val = filters.revenue_growth_min / Decimal("100")  # Convert from % to ratio
            filtered = [r for r in filtered if r.revenue_growth is not None and r.revenue_growth >= min_val]
        if filters.revenue_growth_max is not None:
            max_val = filters.revenue_growth_max / Decimal("100")
            filtered = [r for r in filtered if r.revenue_growth is not None and r.revenue_growth <= max_val]

        if filters.short_percent_min is not None:
            min_val = filters.short_percent_min / Decimal("100")
            filtered = [r for r in filtered if r.short_percent_of_float is not None and r.short_percent_of_float >= min_val]
        if filters.short_percent_max is not None:
            max_val = filters.short_percent_max / Decimal("100")
            filtered = [r for r in filtered if r.short_percent_of_float is not None and r.short_percent_of_float <= max_val]

        return ScreenerSearchResponse(results=filtered, total_matches=len(filtered))

    async def _get_preset_or_404(
        self, user_id: uuid.UUID, preset_id: uuid.UUID
    ) -> ScreenerPreset:
        """Fetch a preset by ID, ensuring it belongs to the given user.

        Raises:
            HTTPException(404): If the preset is not found.
        """
        stmt = select(ScreenerPreset).where(
            ScreenerPreset.id == preset_id,
            ScreenerPreset.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        preset = result.scalar_one_or_none()
        if preset is None:
            raise HTTPException(
                status_code=404,
                detail="Screener preset not found",
            )
        return preset

    @staticmethod
    def _safe_decimal(value) -> Optional[Decimal]:
        """Convert a value to Decimal safely."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _safe_int(value) -> Optional[int]:
        """Convert a value to int safely."""
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None
