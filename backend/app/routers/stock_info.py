"""Stock Info API routes — detailed financial data for individual stocks."""

import asyncio
import logging
from decimal import Decimal
from typing import Optional

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stocks", tags=["stock-info"])


@router.get("/{symbol}/info")
async def get_stock_info(
    symbol: str,
    _user_id=Depends(get_current_user_id),
):
    """Get comprehensive stock information including financials and statistics."""
    symbol = symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: _fetch_stock_data(symbol))
        if not data:
            raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to fetch stock info for %s: %s", symbol, str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}")


def _fetch_stock_data(symbol: str) -> Optional[dict]:
    """Fetch stock data from yfinance synchronously."""
    ticker = yf.Ticker(symbol)
    info = ticker.info

    if not info or info.get("regularMarketPrice") is None:
        return None

    # === Company Profile ===
    profile = {
        "symbol": symbol,
        "company_name": info.get("longName") or info.get("shortName", ""),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "website": info.get("website"),
        "description": info.get("longBusinessSummary", ""),
        "country": info.get("country"),
        "employees": info.get("fullTimeEmployees"),
        "exchange": info.get("exchange"),
        "currency": info.get("currency", "USD"),
    }

    # === Price Info ===
    price_info = {
        "current_price": _safe_float(info.get("regularMarketPrice")),
        "previous_close": _safe_float(info.get("previousClose")),
        "open": _safe_float(info.get("open")),
        "day_high": _safe_float(info.get("dayHigh")),
        "day_low": _safe_float(info.get("dayLow")),
        "volume": info.get("volume"),
        "average_volume": info.get("averageVolume"),
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
        "fifty_day_average": _safe_float(info.get("fiftyDayAverage")),
        "two_hundred_day_average": _safe_float(info.get("twoHundredDayAverage")),
        "total_revenue": info.get("totalRevenue"),
        "net_income": info.get("netIncomeToCommon"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "beta": _safe_float(info.get("beta")),
    }

    # === Valuation Ratios ===
    valuation = {
        "pe_trailing": _safe_float(info.get("trailingPE")),
        "pe_forward": _safe_float(info.get("forwardPE")),
        "peg_ratio": _safe_float(info.get("pegRatio")),
        "price_to_book": _safe_float(info.get("priceToBook")),
        "price_to_sales": _safe_float(info.get("priceToSalesTrailing12Months")),
        "enterprise_value": info.get("enterpriseValue"),
        "ev_to_revenue": _safe_float(info.get("enterpriseToRevenue")),
        "ev_to_ebitda": _safe_float(info.get("enterpriseToEbitda")),
        "trailing_eps": _safe_float(info.get("trailingEps")),
        "forward_eps": _safe_float(info.get("forwardEps")),
        "book_value": _safe_float(info.get("bookValue")),
    }

    # === Dividend Info ===
    dividends = {
        "dividend_rate": _safe_float(info.get("dividendRate")),
        "dividend_yield": _safe_float(info.get("dividendYield")),
        "payout_ratio": _safe_float(info.get("payoutRatio")),
        "ex_dividend_date": info.get("exDividendDate"),
    }

    # === Short Selling Info ===
    short_info = {
        "short_ratio": _safe_float(info.get("shortRatio")),
        "short_percent_of_float": _safe_float(info.get("shortPercentOfFloat")),
        "shares_short": info.get("sharesShort"),
        "shares_short_prior_month": info.get("sharesShortPriorMonth"),
        "date_short_interest": info.get("dateShortInterest"),
    }

    # === Profitability ===
    profitability = {
        "profit_margins": _safe_float(info.get("profitMargins")),
        "operating_margins": _safe_float(info.get("operatingMargins")),
        "gross_margins": _safe_float(info.get("grossMargins")),
        "return_on_equity": _safe_float(info.get("returnOnEquity")),
        "return_on_assets": _safe_float(info.get("returnOnAssets")),
        "revenue_growth": _safe_float(info.get("revenueGrowth")),
        "earnings_growth": _safe_float(info.get("earningsGrowth")),
    }

    # === Financial Statements (last 4 periods) ===
    financials = _fetch_financials(ticker)

    # === Analyst Recommendations ===
    analysts = _fetch_analyst_info(ticker, info)

    # === Dividend History ===
    dividend_history = _fetch_dividend_history(ticker)

    # === Insider & Institutional Data ===
    insider_data = _fetch_insider_data(ticker)

    # === Earnings Data ===
    earnings_data = _fetch_earnings_data(ticker)

    return {
        "profile": profile,
        "price": price_info,
        "valuation": valuation,
        "dividends": dividends,
        "short_info": short_info,
        "profitability": profitability,
        "financials": financials,
        "analysts": analysts,
        "dividend_history": dividend_history,
        "insider": insider_data,
        "earnings": earnings_data,
    }


def _fetch_analyst_info(ticker, info: dict) -> dict:
    """Fetch analyst recommendations and price targets."""
    result = {
        "recommendation": info.get("recommendationKey", "N/A"),
        "target_mean_price": _safe_float(info.get("targetMeanPrice")),
        "target_high_price": _safe_float(info.get("targetHighPrice")),
        "target_low_price": _safe_float(info.get("targetLowPrice")),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "recommendations": [],
        "upgrades_downgrades": [],
    }

    try:
        # Try upgrades_downgrades first (newer yfinance)
        upgrades = getattr(ticker, "upgrades_downgrades", None)
        if upgrades is not None and not upgrades.empty:
            # Filter to last 2 years only
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=730)
            try:
                recent = upgrades[upgrades.index >= cutoff].tail(15)
            except Exception:
                recent = upgrades.tail(15)
            for idx, row in recent.iterrows():
                result["upgrades_downgrades"].append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "firm": str(row.get("Firm", row.get("firm", ""))),
                    "to_grade": str(row.get("ToGrade", row.get("To Grade", row.get("toGrade", "")))),
                    "from_grade": str(row.get("FromGrade", row.get("From Grade", row.get("fromGrade", "")))),
                    "action": str(row.get("Action", row.get("action", ""))),
                })
    except Exception:
        pass

    try:
        # Also try recommendations (older yfinance or different structure)
        recs = ticker.recommendations
        if recs is not None and not recs.empty:
            # Filter to last 2 years
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=730)
            try:
                recent = recs[recs.index >= cutoff].tail(15)
            except Exception:
                recent = recs.tail(15)
            cols = [c.lower() for c in recent.columns.tolist()]
            for idx, row in recent.iterrows():
                entry = {"date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)}
                # Handle various column name formats
                for col in recent.columns:
                    col_lower = col.lower().replace(" ", "_")
                    if "firm" in col_lower:
                        entry["firm"] = str(row[col])
                    elif "to" in col_lower and "grade" in col_lower:
                        entry["to_grade"] = str(row[col])
                    elif "from" in col_lower and "grade" in col_lower:
                        entry["from_grade"] = str(row[col])
                    elif "action" in col_lower:
                        entry["action"] = str(row[col])
                if entry.get("firm"):
                    result["recommendations"].append(entry)
    except Exception:
        pass

    return result


def _fetch_insider_data(ticker) -> dict:
    """Fetch insider trading and institutional holder data."""
    result = {
        "insider_transactions": [],
        "institutional_holders": [],
        "major_holders": [],
    }

    try:
        # Insider transactions - try multiple yfinance attributes
        insider_tx = None
        for attr_name in ["insider_transactions", "get_insider_transactions"]:
            insider_tx = getattr(ticker, attr_name, None)
            if callable(insider_tx):
                insider_tx = insider_tx()
            if insider_tx is not None and not getattr(insider_tx, 'empty', True):
                break

        if insider_tx is not None and not insider_tx.empty:
            # Sort by date descending and take most recent 15
            try:
                # Try to sort - column might be 'Start Date', 'startDate', 'Date', etc.
                date_col = None
                for possible_col in ['Start Date', 'startDate', 'Date', 'date']:
                    if possible_col in insider_tx.columns:
                        date_col = possible_col
                        break
                if date_col:
                    insider_tx = insider_tx.sort_values(date_col, ascending=False).head(15)
                else:
                    insider_tx = insider_tx.tail(15)
            except Exception:
                insider_tx = insider_tx.tail(15)

            # Log available columns for debugging
            cols = insider_tx.columns.tolist()
            logger.info("Insider transaction columns: %s", cols)

            for _, row in insider_tx.iterrows():
                # Dynamic column detection
                tx_date = ""
                for c in ['Start Date', 'startDate', 'Date', 'date']:
                    if c in row.index and row[c] is not None:
                        tx_date = str(row[c])[:10]
                        break

                insider_name = ""
                for c in ['Insider Trading', 'Insider', 'insider', 'Name', 'name', 'Insider Name']:
                    if c in row.index and row[c] is not None:
                        insider_name = str(row[c])
                        break

                position = ""
                for c in ['Position', 'position', 'Title', 'title', 'Relationship']:
                    if c in row.index and row[c] is not None:
                        position = str(row[c])
                        break

                transaction_type = ""
                for c in ['Transaction', 'transaction', 'Text', 'text', 'Type', 'type', 'Transaction Type']:
                    if c in row.index and row[c] is not None:
                        transaction_type = str(row[c])
                        break

                shares = None
                for c in ['Shares', 'shares', 'Share', 'Number of Shares', 'Shares Traded']:
                    if c in row.index and row[c] is not None:
                        shares = _safe_float(row[c])
                        break

                value = None
                for c in ['Value', 'value', 'Cost', 'Total Value']:
                    if c in row.index and row[c] is not None:
                        value = _safe_float(row[c])
                        break

                result["insider_transactions"].append({
                    "date": tx_date,
                    "insider": insider_name,
                    "position": position,
                    "transaction": transaction_type,
                    "shares": shares,
                    "value": value,
                })
    except Exception as e:
        logger.warning("Failed to fetch insider transactions: %s", str(e))

    try:
        # Institutional holders
        inst = getattr(ticker, "institutional_holders", None)
        if inst is not None and not inst.empty:
            for _, row in inst.head(10).iterrows():
                result["institutional_holders"].append({
                    "holder": str(row.get("Holder", row.get("holder", ""))),
                    "shares": _safe_float(row.get("Shares", row.get("shares"))),
                    "date_reported": str(row.get("Date Reported", row.get("dateReported", ""))),
                    "pct_out": _safe_float(row.get("% Out", row.get("pctHeld"))),
                    "value": _safe_float(row.get("Value", row.get("value"))),
                })
    except Exception:
        pass

    try:
        # Major holders percentages
        major = getattr(ticker, "major_holders", None)
        if major is not None and not major.empty:
            for _, row in major.iterrows():
                val = row.iloc[0] if len(row) > 0 else ""
                label = row.iloc[1] if len(row) > 1 else ""
                result["major_holders"].append({
                    "value": str(val),
                    "label": str(label),
                })
    except Exception:
        pass

    return result


def _fetch_earnings_data(ticker) -> dict:
    """Fetch earnings history and upcoming earnings."""
    result = {
        "earnings_dates": [],
        "earnings_history": [],
    }

    try:
        earnings = getattr(ticker, "earnings_dates", None)
        if earnings is not None and not earnings.empty:
            for idx, row in earnings.head(8).iterrows():
                result["earnings_dates"].append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "eps_estimate": _safe_float(row.get("EPS Estimate")),
                    "reported_eps": _safe_float(row.get("Reported EPS")),
                    "surprise_pct": _safe_float(row.get("Surprise(%)")),
                })
    except Exception:
        pass

    try:
        earnings_hist = getattr(ticker, "earnings_history", None)
        if earnings_hist is not None and not earnings_hist.empty:
            for _, row in earnings_hist.iterrows():
                result["earnings_history"].append({
                    "quarter": str(row.get("Quarter", "")),
                    "eps_estimate": _safe_float(row.get("epsEstimate")),
                    "eps_actual": _safe_float(row.get("epsActual")),
                    "eps_difference": _safe_float(row.get("epsDifference")),
                    "surprise_pct": _safe_float(row.get("surprisePercent")),
                })
    except Exception:
        pass

    return result


def _fetch_dividend_history(ticker) -> list:
    """Fetch historical dividend payments."""
    result = []
    try:
        divs = ticker.dividends
        if divs is not None and not divs.empty:
            # Last 20 dividends
            recent = divs.tail(20)
            for idx, value in recent.items():
                result.append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "amount": _safe_float(value),
                })
    except Exception:
        pass
    return result


def _fetch_financials(ticker) -> dict:
    """Fetch income statement, balance sheet, and cash flow (annual + quarterly)."""
    result = {
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": [],
        "quarterly_income": [],
        "quarterly_balance": [],
        "quarterly_cashflow": [],
    }

    def _parse_df(df, max_periods=4):
        """Parse a financial DataFrame into list of period dicts."""
        entries = []
        if df is None or df.empty:
            return entries
        for col in df.columns[:max_periods]:
            period_data = {"period": col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)}
            for idx in df.index:
                val = df.loc[idx, col]
                period_data[str(idx)] = _safe_float(val)
            entries.append(period_data)
        return entries

    try:
        result["income_statement"] = _parse_df(ticker.financials, 4)
    except Exception:
        pass

    try:
        result["balance_sheet"] = _parse_df(ticker.balance_sheet, 4)
    except Exception:
        pass

    try:
        result["cash_flow"] = _parse_df(ticker.cashflow, 4)
    except Exception:
        pass

    try:
        result["quarterly_income"] = _parse_df(ticker.quarterly_financials, 16)
    except Exception:
        pass

    try:
        result["quarterly_balance"] = _parse_df(ticker.quarterly_balance_sheet, 16)
    except Exception:
        pass

    try:
        result["quarterly_cashflow"] = _parse_df(ticker.quarterly_cashflow, 16)
    except Exception:
        pass

    return result


@router.get("/{symbol}/history")
async def get_stock_history(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    _user_id=Depends(get_current_user_id),
):
    """Get historical price data for charting.

    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max
    interval: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo
    """
    symbol = symbol.upper().strip()

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: _fetch_history(symbol, period, interval)
        )
        return data
    except Exception as e:
        logger.warning("Failed to fetch history for %s: %s", symbol, str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch history for {symbol}")


def _fetch_history(symbol: str, period: str, interval: str) -> dict:
    """Fetch historical OHLCV data."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, interval=interval)

    if hist is None or hist.empty:
        return {"prices": [], "period": period, "interval": interval}

    prices = []
    for idx, row in hist.iterrows():
        prices.append({
            "date": idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx),
            "open": _safe_float(row.get("Open")),
            "high": _safe_float(row.get("High")),
            "low": _safe_float(row.get("Low")),
            "close": _safe_float(row.get("Close")),
            "volume": int(row.get("Volume", 0)) if row.get("Volume") else 0,
        })

    return {"prices": prices, "period": period, "interval": interval}


def _safe_float(value) -> Optional[float]:
    """Convert value to float safely."""
    if value is None:
        return None
    try:
        import numpy as np
        if isinstance(value, (float, int, Decimal)):
            f = float(value)
            if np.isnan(f) or np.isinf(f):
                return None
            return f
        return float(value)
    except (ValueError, TypeError):
        return None
