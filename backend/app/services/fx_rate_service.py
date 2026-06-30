"""FX Rate Service - Business logic for FX rate caching and manual entry."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.fx_rate_entry import FXRateEntry
from app.schemas.fx_rates import FXRateCreate


class FXRateService:
    """Service for managing cached and manually entered FX rates.

    Supports:
    - Manual FX rate entry by users
    - Database caching of FX rates by currency pair and date
    - Staleness detection based on configurable threshold
    - Lookup of cached rates for auto-population in transfer forms
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._stale_threshold_hours = settings.fx_cache_ttl_hours

    async def get_rate(
        self,
        user_id: uuid.UUID,
        base_currency: str,
        quote_currency: str,
        rate_date,
    ) -> Optional[FXRateEntry]:
        """Get a cached FX rate for a currency pair and date.

        Looks up the rate in the database. If found, checks staleness based on
        the configured threshold and updates the staleness flag if needed.

        Args:
            user_id: The authenticated user's ID (per-user isolation).
            base_currency: Base currency code (e.g. 'THB').
            quote_currency: Quote currency code (e.g. 'USD').
            rate_date: The date for which the rate is needed.

        Returns:
            The FXRateEntry if found (with updated staleness), or None.
        """
        stmt = select(FXRateEntry).where(
            and_(
                FXRateEntry.user_id == user_id,
                FXRateEntry.base_currency == base_currency.upper(),
                FXRateEntry.quote_currency == quote_currency.upper(),
                FXRateEntry.rate_date == rate_date,
            )
        )
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()

        if entry is not None:
            # Update staleness based on threshold
            updated_staleness = self._compute_staleness(entry)
            if entry.staleness != updated_staleness:
                entry.staleness = updated_staleness
                await self.db.flush()
                await self.db.refresh(entry)

        return entry

    async def create_manual_rate(
        self,
        user_id: uuid.UUID,
        data: FXRateCreate,
    ) -> FXRateEntry:
        """Create or update a manual FX rate entry.

        If a rate already exists for the same user/pair/date, it is replaced
        (upsert behavior). Manual entries are marked with is_manual=True and
        staleness='Manual'.

        Args:
            user_id: The authenticated user's ID.
            data: Validated FX rate creation data.

        Returns:
            The created or updated FXRateEntry.
        """
        base_currency = data.currency_pair[:3]
        quote_currency = data.currency_pair[4:]

        # Check for existing entry (upsert)
        existing = await self.get_rate(user_id, base_currency, quote_currency, data.date)

        if existing is not None:
            # Update existing entry
            existing.rate = data.rate
            existing.provider_name = data.provider or "manual"
            existing.is_manual = True
            existing.staleness = "Manual"
            existing.fetch_timestamp = datetime.utcnow()
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new entry
        entry = FXRateEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            base_currency=base_currency,
            quote_currency=quote_currency,
            rate_date=data.date,
            rate=data.rate,
            provider_name=data.provider or "manual",
            source_timestamp=None,
            fetch_timestamp=datetime.utcnow(),
            is_manual=True,
            staleness="Manual",
            created_at=datetime.utcnow(),
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def cache_provider_rate(
        self,
        user_id: uuid.UUID,
        base_currency: str,
        quote_currency: str,
        rate_date,
        rate: Decimal,
        provider_name: str,
        source_timestamp: Optional[datetime] = None,
    ) -> FXRateEntry:
        """Cache an FX rate fetched from an external provider.

        Used by the market data service to store rates retrieved from
        external FX providers (UniRateAPI, Alpha Vantage, etc.).

        Args:
            user_id: The user's ID.
            base_currency: Base currency code.
            quote_currency: Quote currency code.
            rate_date: Date the rate applies to.
            rate: The exchange rate value.
            provider_name: Name of the provider.
            source_timestamp: When the provider generated the rate.

        Returns:
            The cached FXRateEntry.
        """
        existing = await self.get_rate(user_id, base_currency, quote_currency, rate_date)

        now = datetime.utcnow()

        if existing is not None:
            existing.rate = rate
            existing.provider_name = provider_name
            existing.source_timestamp = source_timestamp
            existing.fetch_timestamp = now
            existing.is_manual = False
            existing.staleness = "Fresh"
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        entry = FXRateEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper(),
            rate_date=rate_date,
            rate=rate,
            provider_name=provider_name,
            source_timestamp=source_timestamp,
            fetch_timestamp=now,
            is_manual=False,
            staleness="Fresh",
            created_at=now,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    def _compute_staleness(self, entry: FXRateEntry) -> str:
        """Compute staleness status for an FX rate entry.

        Rules:
        - Manual entries are always 'Manual' (never stale by time).
        - Provider entries are 'Fresh' if fetch_timestamp is within threshold.
        - Provider entries are 'Stale' if fetch_timestamp exceeds threshold.
        """
        if entry.is_manual:
            return "Manual"

        if entry.fetch_timestamp is None:
            return "Stale"

        # Make fetch_timestamp offset-naive for comparison
        fetch_ts = entry.fetch_timestamp
        if fetch_ts.tzinfo is not None:
            fetch_ts = fetch_ts.replace(tzinfo=None)

        threshold = datetime.utcnow() - timedelta(hours=self._stale_threshold_hours)
        if fetch_ts < threshold:
            return "Stale"

        return "Fresh"
