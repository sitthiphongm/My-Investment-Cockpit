"""Base provider adapter interfaces (Protocol classes)."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol, runtime_checkable


class CircuitState(str, Enum):
    CLOSED = "Closed"
    OPEN = "Open"
    HALF_OPEN = "HalfOpen"


@dataclass
class QuoteData:
    """Unified market quote data independent of provider."""

    symbol: str
    current_price: Decimal | None = None
    previous_close: Decimal | None = None
    day_high: Decimal | None = None
    day_low: Decimal | None = None
    volume: int | None = None
    average_volume: int | None = None
    fifty_two_week_low: Decimal | None = None
    fifty_two_week_high: Decimal | None = None
    market_cap: int | None = None
    pe_trailing: Decimal | None = None
    pe_forward: Decimal | None = None
    beta: Decimal | None = None
    dividend_yield: Decimal | None = None
    price_to_book: Decimal | None = None
    provider_name: str = ""
    source_timestamp: datetime | None = None
    last_fetched: datetime | None = None


@dataclass
class CompanyProfile:
    """Unified company profile data."""

    symbol: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    website: str | None = None
    market_cap: int | None = None
    provider_name: str = ""


@dataclass
class FXRateResult:
    """FX rate result from a provider."""

    base_currency: str
    quote_currency: str
    rate: Decimal
    rate_date: date
    provider_name: str = ""
    source_timestamp: datetime | None = None
    fetch_timestamp: datetime | None = None


@dataclass
class ProviderStatus:
    """Health/status of a provider adapter."""

    provider_name: str
    circuit_state: CircuitState = CircuitState.CLOSED
    success_count: int = 0
    failure_count: int = 0
    cache_hit_count: int = 0
    success_rate: float = 1.0
    last_error: str | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None


@dataclass
class PriceBar:
    """Historical price bar."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@runtime_checkable
class MarketDataAdapter(Protocol):
    """Provider-agnostic interface for market data."""

    async def get_quote(self, symbol: str) -> QuoteData | None: ...
    async def get_historical(self, symbol: str, start: date, end: date) -> list[PriceBar]: ...
    async def get_company_profile(self, symbol: str) -> CompanyProfile | None: ...
    async def get_batch_quotes(self, symbols: list[str]) -> dict[str, QuoteData]: ...
    def provider_name(self) -> str: ...


@runtime_checkable
class FXRateAdapter(Protocol):
    """Provider-agnostic interface for FX rates."""

    async def get_rate(self, base: str, quote: str, for_date: date) -> FXRateResult | None: ...
    async def get_latest_rate(self, base: str, quote: str) -> FXRateResult | None: ...
    def provider_name(self) -> str: ...


@runtime_checkable
class EmailAdapter(Protocol):
    """Pluggable email notification adapter."""

    async def send(self, to: str, subject: str, html_body: str) -> bool: ...
    def provider_name(self) -> str: ...


@runtime_checkable
class AIInsightAdapter(Protocol):
    """Pluggable AI insight adapter."""

    async def generate_weekly_memo(self, context: dict) -> str: ...
    async def generate_trade_review(self, context: dict) -> str: ...
    def provider_name(self) -> str: ...
