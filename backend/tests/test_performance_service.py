"""Unit tests for PerformanceService."""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.performance_snapshot import PerformanceSnapshot
from app.models.user import User
from app.schemas.performance import SnapshotCreate, SnapshotFilters, SnapshotUpdate
from app.services.performance_service import PerformanceService


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
    """Create a PerformanceService instance."""
    return PerformanceService(session)


class TestRecordSnapshot:
    """Tests for PerformanceService.record_snapshot."""

    async def test_record_snapshot_persists_correctly(self, service, user_id):
        """Record snapshot stores all fields correctly."""
        data = SnapshotCreate(
            date=date(2024, 6, 15),
            total_portfolio_value=Decimal("500000.00"),
            total_cost=Decimal("400000.00"),
        )

        result = await service.record_snapshot(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.date == date(2024, 6, 15)
        assert result.total_portfolio_value == Decimal("500000.00")
        assert result.total_cost == Decimal("400000.00")
        assert result.created_at is not None
        assert result.updated_at is not None

    async def test_record_snapshot_unique_id(self, service, user_id):
        """Each snapshot gets a unique ID."""
        data1 = SnapshotCreate(
            date=date(2024, 6, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        data2 = SnapshotCreate(
            date=date(2024, 6, 2),
            total_portfolio_value=Decimal("110000.00"),
            total_cost=Decimal("90000.00"),
        )

        s1 = await service.record_snapshot(user_id, data1)
        s2 = await service.record_snapshot(user_id, data2)

        assert s1.id != s2.id


class TestListSnapshots:
    """Tests for PerformanceService.list_snapshots."""

    async def test_list_empty_returns_empty(self, service, user_id):
        """List returns empty when no snapshots exist."""
        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert result.snapshots == []
        assert result.cumulative_return.cumulative_return_percent is None

    async def test_list_sorted_by_date_ascending(self, service, user_id):
        """Snapshots are returned sorted by date ascending."""
        dates_values = [
            (date(2024, 3, 1), Decimal("300000.00")),
            (date(2024, 1, 1), Decimal("100000.00")),
            (date(2024, 2, 1), Decimal("200000.00")),
        ]
        for d, val in dates_values:
            data = SnapshotCreate(
                date=d,
                total_portfolio_value=val,
                total_cost=Decimal("90000.00"),
            )
            await service.record_snapshot(user_id, data)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert len(result.snapshots) == 3
        assert result.snapshots[0].date == date(2024, 1, 1)
        assert result.snapshots[1].date == date(2024, 2, 1)
        assert result.snapshots[2].date == date(2024, 3, 1)

    async def test_period_return_first_snapshot_is_none(self, service, user_id):
        """First snapshot has period_return = None (N/A)."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        await service.record_snapshot(user_id, data)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert len(result.snapshots) == 1
        assert result.snapshots[0].period_return is None

    async def test_period_return_calculation(self, service, user_id):
        """Period return calculated correctly between consecutive snapshots."""
        # Snapshot 1: 100000, Snapshot 2: 120000
        # Period return = (120000 - 100000) / 100000 * 100 = 20.00%
        data1 = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        data2 = SnapshotCreate(
            date=date(2024, 2, 1),
            total_portfolio_value=Decimal("120000.00"),
            total_cost=Decimal("90000.00"),
        )
        await service.record_snapshot(user_id, data1)
        await service.record_snapshot(user_id, data2)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert result.snapshots[0].period_return is None
        assert result.snapshots[1].period_return == Decimal("20.00")

    async def test_period_return_negative(self, service, user_id):
        """Period return can be negative when value decreases."""
        # 200000 -> 180000: (180000-200000)/200000*100 = -10.00
        data1 = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("200000.00"),
            total_cost=Decimal("150000.00"),
        )
        data2 = SnapshotCreate(
            date=date(2024, 2, 1),
            total_portfolio_value=Decimal("180000.00"),
            total_cost=Decimal("150000.00"),
        )
        await service.record_snapshot(user_id, data1)
        await service.record_snapshot(user_id, data2)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert result.snapshots[1].period_return == Decimal("-10.00")

    async def test_pl_calculation(self, service, user_id):
        """P/L is calculated as total_portfolio_value - total_cost."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("150000.00"),
            total_cost=Decimal("100000.00"),
        )
        await service.record_snapshot(user_id, data)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert result.snapshots[0].pl == Decimal("50000.00")

    async def test_cumulative_return_calculation(self, service, user_id):
        """Cumulative return calculated from earliest to latest snapshot."""
        # Earliest 100000, latest 150000: (150000-100000)/100000*100 = 50.00
        for d, val in [
            (date(2024, 1, 1), Decimal("100000.00")),
            (date(2024, 2, 1), Decimal("120000.00")),
            (date(2024, 3, 1), Decimal("150000.00")),
        ]:
            data = SnapshotCreate(
                date=d,
                total_portfolio_value=val,
                total_cost=Decimal("90000.00"),
            )
            await service.record_snapshot(user_id, data)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert result.cumulative_return.cumulative_return_percent == Decimal("50.00")
        assert result.cumulative_return.earliest_value == Decimal("100000.00")
        assert result.cumulative_return.latest_value == Decimal("150000.00")
        assert result.cumulative_return.earliest_date == date(2024, 1, 1)
        assert result.cumulative_return.latest_date == date(2024, 3, 1)

    async def test_cumulative_return_single_snapshot_is_none(self, service, user_id):
        """Cumulative return is None with only one snapshot."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        await service.record_snapshot(user_id, data)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert result.cumulative_return.cumulative_return_percent is None

    async def test_date_range_filter_inclusive(self, service, user_id):
        """Date range filter includes snapshots on start/end dates."""
        for d in [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1), date(2024, 4, 1)]:
            data = SnapshotCreate(
                date=d,
                total_portfolio_value=Decimal("100000.00"),
                total_cost=Decimal("90000.00"),
            )
            await service.record_snapshot(user_id, data)

        filters = SnapshotFilters(date_from=date(2024, 2, 1), date_to=date(2024, 3, 1))
        result = await service.list_snapshots(user_id, filters)

        assert len(result.snapshots) == 2
        assert result.snapshots[0].date == date(2024, 2, 1)
        assert result.snapshots[1].date == date(2024, 3, 1)

    async def test_monthly_aggregation(self, service, user_id):
        """Monthly aggregation returns last snapshot per month."""
        # Multiple snapshots in January, one in February
        for d, val in [
            (date(2024, 1, 5), Decimal("100000.00")),
            (date(2024, 1, 15), Decimal("105000.00")),
            (date(2024, 1, 25), Decimal("110000.00")),  # last in Jan
            (date(2024, 2, 10), Decimal("115000.00")),  # last in Feb
        ]:
            data = SnapshotCreate(
                date=d,
                total_portfolio_value=val,
                total_cost=Decimal("90000.00"),
            )
            await service.record_snapshot(user_id, data)

        filters = SnapshotFilters(aggregation="monthly")
        result = await service.list_snapshots(user_id, filters)

        assert len(result.snapshots) == 2
        # Jan entry should be the last one (25th with value 110000)
        assert result.snapshots[0].total_portfolio_value == Decimal("110000.00")
        # Feb entry
        assert result.snapshots[1].total_portfolio_value == Decimal("115000.00")

    async def test_yearly_aggregation(self, service, user_id):
        """Yearly aggregation returns last snapshot per year."""
        for d, val in [
            (date(2023, 6, 1), Decimal("80000.00")),
            (date(2023, 12, 1), Decimal("95000.00")),  # last in 2023
            (date(2024, 3, 1), Decimal("100000.00")),
            (date(2024, 6, 1), Decimal("120000.00")),  # last in 2024
        ]:
            data = SnapshotCreate(
                date=d,
                total_portfolio_value=val,
                total_cost=Decimal("90000.00"),
            )
            await service.record_snapshot(user_id, data)

        filters = SnapshotFilters(aggregation="yearly")
        result = await service.list_snapshots(user_id, filters)

        assert len(result.snapshots) == 2
        assert result.snapshots[0].total_portfolio_value == Decimal("95000.00")
        assert result.snapshots[1].total_portfolio_value == Decimal("120000.00")


class TestEditSnapshot:
    """Tests for PerformanceService.edit_snapshot."""

    async def test_edit_updates_fields(self, service, user_id):
        """Edit updates specified fields while preserving others."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        snapshot = await service.record_snapshot(user_id, data)

        update = SnapshotUpdate(total_portfolio_value=Decimal("120000.00"))
        result = await service.edit_snapshot(user_id, snapshot.id, update)

        assert result.total_portfolio_value == Decimal("120000.00")
        assert result.total_cost == Decimal("90000.00")  # preserved
        assert result.date == date(2024, 1, 1)  # preserved

    async def test_edit_date(self, service, user_id):
        """Edit can change the snapshot date."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        snapshot = await service.record_snapshot(user_id, data)

        update = SnapshotUpdate(date=date(2024, 1, 15))
        result = await service.edit_snapshot(user_id, snapshot.id, update)

        assert result.date == date(2024, 1, 15)

    async def test_edit_multiple_fields(self, service, user_id):
        """Edit can update multiple fields at once."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        snapshot = await service.record_snapshot(user_id, data)

        update = SnapshotUpdate(
            date=date(2024, 2, 1),
            total_portfolio_value=Decimal("150000.00"),
            total_cost=Decimal("95000.00"),
        )
        result = await service.edit_snapshot(user_id, snapshot.id, update)

        assert result.date == date(2024, 2, 1)
        assert result.total_portfolio_value == Decimal("150000.00")
        assert result.total_cost == Decimal("95000.00")

    async def test_edit_not_found_raises_404(self, service, user_id):
        """Edit a non-existent snapshot raises 404."""
        fake_id = uuid.uuid4()
        update = SnapshotUpdate(total_portfolio_value=Decimal("100000.00"))

        with pytest.raises(HTTPException) as exc_info:
            await service.edit_snapshot(user_id, fake_id, update)

        assert exc_info.value.status_code == 404

    async def test_edit_recalculates_adjacent_period_returns(self, service, user_id):
        """After edit, period returns are recalculated for adjacent snapshots."""
        # Create 3 snapshots: 100k, 120k, 150k
        for d, val in [
            (date(2024, 1, 1), Decimal("100000.00")),
            (date(2024, 2, 1), Decimal("120000.00")),
            (date(2024, 3, 1), Decimal("150000.00")),
        ]:
            data = SnapshotCreate(
                date=d, total_portfolio_value=val, total_cost=Decimal("90000.00")
            )
            await service.record_snapshot(user_id, data)

        # Get the middle snapshot's ID
        filters = SnapshotFilters()
        before = await service.list_snapshots(user_id, filters)
        mid_id = uuid.UUID(before.snapshots[1].id)

        # Edit middle snapshot value from 120k to 110k
        update = SnapshotUpdate(total_portfolio_value=Decimal("110000.00"))
        await service.edit_snapshot(user_id, mid_id, update)

        # Re-list and verify period returns are recalculated
        after = await service.list_snapshots(user_id, filters)
        # 2nd period return: (110000 - 100000) / 100000 * 100 = 10.00
        assert after.snapshots[1].period_return == Decimal("10.00")
        # 3rd period return: (150000 - 110000) / 110000 * 100 = 36.36
        assert after.snapshots[2].period_return == Decimal("36.36")


class TestDeleteSnapshot:
    """Tests for PerformanceService.delete_snapshot."""

    async def test_delete_removes_record(self, service, user_id):
        """Delete removes the snapshot from the list."""
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        snapshot = await service.record_snapshot(user_id, data)

        await service.delete_snapshot(user_id, snapshot.id)

        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)
        assert len(result.snapshots) == 0

    async def test_delete_not_found_raises_404(self, service, user_id):
        """Delete a non-existent snapshot raises 404."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_snapshot(user_id, fake_id)

        assert exc_info.value.status_code == 404

    async def test_delete_recalculates_adjacent_period_returns(self, service, user_id):
        """After deleting a middle snapshot, period returns are recalculated."""
        # Create 3 snapshots: 100k, 120k, 150k
        for d, val in [
            (date(2024, 1, 1), Decimal("100000.00")),
            (date(2024, 2, 1), Decimal("120000.00")),
            (date(2024, 3, 1), Decimal("150000.00")),
        ]:
            data = SnapshotCreate(
                date=d, total_portfolio_value=val, total_cost=Decimal("90000.00")
            )
            await service.record_snapshot(user_id, data)

        # Get the middle snapshot's ID
        filters = SnapshotFilters()
        before = await service.list_snapshots(user_id, filters)
        mid_id = uuid.UUID(before.snapshots[1].id)

        # Delete the middle snapshot
        await service.delete_snapshot(user_id, mid_id)

        # Re-list: now 2 snapshots (100k, 150k)
        after = await service.list_snapshots(user_id, filters)
        assert len(after.snapshots) == 2
        assert after.snapshots[0].period_return is None
        # (150000 - 100000) / 100000 * 100 = 50.00
        assert after.snapshots[1].period_return == Decimal("50.00")


class TestCalculatePeriodReturn:
    """Tests for PerformanceService.calculate_period_return."""

    def test_positive_return(self, service):
        """Positive period return when value increases."""
        result = service.calculate_period_return(
            Decimal("120000.00"), Decimal("100000.00")
        )
        assert result == Decimal("20.00")

    def test_negative_return(self, service):
        """Negative period return when value decreases."""
        result = service.calculate_period_return(
            Decimal("80000.00"), Decimal("100000.00")
        )
        assert result == Decimal("-20.00")

    def test_zero_previous_returns_none(self, service):
        """Returns None when previous value is zero (avoid division by zero)."""
        result = service.calculate_period_return(
            Decimal("100000.00"), Decimal("0")
        )
        assert result is None

    def test_no_change_returns_zero(self, service):
        """Returns 0.00 when value is unchanged."""
        result = service.calculate_period_return(
            Decimal("100000.00"), Decimal("100000.00")
        )
        assert result == Decimal("0.00")

    def test_rounds_to_2_decimal_places(self, service):
        """Result is rounded to 2 decimal places."""
        # (133333 - 100000) / 100000 * 100 = 33.333...
        result = service.calculate_period_return(
            Decimal("133333.00"), Decimal("100000.00")
        )
        assert result == Decimal("33.33")


class TestCalculateCumulativeReturn:
    """Tests for PerformanceService.calculate_cumulative_return."""

    def test_positive_cumulative(self, service):
        """Positive cumulative return."""
        result = service.calculate_cumulative_return(
            Decimal("100000.00"), Decimal("150000.00")
        )
        assert result == Decimal("50.00")

    def test_negative_cumulative(self, service):
        """Negative cumulative return."""
        result = service.calculate_cumulative_return(
            Decimal("200000.00"), Decimal("150000.00")
        )
        assert result == Decimal("-25.00")

    def test_zero_earliest_returns_none(self, service):
        """Returns None when earliest value is zero."""
        result = service.calculate_cumulative_return(
            Decimal("0"), Decimal("100000.00")
        )
        assert result is None


class TestDataIsolation:
    """Tests for per-user data isolation."""

    async def test_list_does_not_return_other_users_snapshots(
        self, service, session, user_id
    ):
        """List only returns snapshots belonging to the requesting user."""
        # Create snapshot for test user
        data = SnapshotCreate(
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("100000.00"),
            total_cost=Decimal("90000.00"),
        )
        await service.record_snapshot(user_id, data)

        # Create another user and their snapshot
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

        other_snapshot = PerformanceSnapshot(
            id=uuid.uuid4(),
            user_id=other_user_id,
            date=date(2024, 1, 1),
            total_portfolio_value=Decimal("200000.00"),
            total_cost=Decimal("180000.00"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_snapshot)
        await session.flush()

        # List should only show the first user's snapshot
        filters = SnapshotFilters()
        result = await service.list_snapshots(user_id, filters)

        assert len(result.snapshots) == 1
        assert result.snapshots[0].total_portfolio_value == Decimal("100000.00")
