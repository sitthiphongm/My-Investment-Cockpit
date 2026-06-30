"""Unit tests for ScreenerService."""

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.screener_preset import ScreenerPreset
from app.models.user import User
from app.schemas.screener import (
    ScreenerFilterCreate,
    ScreenerPresetCreate,
    ScreenerSearchResponse,
)
from app.services.screener_service import ScreenerService


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
async def other_user_id(session):
    """Create a second test user and return its ID."""
    uid = uuid.uuid4()
    user = User(
        id=uid,
        display_name="Other User",
        email="other@example.com",
        oauth_provider="facebook",
        oauth_provider_id="fb_456",
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
    """Create a ScreenerService instance."""
    return ScreenerService(session)


class TestScreenerSearch:
    """Tests for ScreenerService.search."""

    async def test_search_with_no_filters_returns_empty(self, service):
        """Search with no filter criteria returns empty results."""
        filters = ScreenerFilterCreate()
        result = await service.search(filters)

        assert isinstance(result, ScreenerSearchResponse)
        assert result.results == []
        assert result.total_matches == 0

    async def test_build_equity_query_pe_range(self, service):
        """Build query with PE min and max."""
        filters = ScreenerFilterCreate(pe_min=Decimal("5"), pe_max=Decimal("20"))
        query = service._build_equity_query(filters)

        assert query is not None
        # The query should be an AND with a btwn condition + region
        assert query.operator == "AND"

    async def test_build_equity_query_pe_min_only(self, service):
        """Build query with PE min only."""
        filters = ScreenerFilterCreate(pe_min=Decimal("10"))
        query = service._build_equity_query(filters)

        assert query is not None
        assert query.operator == "AND"

    async def test_build_equity_query_pe_max_only(self, service):
        """Build query with PE max only."""
        filters = ScreenerFilterCreate(pe_max=Decimal("30"))
        query = service._build_equity_query(filters)

        assert query is not None
        assert query.operator == "AND"

    async def test_build_equity_query_dividend_yield_range(self, service):
        """Build query with dividend yield range."""
        filters = ScreenerFilterCreate(
            dividend_yield_min=Decimal("0.02"),
            dividend_yield_max=Decimal("0.05"),
        )
        query = service._build_equity_query(filters)

        assert query is not None

    async def test_build_equity_query_market_cap_range(self, service):
        """Build query with market cap range."""
        filters = ScreenerFilterCreate(
            market_cap_min=1000000000,
            market_cap_max=50000000000,
        )
        query = service._build_equity_query(filters)

        assert query is not None

    async def test_build_equity_query_sector(self, service):
        """Build query with sector filter."""
        filters = ScreenerFilterCreate(sector="Technology")
        query = service._build_equity_query(filters)

        assert query is not None

    async def test_build_equity_query_industry(self, service):
        """Build query with industry filter."""
        filters = ScreenerFilterCreate(industry="Steel")
        query = service._build_equity_query(filters)

        assert query is not None

    async def test_build_equity_query_multiple_filters(self, service):
        """Build query with multiple filter criteria (AND logic)."""
        filters = ScreenerFilterCreate(
            pe_min=Decimal("5"),
            pe_max=Decimal("25"),
            dividend_yield_min=Decimal("0.01"),
            sector="Technology",
            market_cap_min=10000000000,
        )
        query = service._build_equity_query(filters)

        assert query is not None
        assert query.operator == "AND"
        # Should have multiple conditions (4 filters)
        assert len(query.operands) >= 4

    async def test_build_equity_query_beta_range(self, service):
        """Build query with beta range."""
        filters = ScreenerFilterCreate(
            beta_min=Decimal("0.5"),
            beta_max=Decimal("1.5"),
        )
        query = service._build_equity_query(filters)

        assert query is not None

    async def test_build_equity_query_price_to_book_range(self, service):
        """Build query with price-to-book range."""
        filters = ScreenerFilterCreate(
            price_to_book_min=Decimal("0.5"),
            price_to_book_max=Decimal("3.0"),
        )
        query = service._build_equity_query(filters)

        assert query is not None

    async def test_parse_screen_results_limits_to_50(self, service):
        """Parse results caps at 50 entries."""
        # Create fake response with 60 quotes
        quotes = [
            {
                "symbol": f"SYM{i}",
                "longName": f"Company {i}",
                "sector": "Technology",
                "industry": "Software",
                "regularMarketPrice": 100.0 + i,
                "trailingPE": 15.0 + i * 0.1,
                "forwardPE": 14.0,
                "dividendYield": 0.02,
                "marketCap": 1000000000 + i * 1000000,
                "beta": 1.1,
                "priceToBook": 2.5,
            }
            for i in range(60)
        ]
        response = {"quotes": quotes, "total": 60}

        result = service._parse_screen_results(response)

        assert len(result.results) == 50
        assert result.total_matches == 50

    async def test_parse_screen_results_handles_missing_fields(self, service):
        """Parse results handles quotes with missing fields gracefully."""
        response = {
            "quotes": [
                {
                    "symbol": "AAPL",
                    "longName": "Apple Inc.",
                    # Missing most fields
                }
            ],
            "total": 1,
        }

        result = service._parse_screen_results(response)

        assert len(result.results) == 1
        entry = result.results[0]
        assert entry.stock_symbol == "AAPL"
        assert entry.company_name == "Apple Inc."
        assert entry.sector is None
        assert entry.current_price is None
        assert entry.pe_trailing is None

    async def test_parse_screen_results_skips_empty_symbol(self, service):
        """Parse results skips quotes without a symbol."""
        response = {
            "quotes": [
                {"longName": "No Symbol Stock"},
                {"symbol": "AAPL", "longName": "Apple Inc."},
            ],
            "total": 2,
        }

        result = service._parse_screen_results(response)

        assert len(result.results) == 1
        assert result.results[0].stock_symbol == "AAPL"

    @patch("app.services.screener_service.ScreenerService._execute_screen")
    async def test_search_with_filters_calls_yfinance(self, mock_execute, service):
        """Search with filters calls the yfinance screen API."""
        mock_execute.return_value = {
            "quotes": [
                {
                    "symbol": "MSFT",
                    "longName": "Microsoft Corporation",
                    "sector": "Technology",
                    "regularMarketPrice": 400.0,
                    "trailingPE": 35.0,
                    "marketCap": 3000000000000,
                }
            ],
            "total": 1,
        }

        filters = ScreenerFilterCreate(pe_min=Decimal("10"), pe_max=Decimal("40"))
        result = await service.search(filters)

        assert len(result.results) == 1
        assert result.results[0].stock_symbol == "MSFT"
        assert result.results[0].company_name == "Microsoft Corporation"
        assert result.results[0].current_price == Decimal("400.0")
        mock_execute.assert_called_once()

    @patch("app.services.screener_service.ScreenerService._execute_screen")
    async def test_search_failure_raises_502(self, mock_execute, service):
        """Search raises 502 when yfinance call fails."""
        mock_execute.side_effect = Exception("Network error")

        filters = ScreenerFilterCreate(pe_min=Decimal("10"))

        with pytest.raises(HTTPException) as exc_info:
            await service.search(filters)

        assert exc_info.value.status_code == 502


class TestScreenerPresets:
    """Tests for ScreenerService preset CRUD operations."""

    async def test_create_preset(self, service, user_id):
        """Create a new preset with name and filter criteria."""
        data = ScreenerPresetCreate(
            name="Tech Value Stocks",
            filter_criteria=ScreenerFilterCreate(
                pe_min=Decimal("5"),
                pe_max=Decimal("20"),
                sector="Technology",
            ),
        )

        result = await service.create_preset(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.name == "Tech Value Stocks"
        assert result.filter_criteria is not None
        assert result.created_at is not None

    async def test_create_preset_stores_filter_criteria_as_json(self, service, user_id):
        """Filter criteria is stored as JSON dict."""
        data = ScreenerPresetCreate(
            name="High Dividend",
            filter_criteria=ScreenerFilterCreate(
                dividend_yield_min=Decimal("0.03"),
                market_cap_min=1000000000,
            ),
        )

        result = await service.create_preset(user_id, data)

        criteria = result.filter_criteria
        assert isinstance(criteria, dict)
        assert criteria.get("dividend_yield_min") is not None
        assert criteria.get("market_cap_min") == 1000000000

    async def test_list_presets_empty(self, service, user_id):
        """List returns empty when no presets exist."""
        presets = await service.list_presets(user_id)
        assert presets == []

    async def test_list_presets_returns_user_presets(self, service, user_id):
        """List returns all presets for the user."""
        for i in range(3):
            data = ScreenerPresetCreate(
                name=f"Preset {i}",
                filter_criteria=ScreenerFilterCreate(pe_min=Decimal(str(i + 5))),
            )
            await service.create_preset(user_id, data)

        presets = await service.list_presets(user_id)

        assert len(presets) == 3

    async def test_list_presets_sorted_by_created_at_desc(self, service, user_id):
        """Presets are returned sorted by creation date descending."""
        data1 = ScreenerPresetCreate(
            name="First",
            filter_criteria=ScreenerFilterCreate(pe_min=Decimal("5")),
        )
        data2 = ScreenerPresetCreate(
            name="Second",
            filter_criteria=ScreenerFilterCreate(pe_min=Decimal("10")),
        )
        data3 = ScreenerPresetCreate(
            name="Third",
            filter_criteria=ScreenerFilterCreate(pe_min=Decimal("15")),
        )

        await service.create_preset(user_id, data1)
        await service.create_preset(user_id, data2)
        await service.create_preset(user_id, data3)

        presets = await service.list_presets(user_id)

        assert presets[0].name == "Third"
        assert presets[1].name == "Second"
        assert presets[2].name == "First"

    async def test_list_presets_does_not_return_other_users_presets(
        self, service, user_id, other_user_id, session
    ):
        """List only returns presets for the requesting user."""
        # Create preset for user
        data = ScreenerPresetCreate(
            name="My Preset",
            filter_criteria=ScreenerFilterCreate(pe_min=Decimal("5")),
        )
        await service.create_preset(user_id, data)

        # Create preset for other user directly
        other_preset = ScreenerPreset(
            id=uuid.uuid4(),
            user_id=other_user_id,
            name="Their Preset",
            filter_criteria={"pe_min": "10"},
            created_at=datetime.utcnow(),
        )
        session.add(other_preset)
        await session.flush()

        presets = await service.list_presets(user_id)

        assert len(presets) == 1
        assert presets[0].name == "My Preset"

    async def test_delete_preset(self, service, user_id):
        """Delete removes the preset."""
        data = ScreenerPresetCreate(
            name="To Delete",
            filter_criteria=ScreenerFilterCreate(pe_min=Decimal("5")),
        )
        preset = await service.create_preset(user_id, data)

        await service.delete_preset(user_id, preset.id)

        presets = await service.list_presets(user_id)
        assert len(presets) == 0

    async def test_delete_nonexistent_raises_404(self, service, user_id):
        """Delete a non-existent preset raises 404."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_preset(user_id, fake_id)

        assert exc_info.value.status_code == 404

    async def test_delete_other_users_preset_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot delete another user's preset."""
        other_preset = ScreenerPreset(
            id=uuid.uuid4(),
            user_id=other_user_id,
            name="Their Preset",
            filter_criteria={"pe_min": "10"},
            created_at=datetime.utcnow(),
        )
        session.add(other_preset)
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_preset(user_id, other_preset.id)

        assert exc_info.value.status_code == 404


class TestScreenerPresetValidation:
    """Tests for ScreenerPresetCreate validation."""

    def test_preset_name_min_length(self):
        """Preset name must be at least 1 character."""
        with pytest.raises(Exception):
            ScreenerPresetCreate(
                name="",
                filter_criteria=ScreenerFilterCreate(),
            )

    def test_preset_name_max_length(self):
        """Preset name must be at most 100 characters."""
        with pytest.raises(Exception):
            ScreenerPresetCreate(
                name="x" * 101,
                filter_criteria=ScreenerFilterCreate(),
            )

    def test_preset_name_not_blank(self):
        """Preset name cannot be blank (whitespace only)."""
        with pytest.raises(Exception):
            ScreenerPresetCreate(
                name="   ",
                filter_criteria=ScreenerFilterCreate(),
            )

    def test_preset_name_trimmed(self):
        """Preset name is trimmed of leading/trailing whitespace."""
        preset = ScreenerPresetCreate(
            name="  My Preset  ",
            filter_criteria=ScreenerFilterCreate(),
        )
        assert preset.name == "My Preset"

    def test_preset_name_valid(self):
        """Valid preset name (1-100 chars) passes validation."""
        preset = ScreenerPresetCreate(
            name="Tech Stocks Low PE",
            filter_criteria=ScreenerFilterCreate(
                pe_min=Decimal("5"),
                pe_max=Decimal("15"),
            ),
        )
        assert preset.name == "Tech Stocks Low PE"
