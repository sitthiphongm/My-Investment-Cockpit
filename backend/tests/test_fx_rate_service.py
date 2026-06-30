"""Unit tests for FXRateService — FX rate caching and manual entry."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.fx_rate_entry import FXRateEntry
from app.models.user import User
from app.schemas.fx_rates import FXRateCreate
from app.services.fx_rate_service import FXRateService


@pytest.fixture
async def engine():
    """Create an async SQLite engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    @event.listens_for(eng.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Provide a test database session."""
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as sess:
        yield sess


@pytest.fixture
async def user_id(session):
    """Create a test user and return its ID."""
    uid = uuid.uuid4()
    user = User(
        id=uid,
        display_name="Test User",
        email="test@example.com",
        oauth_provider="google",
        oauth_provider_id="google_123",
        status="Approved",
        is_admin=False,
        registered_at=datetime.utcnow(),
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    await session.flush()
    return uid


@pytest.fixture
def service(session):
    """Create an FXRateService instance."""
    return FXRateService(session)


class TestCreateManualRate:
    """Tests for FXRateService.create_manual_rate."""

    async def test_create_manual_rate_persists_correctly(self, service, user_id):
        """Manual entry persists all fields correctly."""
        data = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )

        result = await service.create_manual_rate(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.base_currency == "THB"
        assert result.quote_currency == "USD"
        assert result.rate_date == date(2024, 6, 15)
        assert result.rate == Decimal("35.250000")
        assert result.provider_name == "manual"
        assert result.is_manual is True
        assert result.staleness == "Manual"
        assert result.fetch_timestamp is not None
        assert result.created_at is not None

    async def test_create_manual_rate_with_custom_provider(self, service, user_id):
        """Manual entry with custom provider name."""
        data = FXRateCreate(
            currency_pair="EUR/USD",
            date=date(2024, 1, 10),
            rate=Decimal("1.095000"),
            provider="bank_rate",
        )

        result = await service.create_manual_rate(user_id, data)

        assert result.provider_name == "bank_rate"
        assert result.is_manual is True

    async def test_create_manual_rate_upsert_updates_existing(self, service, user_id):
        """Creating a rate for existing pair+date updates instead of duplicating."""
        data1 = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )
        entry1 = await service.create_manual_rate(user_id, data1)
        entry1_id = entry1.id

        # Create again with different rate for same pair+date
        data2 = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.500000"),
        )
        entry2 = await service.create_manual_rate(user_id, data2)

        # Should update existing entry, same ID
        assert entry2.id == entry1_id
        assert entry2.rate == Decimal("35.500000")
        assert entry2.is_manual is True

    async def test_different_dates_create_separate_entries(self, service, user_id):
        """Different dates for same pair create separate entries."""
        data1 = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )
        data2 = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 16),
            rate=Decimal("35.300000"),
        )

        entry1 = await service.create_manual_rate(user_id, data1)
        entry2 = await service.create_manual_rate(user_id, data2)

        assert entry1.id != entry2.id
        assert entry1.rate_date == date(2024, 6, 15)
        assert entry2.rate_date == date(2024, 6, 16)


class TestGetRate:
    """Tests for FXRateService.get_rate."""

    async def test_get_rate_returns_cached_entry(self, service, user_id):
        """Get returns cached rate when available."""
        data = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )
        await service.create_manual_rate(user_id, data)

        result = await service.get_rate(user_id, "THB", "USD", date(2024, 6, 15))

        assert result is not None
        assert result.rate == Decimal("35.250000")
        assert result.base_currency == "THB"
        assert result.quote_currency == "USD"

    async def test_get_rate_returns_none_when_not_found(self, service, user_id):
        """Get returns None when no rate exists for the pair+date."""
        result = await service.get_rate(user_id, "THB", "USD", date(2024, 6, 15))

        assert result is None

    async def test_get_rate_case_insensitive_currency(self, service, user_id):
        """Get works with lowercase currency codes."""
        data = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )
        await service.create_manual_rate(user_id, data)

        result = await service.get_rate(user_id, "thb", "usd", date(2024, 6, 15))

        assert result is not None
        assert result.rate == Decimal("35.250000")

    async def test_get_rate_per_user_isolation(self, service, session, user_id):
        """Rates are isolated per user."""
        # Create rate for user A
        data = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )
        await service.create_manual_rate(user_id, data)

        # Create another user
        other_user_id = uuid.uuid4()
        other_user = User(
            id=other_user_id,
            display_name="Other User",
            email="other@example.com",
            oauth_provider="facebook",
            oauth_provider_id="fb_456",
            status="Approved",
            is_admin=False,
            registered_at=datetime.utcnow(),
            last_login_at=datetime.utcnow(),
        )
        session.add(other_user)
        await session.flush()

        # Other user should not see user A's rate
        result = await service.get_rate(other_user_id, "THB", "USD", date(2024, 6, 15))
        assert result is None


class TestStalenessDetection:
    """Tests for staleness marking logic."""

    async def test_manual_entries_never_stale(self, service, user_id):
        """Manual entries always have staleness 'Manual'."""
        data = FXRateCreate(
            currency_pair="THB/USD",
            date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
        )
        entry = await service.create_manual_rate(user_id, data)

        assert entry.staleness == "Manual"

        # Retrieve it again — should still be Manual
        result = await service.get_rate(user_id, "THB", "USD", date(2024, 6, 15))
        assert result.staleness == "Manual"

    async def test_provider_rate_fresh_within_threshold(self, service, user_id):
        """Provider rate is Fresh when fetch_timestamp is within threshold."""
        entry = await service.cache_provider_rate(
            user_id=user_id,
            base_currency="THB",
            quote_currency="USD",
            rate_date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
            provider_name="unirate",
            source_timestamp=datetime.utcnow(),
        )

        assert entry.staleness == "Fresh"

        # Retrieve — should still be fresh (within threshold)
        result = await service.get_rate(user_id, "THB", "USD", date(2024, 6, 15))
        assert result.staleness == "Fresh"

    async def test_provider_rate_stale_beyond_threshold(self, service, user_id, session):
        """Provider rate is marked Stale when fetch_timestamp exceeds threshold."""
        # Create a rate with old fetch_timestamp (beyond default 24h threshold)
        old_time = datetime.utcnow() - timedelta(hours=25)
        entry = FXRateEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            base_currency="THB",
            quote_currency="USD",
            rate_date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
            provider_name="unirate",
            source_timestamp=old_time,
            fetch_timestamp=old_time,
            is_manual=False,
            staleness="Fresh",  # Initially Fresh in DB
            created_at=old_time,
        )
        session.add(entry)
        await session.flush()

        # Retrieve — should be updated to Stale
        result = await service.get_rate(user_id, "THB", "USD", date(2024, 6, 15))
        assert result.staleness == "Stale"

    async def test_provider_rate_stale_when_no_fetch_timestamp(self, service, user_id, session):
        """Provider rate without fetch_timestamp is marked Stale."""
        entry = FXRateEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            base_currency="EUR",
            quote_currency="USD",
            rate_date=date(2024, 6, 15),
            rate=Decimal("1.095000"),
            provider_name="alpha_vantage",
            source_timestamp=None,
            fetch_timestamp=None,
            is_manual=False,
            staleness="Fresh",
            created_at=datetime.utcnow(),
        )
        session.add(entry)
        await session.flush()

        result = await service.get_rate(user_id, "EUR", "USD", date(2024, 6, 15))
        assert result.staleness == "Stale"


class TestCacheProviderRate:
    """Tests for FXRateService.cache_provider_rate."""

    async def test_cache_provider_rate_creates_fresh_entry(self, service, user_id):
        """Caching a provider rate creates a Fresh, non-manual entry."""
        result = await service.cache_provider_rate(
            user_id=user_id,
            base_currency="THB",
            quote_currency="USD",
            rate_date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
            provider_name="unirate",
            source_timestamp=datetime(2024, 6, 15, 12, 0, 0),
        )

        assert result.is_manual is False
        assert result.staleness == "Fresh"
        assert result.provider_name == "unirate"
        assert result.source_timestamp == datetime(2024, 6, 15, 12, 0, 0)
        assert result.fetch_timestamp is not None

    async def test_cache_provider_rate_updates_existing(self, service, user_id):
        """Caching overwrites existing entry for same pair+date."""
        await service.cache_provider_rate(
            user_id=user_id,
            base_currency="THB",
            quote_currency="USD",
            rate_date=date(2024, 6, 15),
            rate=Decimal("35.250000"),
            provider_name="unirate",
        )

        # Cache again with different rate
        result = await service.cache_provider_rate(
            user_id=user_id,
            base_currency="THB",
            quote_currency="USD",
            rate_date=date(2024, 6, 15),
            rate=Decimal("35.300000"),
            provider_name="alpha_vantage",
        )

        assert result.rate == Decimal("35.300000")
        assert result.provider_name == "alpha_vantage"
        assert result.staleness == "Fresh"
