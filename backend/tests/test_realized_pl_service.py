"""Unit tests for the realized P/L service."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.realized_pl import RealizedPL
from app.schemas.enums import TermType
from app.schemas.realized_pl import (
    RealizedPLFilters,
    RealizedPLSummaryEntry,
    RealizedPLSummaryResponse,
)
from app.services.realized_pl_service import RealizedPLService


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
    """Create RealizedPLService with mock db."""
    return RealizedPLService(mock_db)


@pytest.fixture
def user_id():
    """A test user ID."""
    return uuid.uuid4()


class TestCalculateAndStore:
    """Tests for the auto-calculation on sell transactions."""

    @pytest.mark.asyncio
    async def test_realized_pl_calculation_profit(self, service, mock_db, user_id):
        """Realized P/L = (sell_price - avg_cost) × sell_qty for profit."""
        tx_id = uuid.uuid4()

        # Mock avg cost query: total_cost=10000, total_qty=100 -> avg_cost=100.00
        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("10000.00")
        avg_cost_row.total_qty = 100
        avg_cost_result = MagicMock()
        avg_cost_result.one.return_value = avg_cost_row

        # Mock hold duration query: buy date 180 days before sell
        buy_row = MagicMock()
        buy_row.date = date(2024, 1, 1)
        buy_row.quantity = 100
        hold_result = MagicMock()
        hold_result.all.return_value = [buy_row]

        mock_db.execute.side_effect = [avg_cost_result, hold_result]

        sell_date = date(2024, 6, 29)  # 180 days after Jan 1
        result = await service.calculate_and_store(
            user_id=user_id,
            transaction_id=tx_id,
            sell_date=sell_date,
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
        )

        # Verify record was created
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]

        assert added_record.user_id == user_id
        assert added_record.stock_symbol == "PTT"
        assert added_record.sell_quantity == 50
        assert added_record.sell_price == Decimal("120.00")
        assert added_record.avg_cost_at_sale == Decimal("100.00")
        # (120 - 100) × 50 = 1000.00
        assert added_record.realized_pl == Decimal("1000.00")
        assert added_record.transaction_id == tx_id

    @pytest.mark.asyncio
    async def test_realized_pl_calculation_loss(self, service, mock_db, user_id):
        """Realized P/L should be negative when selling at a loss."""
        tx_id = uuid.uuid4()

        # avg_cost = 150.00
        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("15000.00")
        avg_cost_row.total_qty = 100
        avg_cost_result = MagicMock()
        avg_cost_result.one.return_value = avg_cost_row

        # Buy date 30 days before sell
        buy_row = MagicMock()
        buy_row.date = date(2024, 5, 30)
        buy_row.quantity = 100
        hold_result = MagicMock()
        hold_result.all.return_value = [buy_row]

        mock_db.execute.side_effect = [avg_cost_result, hold_result]

        sell_date = date(2024, 6, 29)  # 30 days after May 30
        result = await service.calculate_and_store(
            user_id=user_id,
            transaction_id=tx_id,
            sell_date=sell_date,
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("130.00"),
        )

        added_record = mock_db.add.call_args[0][0]
        # (130 - 150) × 50 = -1000.00
        assert added_record.realized_pl == Decimal("-1000.00")

    @pytest.mark.asyncio
    async def test_short_term_classification(self, service, mock_db, user_id):
        """Holdings < 365 days should be classified as Short-term."""
        tx_id = uuid.uuid4()

        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("10000.00")
        avg_cost_row.total_qty = 100
        avg_cost_result = MagicMock()
        avg_cost_result.one.return_value = avg_cost_row

        # Buy date 100 days before sell
        buy_row = MagicMock()
        buy_row.date = date(2024, 3, 21)
        buy_row.quantity = 100
        hold_result = MagicMock()
        hold_result.all.return_value = [buy_row]

        mock_db.execute.side_effect = [avg_cost_result, hold_result]

        sell_date = date(2024, 6, 29)  # 100 days
        await service.calculate_and_store(
            user_id=user_id,
            transaction_id=tx_id,
            sell_date=sell_date,
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.term_type == "Short-term"
        assert added_record.hold_duration_days == 100

    @pytest.mark.asyncio
    async def test_long_term_classification(self, service, mock_db, user_id):
        """Holdings >= 365 days should be classified as Long-term."""
        tx_id = uuid.uuid4()

        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("10000.00")
        avg_cost_row.total_qty = 100
        avg_cost_result = MagicMock()
        avg_cost_result.one.return_value = avg_cost_row

        # Buy date 400 days before sell
        buy_row = MagicMock()
        buy_row.date = date(2023, 5, 25)
        buy_row.quantity = 100
        hold_result = MagicMock()
        hold_result.all.return_value = [buy_row]

        mock_db.execute.side_effect = [avg_cost_result, hold_result]

        sell_date = date(2024, 6, 29)  # 401 days
        await service.calculate_and_store(
            user_id=user_id,
            transaction_id=tx_id,
            sell_date=sell_date,
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.term_type == "Long-term"
        assert added_record.hold_duration_days >= 365

    @pytest.mark.asyncio
    async def test_exactly_365_days_is_long_term(self, service, mock_db, user_id):
        """Exactly 365 days should be classified as Long-term."""
        tx_id = uuid.uuid4()

        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("10000.00")
        avg_cost_row.total_qty = 100
        avg_cost_result = MagicMock()
        avg_cost_result.one.return_value = avg_cost_row

        # Exactly 365 days
        buy_row = MagicMock()
        buy_row.date = date(2023, 6, 30)
        buy_row.quantity = 100
        hold_result = MagicMock()
        hold_result.all.return_value = [buy_row]

        mock_db.execute.side_effect = [avg_cost_result, hold_result]

        sell_date = date(2024, 6, 29)  # 365 days
        await service.calculate_and_store(
            user_id=user_id,
            transaction_id=tx_id,
            sell_date=sell_date,
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.hold_duration_days == 365
        assert added_record.term_type == "Long-term"

    @pytest.mark.asyncio
    async def test_weighted_avg_hold_duration(self, service, mock_db, user_id):
        """Hold duration should be weighted by quantity across multiple buys."""
        tx_id = uuid.uuid4()

        avg_cost_row = MagicMock()
        avg_cost_row.total_cost = Decimal("20000.00")
        avg_cost_row.total_qty = 200
        avg_cost_result = MagicMock()
        avg_cost_result.one.return_value = avg_cost_row

        # Two buys: 100 shares 400 days ago, 100 shares 100 days ago
        sell_date = date(2024, 6, 29)
        buy_row1 = MagicMock()
        buy_row1.date = date(2023, 5, 25)  # ~400 days
        buy_row1.quantity = 100
        buy_row2 = MagicMock()
        buy_row2.date = date(2024, 3, 21)  # ~100 days
        buy_row2.quantity = 100
        hold_result = MagicMock()
        hold_result.all.return_value = [buy_row1, buy_row2]

        mock_db.execute.side_effect = [avg_cost_result, hold_result]

        await service.calculate_and_store(
            user_id=user_id,
            transaction_id=tx_id,
            sell_date=sell_date,
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
        )

        added_record = mock_db.add.call_args[0][0]
        # Weighted avg: (400*100 + 100*100) / 200 = 250 days (approximately)
        days1 = (sell_date - date(2023, 5, 25)).days
        days2 = (sell_date - date(2024, 3, 21)).days
        expected_duration = (days1 * 100 + days2 * 100) // 200
        assert added_record.hold_duration_days == expected_duration


class TestListRealizedPL:
    """Tests for listing realized P/L records."""

    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_records(self, service, mock_db, user_id):
        """List should return empty list when no records exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.list_realized_pl(user_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_symbol_filter(self, service, mock_db, user_id):
        """List should filter by stock symbol."""
        record = RealizedPL(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 6, 15),
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
            avg_cost_at_sale=Decimal("100.00"),
            realized_pl=Decimal("1000.00"),
            hold_duration_days=180,
            term_type="Short-term",
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record]
        mock_db.execute.return_value = mock_result

        filters = RealizedPLFilters(stock_symbol="PTT")
        result = await service.list_realized_pl(user_id, filters)

        assert len(result) == 1
        assert result[0].stock_symbol == "PTT"

    @pytest.mark.asyncio
    async def test_list_with_date_range_filter(self, service, mock_db, user_id):
        """List should filter by date range."""
        record = RealizedPL(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 6, 15),
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
            avg_cost_at_sale=Decimal("100.00"),
            realized_pl=Decimal("1000.00"),
            hold_duration_days=180,
            term_type="Short-term",
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record]
        mock_db.execute.return_value = mock_result

        filters = RealizedPLFilters(
            date_from=date(2024, 6, 1), date_to=date(2024, 6, 30)
        )
        result = await service.list_realized_pl(user_id, filters)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_with_term_type_filter(self, service, mock_db, user_id):
        """List should filter by term type."""
        record = RealizedPL(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 6, 15),
            stock_symbol="PTT",
            sell_quantity=50,
            sell_price=Decimal("120.00"),
            avg_cost_at_sale=Decimal("100.00"),
            realized_pl=Decimal("1000.00"),
            hold_duration_days=180,
            term_type="Short-term",
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record]
        mock_db.execute.return_value = mock_result

        filters = RealizedPLFilters(term_type=TermType.SHORT_TERM)
        result = await service.list_realized_pl(user_id, filters)

        assert len(result) == 1
        assert result[0].term_type == "Short-term"


class TestGetSummary:
    """Tests for realized P/L summary endpoint."""

    @pytest.mark.asyncio
    async def test_summary_all_time_only(self, service, mock_db, user_id):
        """Summary without group_by returns all-time totals only."""
        # Mock all-time totals query
        all_time_row = MagicMock()
        all_time_row.total = Decimal("5000.00")
        all_time_row.short_term = Decimal("3000.00")
        all_time_row.long_term = Decimal("2000.00")
        mock_result = MagicMock()
        mock_result.one.return_value = all_time_row
        mock_db.execute.return_value = mock_result

        result = await service.get_summary(user_id)

        assert isinstance(result, RealizedPLSummaryResponse)
        assert result.all_time_total == Decimal("5000.00")
        assert result.all_time_short_term == Decimal("3000.00")
        assert result.all_time_long_term == Decimal("2000.00")
        assert result.entries == []

    @pytest.mark.asyncio
    async def test_summary_monthly_grouping(self, service, mock_db, user_id):
        """Summary with monthly group_by returns entries per month."""
        # Mock monthly summary query
        monthly_row = MagicMock()
        monthly_row.year = 2024
        monthly_row.month = 6
        monthly_row.total_pl = Decimal("5000.00")
        monthly_row.total_short = Decimal("3000.00")
        monthly_row.total_long = Decimal("2000.00")
        monthly_row.record_count = 3
        monthly_result = MagicMock()
        monthly_result.all.return_value = [monthly_row]

        # Mock all-time totals query
        all_time_row = MagicMock()
        all_time_row.total = Decimal("5000.00")
        all_time_row.short_term = Decimal("3000.00")
        all_time_row.long_term = Decimal("2000.00")
        all_time_result = MagicMock()
        all_time_result.one.return_value = all_time_row

        mock_db.execute.side_effect = [monthly_result, all_time_result]

        filters = RealizedPLFilters(group_by="monthly")
        result = await service.get_summary(user_id, filters)

        assert isinstance(result, RealizedPLSummaryResponse)
        assert len(result.entries) == 1
        assert result.entries[0].period == "2024-06"
        assert result.entries[0].total_realized_pl == Decimal("5000.00")
        assert result.entries[0].total_short_term == Decimal("3000.00")
        assert result.entries[0].total_long_term == Decimal("2000.00")
        assert result.entries[0].record_count == 3
        assert result.all_time_total == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_summary_yearly_grouping(self, service, mock_db, user_id):
        """Summary with yearly group_by returns entries per year."""
        # Mock yearly summary query
        yearly_row = MagicMock()
        yearly_row.year = 2024
        yearly_row.total_pl = Decimal("12000.00")
        yearly_row.total_short = Decimal("8000.00")
        yearly_row.total_long = Decimal("4000.00")
        yearly_row.record_count = 10
        yearly_result = MagicMock()
        yearly_result.all.return_value = [yearly_row]

        # Mock all-time totals query
        all_time_row = MagicMock()
        all_time_row.total = Decimal("12000.00")
        all_time_row.short_term = Decimal("8000.00")
        all_time_row.long_term = Decimal("4000.00")
        all_time_result = MagicMock()
        all_time_result.one.return_value = all_time_row

        mock_db.execute.side_effect = [yearly_result, all_time_result]

        filters = RealizedPLFilters(group_by="yearly")
        result = await service.get_summary(user_id, filters)

        assert isinstance(result, RealizedPLSummaryResponse)
        assert len(result.entries) == 1
        assert result.entries[0].period == "2024"
        assert result.entries[0].total_realized_pl == Decimal("12000.00")
        assert result.entries[0].record_count == 10


class TestAvgCostCalculation:
    """Tests for the average cost calculation helper."""

    @pytest.mark.asyncio
    async def test_avg_cost_single_buy(self, service, mock_db, user_id):
        """Avg cost with single buy = buy price."""
        row = MagicMock()
        row.total_cost = Decimal("10000.00")
        row.total_qty = 100
        mock_result = MagicMock()
        mock_result.one.return_value = row
        mock_db.execute.return_value = mock_result

        result = await service._calculate_avg_cost(user_id, "PTT")
        assert result == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_avg_cost_multiple_buys(self, service, mock_db, user_id):
        """Avg cost with multiple buys = weighted average."""
        # 100 shares @ 80 + 200 shares @ 110 = (8000 + 22000) / 300 = 100.00
        row = MagicMock()
        row.total_cost = Decimal("30000.00")
        row.total_qty = 300
        mock_result = MagicMock()
        mock_result.one.return_value = row
        mock_db.execute.return_value = mock_result

        result = await service._calculate_avg_cost(user_id, "PTT")
        assert result == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_avg_cost_zero_quantity(self, service, mock_db, user_id):
        """Avg cost returns 0 when no holdings exist."""
        row = MagicMock()
        row.total_cost = None
        row.total_qty = 0
        mock_result = MagicMock()
        mock_result.one.return_value = row
        mock_db.execute.return_value = mock_result

        result = await service._calculate_avg_cost(user_id, "PTT")
        assert result == Decimal("0.00")


class TestHoldDurationCalculation:
    """Tests for the hold duration calculation helper."""

    @pytest.mark.asyncio
    async def test_hold_duration_single_buy(self, service, mock_db, user_id):
        """Hold duration with single buy = days between buy and sell."""
        buy_row = MagicMock()
        buy_row.date = date(2024, 1, 1)
        buy_row.quantity = 100
        mock_result = MagicMock()
        mock_result.all.return_value = [buy_row]
        mock_db.execute.return_value = mock_result

        sell_date = date(2024, 7, 1)
        result = await service._calculate_hold_duration(user_id, "PTT", sell_date)
        expected_days = (sell_date - date(2024, 1, 1)).days
        assert result == expected_days

    @pytest.mark.asyncio
    async def test_hold_duration_no_buys(self, service, mock_db, user_id):
        """Hold duration returns 0 when no buys exist."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service._calculate_hold_duration(user_id, "PTT", date(2024, 6, 29))
        assert result == 0

    @pytest.mark.asyncio
    async def test_hold_duration_weighted_multiple_buys(self, service, mock_db, user_id):
        """Hold duration is weighted by quantity for multiple buys."""
        sell_date = date(2024, 6, 29)

        buy_row1 = MagicMock()
        buy_row1.date = date(2024, 1, 1)  # ~180 days before
        buy_row1.quantity = 50
        buy_row2 = MagicMock()
        buy_row2.date = date(2024, 4, 1)  # ~89 days before
        buy_row2.quantity = 150

        mock_result = MagicMock()
        mock_result.all.return_value = [buy_row1, buy_row2]
        mock_db.execute.return_value = mock_result

        result = await service._calculate_hold_duration(user_id, "PTT", sell_date)

        # Weighted: (180*50 + 89*150) / 200 = (9000 + 13350) / 200 = 111
        days1 = (sell_date - date(2024, 1, 1)).days
        days2 = (sell_date - date(2024, 4, 1)).days
        expected = (days1 * 50 + days2 * 150) // 200
        assert result == expected
