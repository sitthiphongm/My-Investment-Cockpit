"""Provider adapter layer — abstracts external data sources behind interfaces."""

from app.infrastructure.providers.base import (
    MarketDataAdapter,
    FXRateAdapter,
    EmailAdapter,
    AIInsightAdapter,
    ProviderStatus,
    QuoteData,
    CompanyProfile,
    FXRateResult,
)

__all__ = [
    "AIInsightAdapter",
    "CompanyProfile",
    "EmailAdapter",
    "FXRateAdapter",
    "FXRateResult",
    "MarketDataAdapter",
    "ProviderStatus",
    "QuoteData",
]
