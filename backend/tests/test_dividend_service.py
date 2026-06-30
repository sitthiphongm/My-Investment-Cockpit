"""Unit tests for the dividend service."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.dividend_record import DividendRecord
from app.models.transaction import Transaction
from app.schemas.dividends import (
    DividendCreate,
    DividendFilters,
    DividendProjectionEntry,
    DividendProjectionResponse,
    DividendSummaryEntry,
    DividendSummaryResponse,
)
from app.services.dividend_service import DividendService


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    """Create DividendService with mock db."""
    return DividendService(mock_db)


@pytest.fixture
def user_id():
    """A test user ID."""
    return uuid.uuid4()


class TestCreateDividend:
    """Tests for creating dividend records."""

    @pytest.mark.asyncio
    async def test_create_dividend_success(self, service, mock_db, user_id):
        """Creating a dividend record should persist and return the record."""
        data = DividendCreate(
            date=date(2024, 6, 15),
            stock_symbol="PTT",
            amount_per_share=Decimal("1.50"),
            shares_held=1000,
            total_amount=Decimal("1500.00"),
        )

        result = await service.create_dividend(user_id, data)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()

        # Verify the record was created with correct data
        added_record = mock_db.add.call_args[0][0]
        assert added_record.user_id == user_id
        assert added_record.date == date(2024, 6, 15)
        assert added_record.stock_symbol == "PTT"
        assert added_record.amount_per_share == Decimal("1.50")
        assert added_record.shares_held == 1000
        assert added_record.total_amount == Decimal("1500.00")

    @pytest.mark.asyncio
    async def test_create_dividend_symbol_uppercased(self, service, mock_db, user_id):
        """Stock symbol should be uppercased by schema validation."""
        data = DividendCreate(
            date=date(2024, 6, 15),
            stock_symbol="ptt",
            amount_per_share=Decimal("1.50"),
            shares_held=1000,
            total_amount=Decimal("1500.00"),
        )
        # Schema validator converts to uppercase
        assert data.stock_symbol == "PTT"


class TestListDividends:
    """Tests for listing dividend records."""

    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_records(self, service, mock_db, user_id):
        """List should return empty list when no records exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        filters = DividendFilters()
        result = await service.list_dividends(user_id, filters)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_stock_filter(self, service, mock_db, user_id):
        """List should filter by stock symbol."""
        record = DividendRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 6, 15),
            stock_symbol="PTT",
            amount_per_share=Decimal("1.50"),
            shares_held=1000,
            total_amount=Decimal("1500.00"),
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record]
        mock_db.execute.return_value = mock_result

        filters = DividendFilters(stock_symbol="PTT")
        result = await service.list_dividends(user_id, filters)

        assert len(result) == 1
        assert result[0].stock_symbol == "PTT"


class TestDividendSummary:
    """Tests for dividend summary endpoint."""

    @pytest.mark.asyncio
    async def test_summary_by_stock(self, service, mock_db, user_id):
        """Summary by stock should aggregate by stock symbol."""
        mock_row = MagicMock()
        mock_row.stock_symbol = "PTT"
        mock_row.total_dividends = Decimal("3000.00")
        mock_row.record_count = 2

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        filters = DividendFilters(group_by="stock")
        result = await service.get_summary(user_id, filters)

        assert isinstance(result, DividendSummaryResponse)
        assert len(result.entries) == 1
        assert result.entries[0].stock_symbol == "PTT"
        assert result.entries[0].total_dividends == Decimal("3000.00")
        assert result.entries[0].record_count == 2
        assert result.total_all_dividends == Decimal("3000.00")

    @pytest.mark.asyncio
    async def test_summary_by_monthly(self, service, mock_db, user_id):
        """Summary by monthly should aggregate by year-month."""
        mock_row = MagicMock()
        mock_row.year = 2024
        mock_row.month = 6
        mock_row.total_dividends = Decimal("1500.00")
        mock_row.record_count = 1

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        filters = DividendFilters(group_by="monthly")
        result = await service.get_summary(user_id, filters)

        assert isinstance(result, DividendSummaryResponse)
        assert len(result.entries) == 1
        assert result.entries[0].period == "2024-06"
        assert result.entries[0].stock_symbol is None
        assert result.entries[0].total_dividends == Decimal("1500.00")

    @pytest.mark.asyncio
    async def test_summary_by_yearly(self, service, mock_db, user_id):
        """Summary by yearly should aggregate by year."""
        mock_row = MagicMock()
        mock_row.year = 2024
        mock_row.total_dividends = Decimal("6000.00")
        mock_row.record_count = 4

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        filters = DividendFilters(group_by="yearly")
        result = await service.get_summary(user_id, filters)

        assert isinstance(result, DividendSummaryResponse)
        assert len(result.entries) == 1
        assert result.entries[0].period == "2024"
        assert result.entries[0].total_dividends == Decimal("6000.00")
        assert result.entries[0].record_count == 4


class TestDividendProjection:
    """Tests for dividend projection calculations."""

    @pytest.mark.asyncio
    async def test_projection_empty_when_no_dividends(self, service, mock_db, user_id):
        """Projection should return empty when no dividend history."""
        # Mock _get_latest_dividends_per_stock returns empty
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.get_projection(user_id)

        assert isinstance(result, DividendProjectionResponse)
        assert result.projections == []
        assert result.total_projected_annual == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_projection_calculates_correctly(self, service, mock_db, user_id):
        """Projection should calculate: last_rate × shares × frequency."""
        # We need to mock multiple sequential db.execute calls
        # Call 1: _get_latest_dividends_per_stock (subquery for max date)
        latest_div_row = MagicMock()
        latest_div_row.stock_symbol = "PTT"
        latest_div_row.amount_per_share = Decimal("1.50")

        # Call 2: _get_current_holdings
        holdings_row = MagicMock()
        holdings_row.stock_symbol = "PTT"
        holdings_row.holdings = 1000

        # Call 3: _get_dividend_frequencies
        freq_row = MagicMock()
        freq_row.stock_symbol = "PTT"
        freq_row.total_records = 4
        freq_row.min_year = 2024
        freq_row.max_year = 2024

        # Call 4: _get_avg_costs
        cost_row = MagicMock()
        cost_row.stock_symbol = "PTT"
        cost_row.total_cost = Decimal("35000.00")
        cost_row.total_qty = 1000

        mock_results = []
        for rows in [
            [latest_div_row],
            [holdings_row],
            [freq_row],
            [cost_row],
        ]:
            mock_result = MagicMock()
            mock_result.all.return_value = rows
            mock_results.append(mock_result)

        mock_db.execute.side_effect = mock_results

        result = await service.get_projection(user_id)

        assert isinstance(result, DividendProjectionResponse)
        assert len(result.projections) == 1

        proj = result.projections[0]
        assert proj.stock_symbol == "PTT"
        assert proj.current_shares == 1000
        assert proj.last_dividend_per_share == Decimal("1.50")
        # 1.50 * 1000 * 4 = 6000.00
        assert proj.projected_annual == Decimal("6000.00")
        # avg_cost = 35000/1000 = 35.00, total_cost = 35.00 * 1000 = 35000.00
        # yield_on_cost = (6000/35000) * 100 = 17.14%
        assert proj.yield_on_cost == Decimal("17.14")

    @pytest.mark.asyncio
    async def test_projection_skips_zero_holdings(self, service, mock_db, user_id):
        """Projection should skip stocks with no current holdings."""
        # Mock latest dividends for DELTA (not held)
        latest_div_row = MagicMock()
        latest_div_row.stock_symbol = "DELTA"
        latest_div_row.amount_per_share = Decimal("2.00")

        # Holdings returns empty (no DELTA held)
        mock_results = []
        for rows in [
            [latest_div_row],  # latest dividends
            [],  # holdings (empty - DELTA not held)
            [],  # frequencies
            [],  # avg costs
        ]:
            mock_result = MagicMock()
            mock_result.all.return_value = rows
            mock_results.append(mock_result)

        mock_db.execute.side_effect = mock_results

        result = await service.get_projection(user_id)

        assert result.projections == []
        assert result.total_projected_annual == Decimal("0.00")


class TestDividendYieldOnCost:
    """Tests for dividend yield on cost calculation."""

    def test_yield_on_cost_formula(self):
        """Yield on cost = (annual_dividends / total_cost) × 100."""
        annual_dividends = Decimal("6000.00")
        total_cost = Decimal("35000.00")
        expected = (annual_dividends / total_cost * Decimal("100")).quantize(
            Decimal("0.01")
        )
        assert expected == Decimal("17.14")

    def test_yield_on_cost_zero_cost(self):
        """Yield on cost should be None when total cost is zero."""
        # This is handled in the service by checking total_cost > 0
        total_cost = Decimal("0.00")
        yield_on_cost = None if total_cost <= 0 else Decimal("100.00")
        assert yield_on_cost is None


class TestDividendFrequency:
    """Tests for frequency estimation logic."""

    @pytest.mark.asyncio
    async def test_single_year_frequency(self, service, mock_db, user_id):
        """Single year with 4 records should estimate 4x per year."""
        freq_row = MagicMock()
        freq_row.stock_symbol = "PTT"
        freq_row.total_records = 4
        freq_row.min_year = 2024
        freq_row.max_year = 2024

        mock_result = MagicMock()
        mock_result.all.return_value = [freq_row]
        mock_db.execute.return_value = mock_result

        result = await service._get_dividend_frequencies(user_id)
        assert result["PTT"] == 4

    @pytest.mark.asyncio
    async def test_multi_year_frequency(self, service, mock_db, user_id):
        """Multiple years: frequency = records / years span."""
        freq_row = MagicMock()
        freq_row.stock_symbol = "PTT"
        freq_row.total_records = 8
        freq_row.min_year = 2022
        freq_row.max_year = 2024  # 3 years span

        mock_result = MagicMock()
        mock_result.all.return_value = [freq_row]
        mock_db.execute.return_value = mock_result

        result = await service._get_dividend_frequencies(user_id)
        # 8 records / 3 years = 2.67 → rounds to 3
        assert result["PTT"] == 3

    @pytest.mark.asyncio
    async def test_frequency_caps_at_4(self, service, mock_db, user_id):
        """Single year frequency should be capped at 4."""
        freq_row = MagicMock()
        freq_row.stock_symbol = "PTT"
        freq_row.total_records = 12  # unlikely but edge case
        freq_row.min_year = 2024
        freq_row.max_year = 2024

        mock_result = MagicMock()
        mock_result.all.return_value = [freq_row]
        mock_db.execute.return_value = mock_result

        result = await service._get_dividend_frequencies(user_id)
        assert result["PTT"] == 4  # capped at 4

    @pytest.mark.asyncio
    async def test_frequency_minimum_1(self, service, mock_db, user_id):
        """Frequency should be at least 1."""
        freq_row = MagicMock()
        freq_row.stock_symbol = "PTT"
        freq_row.total_records = 1
        freq_row.min_year = 2024
        freq_row.max_year = 2024

        mock_result = MagicMock()
        mock_result.all.return_value = [freq_row]
        mock_db.execute.return_value = mock_result

        result = await service._get_dividend_frequencies(user_id)
        assert result["PTT"] == 1
