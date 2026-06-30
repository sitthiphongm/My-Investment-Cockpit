"""Unit tests for AlertService."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.price_alert import PriceAlert
from app.models.user import User
from app.schemas.alerts import AlertCreate
from app.schemas.enums import AlertType
from app.services.alert_service import AlertService


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
    """Create an AlertService instance."""
    return AlertService(session)


class TestCreateAlert:
    """Tests for AlertService.create_alert."""

    async def test_create_alert_above(self, service, user_id):
        """Create an 'Above' alert persists all fields correctly."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
            note="Target breakout",
        )

        result = await service.create_alert(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.stock_symbol == "AAPL"
        assert result.alert_type == "Above"
        assert result.target_price == Decimal("200.00")
        assert result.note == "Target breakout"
        assert result.triggered is False
        assert result.created_at is not None

    async def test_create_alert_below(self, service, user_id):
        """Create a 'Below' alert persists correctly."""
        data = AlertCreate(
            stock_symbol="TSLA",
            alert_type=AlertType.BELOW,
            target_price=Decimal("150.50"),
            note=None,
        )

        result = await service.create_alert(user_id, data)

        assert result.alert_type == "Below"
        assert result.target_price == Decimal("150.50")
        assert result.note is None

    async def test_create_multiple_alerts_per_symbol(self, service, user_id):
        """Multiple alerts for the same symbol are allowed."""
        data1 = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        data2 = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.BELOW,
            target_price=Decimal("150.00"),
        )
        data3 = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("250.00"),
        )

        a1 = await service.create_alert(user_id, data1)
        a2 = await service.create_alert(user_id, data2)
        a3 = await service.create_alert(user_id, data3)

        alerts = await service.list_active_alerts(user_id)
        assert len(alerts) == 3

    async def test_symbol_is_uppercased(self, service, user_id):
        """Stock symbol is stored in uppercase."""
        data = AlertCreate(
            stock_symbol="aapl",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )

        result = await service.create_alert(user_id, data)

        assert result.stock_symbol == "AAPL"


class TestListActiveAlerts:
    """Tests for AlertService.list_active_alerts."""

    async def test_list_returns_only_active_alerts(self, service, user_id, session):
        """List only returns non-triggered alerts."""
        # Create active alert
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        # Create a triggered alert directly
        triggered_alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            stock_symbol="TSLA",
            alert_type="Below",
            target_price=Decimal("100.00"),
            triggered=True,
            created_at=datetime.utcnow(),
        )
        session.add(triggered_alert)
        await session.flush()

        alerts = await service.list_active_alerts(user_id)

        assert len(alerts) == 1
        assert alerts[0].stock_symbol == "AAPL"

    async def test_list_sorted_by_symbol(self, service, user_id):
        """List returns alerts sorted by symbol ascending."""
        symbols = ["TSLA", "AAPL", "MSFT", "AMZN"]
        for s in symbols:
            data = AlertCreate(
                stock_symbol=s,
                alert_type=AlertType.ABOVE,
                target_price=Decimal("100.00"),
            )
            await service.create_alert(user_id, data)

        alerts = await service.list_active_alerts(user_id)

        assert len(alerts) == 4
        assert alerts[0].stock_symbol == "AAPL"
        assert alerts[1].stock_symbol == "AMZN"
        assert alerts[2].stock_symbol == "MSFT"
        assert alerts[3].stock_symbol == "TSLA"

    async def test_list_empty_when_no_alerts(self, service, user_id):
        """List returns empty when user has no alerts."""
        alerts = await service.list_active_alerts(user_id)
        assert alerts == []

    async def test_list_does_not_return_other_users_alerts(
        self, service, user_id, other_user_id, session
    ):
        """List only returns alerts belonging to the requesting user."""
        # Create alert for user
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        # Create alert for other user
        other_alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="MSFT",
            alert_type="Below",
            target_price=Decimal("300.00"),
            triggered=False,
            created_at=datetime.utcnow(),
        )
        session.add(other_alert)
        await session.flush()

        alerts = await service.list_active_alerts(user_id)

        assert len(alerts) == 1
        assert alerts[0].stock_symbol == "AAPL"


class TestDeleteAlert:
    """Tests for AlertService.delete_alert."""

    async def test_delete_removes_alert(self, service, user_id):
        """Delete removes the alert record."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        alert = await service.create_alert(user_id, data)
        alert_id = alert.id

        await service.delete_alert(user_id, alert_id)

        alerts = await service.list_active_alerts(user_id)
        assert len(alerts) == 0

    async def test_delete_not_found_raises_404(self, service, user_id):
        """Delete a non-existent alert raises 404."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_alert(user_id, fake_id)

        assert exc_info.value.status_code == 404

    async def test_delete_other_users_alert_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot delete another user's alert."""
        other_alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            alert_type="Above",
            target_price=Decimal("300.00"),
            triggered=False,
            created_at=datetime.utcnow(),
        )
        session.add(other_alert)
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_alert(user_id, other_alert.id)

        assert exc_info.value.status_code == 404


class TestCheckAndTriggerAlerts:
    """Tests for AlertService.check_and_trigger_alerts."""

    async def test_trigger_above_when_price_at_target(self, service, user_id):
        """Above alert triggers when current_price == target_price."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("200.00")}
        )

        assert len(triggered) == 1
        assert triggered[0].stock_symbol == "AAPL"
        assert triggered[0].triggered is True

    async def test_trigger_above_when_price_exceeds_target(self, service, user_id):
        """Above alert triggers when current_price > target_price."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("210.00")}
        )

        assert len(triggered) == 1
        assert triggered[0].triggered is True

    async def test_no_trigger_above_when_price_below_target(self, service, user_id):
        """Above alert does NOT trigger when current_price < target_price."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("199.99")}
        )

        assert len(triggered) == 0

    async def test_trigger_below_when_price_at_target(self, service, user_id):
        """Below alert triggers when current_price == target_price."""
        data = AlertCreate(
            stock_symbol="TSLA",
            alert_type=AlertType.BELOW,
            target_price=Decimal("150.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts(
            {"TSLA": Decimal("150.00")}
        )

        assert len(triggered) == 1
        assert triggered[0].triggered is True

    async def test_trigger_below_when_price_below_target(self, service, user_id):
        """Below alert triggers when current_price < target_price."""
        data = AlertCreate(
            stock_symbol="TSLA",
            alert_type=AlertType.BELOW,
            target_price=Decimal("150.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts(
            {"TSLA": Decimal("140.00")}
        )

        assert len(triggered) == 1

    async def test_no_trigger_below_when_price_above_target(self, service, user_id):
        """Below alert does NOT trigger when current_price > target_price."""
        data = AlertCreate(
            stock_symbol="TSLA",
            alert_type=AlertType.BELOW,
            target_price=Decimal("150.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts(
            {"TSLA": Decimal("150.01")}
        )

        assert len(triggered) == 0

    async def test_trigger_multiple_alerts_same_symbol(self, service, user_id):
        """Multiple alerts for same symbol can trigger independently."""
        data1 = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        data2 = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("250.00"),
        )
        await service.create_alert(user_id, data1)
        await service.create_alert(user_id, data2)

        # Price at 210 should trigger first but not second
        triggered = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("210.00")}
        )

        assert len(triggered) == 1
        assert triggered[0].target_price == Decimal("200.00")

    async def test_triggered_alerts_not_retriggered(self, service, user_id):
        """Already triggered alerts are not triggered again."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        # First trigger
        triggered1 = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("210.00")}
        )
        assert len(triggered1) == 1

        # Second check should not re-trigger
        triggered2 = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("220.00")}
        )
        assert len(triggered2) == 0

    async def test_skips_symbols_with_none_price(self, service, user_id):
        """Symbols with None price are skipped."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts({"AAPL": None})

        assert len(triggered) == 0

    async def test_empty_prices_returns_empty(self, service, user_id):
        """Empty market prices dict returns no triggered alerts."""
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        triggered = await service.check_and_trigger_alerts({})

        assert len(triggered) == 0

    async def test_trigger_across_multiple_users(
        self, service, user_id, other_user_id, session
    ):
        """Trigger check affects alerts from all users."""
        # Create alert for first user
        data = AlertCreate(
            stock_symbol="AAPL",
            alert_type=AlertType.ABOVE,
            target_price=Decimal("200.00"),
        )
        await service.create_alert(user_id, data)

        # Create alert for other user
        other_alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="AAPL",
            alert_type="Above",
            target_price=Decimal("190.00"),
            triggered=False,
            created_at=datetime.utcnow(),
        )
        session.add(other_alert)
        await session.flush()

        # Price at 200 should trigger both
        triggered = await service.check_and_trigger_alerts(
            {"AAPL": Decimal("200.00")}
        )

        assert len(triggered) == 2


class TestShouldTrigger:
    """Tests for AlertService._should_trigger static method."""

    def test_above_at_target(self):
        """Above triggers at exact target."""
        assert AlertService._should_trigger("Above", Decimal("100"), Decimal("100")) is True

    def test_above_over_target(self):
        """Above triggers above target."""
        assert AlertService._should_trigger("Above", Decimal("100"), Decimal("101")) is True

    def test_above_below_target(self):
        """Above does not trigger below target."""
        assert AlertService._should_trigger("Above", Decimal("100"), Decimal("99")) is False

    def test_below_at_target(self):
        """Below triggers at exact target."""
        assert AlertService._should_trigger("Below", Decimal("100"), Decimal("100")) is True

    def test_below_under_target(self):
        """Below triggers under target."""
        assert AlertService._should_trigger("Below", Decimal("100"), Decimal("99")) is True

    def test_below_over_target(self):
        """Below does not trigger over target."""
        assert AlertService._should_trigger("Below", Decimal("100"), Decimal("101")) is False
