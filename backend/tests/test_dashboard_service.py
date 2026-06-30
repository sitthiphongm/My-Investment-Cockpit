"""Unit tests for DashboardService."""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.models.user import User
from app.schemas.dashboard import BrokerCapital, DashboardResponse
from app.schemas.market_data import TickerInfo
from app.services.dashboard_service import DashboardService


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
    """Create a DashboardService instance without market data service."""
    return DashboardService(session)


async def _create_transfer(session, user_id, broker, transfer_type, amount, d=None):
    """Helper to create a transfer record."""
    transfer = Transfer(
        id=uuid.uuid4(),
        user_id=user_id,
        date=d or date(2024, 6, 15),
        broker=broker,
        transfer_type=transfer_type,
        amount=Decimal(str(amount)),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(transfer)
    await session.flush()
    return transfer


async def _create_transaction(session, user_id, symbol, action, qty, price, broker="Webull"):
    """Helper to create a transaction record."""
    gross_value = Decimal(str(qty)) * Decimal(str(price))
    fee = Decimal("0.00")
    vat = Decimal("0.00")
    if action == "Buy":
        net_cf = gross_value + fee + vat
    elif action == "Sell":
        net_cf = gross_value - fee - vat
    else:
        net_cf = gross_value

    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        date=date(2024, 6, 15),
        stock_symbol=symbol,
        action=action,
        quantity=qty,
        price_per_share=Decimal(str(price)),
        gross_value=gross_value,
        brokerage_fee=fee,
        vat=vat,
        net_capital_flow=net_cf,
        broker=broker,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(tx)
    await session.flush()
    return tx


class TestDashboardNoData:
    """Tests for dashboard with no data (Requirement 9.6)."""

    async def test_no_data_returns_all_zeros(self, service, user_id):
        """When no data exists, all monetary values should be 0.00 and counts 0."""
        result = await service.get_overview(user_id)

        assert result.total_invested == Decimal("0.00")
        assert result.total_withdrawn == Decimal("0.00")
        assert result.net_invested == Decimal("0.00")
        assert result.total_market_value == Decimal("0.00")
        assert result.overall_pl == Decimal("0.00")
        assert result.overall_roi_percent == Decimal("0.00")
        assert result.total_positions == 0
        assert result.total_brokers == 0
        assert result.capital_per_broker == []
        assert result.market_data_complete is True


class TestDashboardTransferAggregations:
    """Tests for transfer-based calculations (Requirements 9.1, 9.4, 9.5)."""

    async def test_total_invested_sums_in_transfers(self, service, user_id, session):
        """Total Invested = sum of all 'In' transfer amounts."""
        await _create_transfer(session, user_id, "Webull", "In", "50000.00")
        await _create_transfer(session, user_id, "Dime", "In", "30000.00")
        await _create_transfer(session, user_id, "Webull", "Out", "10000.00")

        result = await service.get_overview(user_id)

        assert result.total_invested == Decimal("80000.00")

    async def test_total_withdrawn_sums_out_transfers(self, service, user_id, session):
        """Total Withdrawn = sum of all 'Out' transfer amounts."""
        await _create_transfer(session, user_id, "Webull", "In", "50000.00")
        await _create_transfer(session, user_id, "Webull", "Out", "10000.00")
        await _create_transfer(session, user_id, "Dime", "Out", "5000.50")

        result = await service.get_overview(user_id)

        assert result.total_withdrawn == Decimal("15000.50")

    async def test_net_invested_equals_in_minus_out(self, service, user_id, session):
        """Net Invested = Total In - Total Out."""
        await _create_transfer(session, user_id, "Webull", "In", "100000.00")
        await _create_transfer(session, user_id, "Webull", "Out", "25000.00")

        result = await service.get_overview(user_id)

        assert result.net_invested == Decimal("75000.00")

    async def test_capital_per_broker_breakdown(self, service, user_id, session):
        """Per-broker breakdown shows net capital (In - Out) per broker."""
        await _create_transfer(session, user_id, "Webull", "In", "50000.00")
        await _create_transfer(session, user_id, "Webull", "Out", "10000.00")
        await _create_transfer(session, user_id, "Dime", "In", "30000.00")

        result = await service.get_overview(user_id)

        assert result.total_brokers == 2
        broker_map = {b.broker: b for b in result.capital_per_broker}
        assert "Webull" in broker_map
        assert "Dime" in broker_map
        assert broker_map["Webull"].total_in == Decimal("50000.00")
        assert broker_map["Webull"].total_out == Decimal("10000.00")
        assert broker_map["Webull"].net_capital == Decimal("40000.00")
        assert broker_map["Dime"].total_in == Decimal("30000.00")
        assert broker_map["Dime"].total_out == Decimal("0.00")
        assert broker_map["Dime"].net_capital == Decimal("30000.00")

    async def test_total_brokers_counts_distinct_brokers(self, service, user_id, session):
        """Total brokers counts distinct broker names from transfers."""
        await _create_transfer(session, user_id, "Webull", "In", "10000.00")
        await _create_transfer(session, user_id, "Webull", "In", "20000.00")
        await _create_transfer(session, user_id, "Dime", "In", "10000.00")
        await _create_transfer(session, user_id, "Tiger", "Out", "5000.00")

        result = await service.get_overview(user_id)

        assert result.total_brokers == 3


class TestDashboardPositions:
    """Tests for position count (Requirement 9.5)."""

    async def test_total_positions_counts_held_stocks(self, service, user_id, session):
        """Total positions = stocks with qty > 0."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")
        await _create_transaction(session, user_id, "META", "Buy", 50, "20.00")
        # AAPL is sold to zero - should not count
        await _create_transaction(session, user_id, "AAPL", "Buy", 10, "150.00")
        await _create_transaction(session, user_id, "AAPL", "Sell", 10, "160.00")

        # Provide market data so market_data_complete = True
        market_data = {
            "DRAM": TickerInfo(symbol="DRAM", current_price=Decimal("12.00")),
            "META": TickerInfo(symbol="META", current_price=Decimal("25.00")),
        }

        result = await service.get_overview(user_id, market_data=market_data)

        assert result.total_positions == 2

    async def test_snapshot_positions_are_counted(self, service, user_id, session):
        """Snapshot entries contribute to held positions."""
        await _create_transaction(session, user_id, "RGNX", "Snapshot", 200, "15.00")

        market_data = {
            "RGNX": TickerInfo(symbol="RGNX", current_price=Decimal("18.00")),
        }

        result = await service.get_overview(user_id, market_data=market_data)

        assert result.total_positions == 1


class TestDashboardMarketValue:
    """Tests for market value, P/L, and ROI (Requirements 9.2, 9.3)."""

    async def test_total_market_value_with_complete_data(self, service, user_id, session):
        """Total MV = Σ(qty × current_price) when market data is complete."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")
        await _create_transaction(session, user_id, "META", "Buy", 50, "20.00")

        market_data = {
            "DRAM": TickerInfo(symbol="DRAM", current_price=Decimal("12.00")),
            "META": TickerInfo(symbol="META", current_price=Decimal("25.00")),
        }

        result = await service.get_overview(user_id, market_data=market_data)

        # DRAM: 100 × 12 = 1200, META: 50 × 25 = 1250 → Total MV = 2450
        assert result.total_market_value == Decimal("2450.00")
        assert result.market_data_complete is True

    async def test_overall_pl_calculation(self, service, user_id, session):
        """Overall P/L = Total MV - Total Cost."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")

        market_data = {
            "DRAM": TickerInfo(symbol="DRAM", current_price=Decimal("15.00")),
        }

        result = await service.get_overview(user_id, market_data=market_data)

        # Total cost = 100 × 10 = 1000, Total MV = 100 × 15 = 1500
        # P/L = 1500 - 1000 = 500
        assert result.overall_pl == Decimal("500.00")

    async def test_overall_roi_percent(self, service, user_id, session):
        """Overall ROI = (P/L / Total Cost) × 100."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")

        market_data = {
            "DRAM": TickerInfo(symbol="DRAM", current_price=Decimal("15.00")),
        }

        result = await service.get_overview(user_id, market_data=market_data)

        # P/L = 500, Total Cost = 1000 → ROI = (500/1000) × 100 = 50.00
        assert result.overall_roi_percent == Decimal("50.00")

    async def test_negative_pl_and_roi(self, service, user_id, session):
        """Negative P/L when market value < total cost."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")

        market_data = {
            "DRAM": TickerInfo(symbol="DRAM", current_price=Decimal("8.00")),
        }

        result = await service.get_overview(user_id, market_data=market_data)

        # Total cost = 1000, Total MV = 800
        # P/L = -200, ROI = -20.00%
        assert result.overall_pl == Decimal("-200.00")
        assert result.overall_roi_percent == Decimal("-20.00")


class TestDashboardIncompleteMarketData:
    """Tests for incomplete market data (Requirement 9.7)."""

    async def test_incomplete_market_data_shows_not_available(self, service, user_id, session):
        """When market data is incomplete, MV and P/L should be None."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")
        await _create_transaction(session, user_id, "META", "Buy", 50, "20.00")

        # Only provide data for DRAM, not META
        market_data = {
            "DRAM": TickerInfo(symbol="DRAM", current_price=Decimal("12.00")),
            "META": TickerInfo(symbol="META", current_price=None),  # incomplete
        }

        result = await service.get_overview(user_id, market_data=market_data)

        assert result.total_market_value is None
        assert result.overall_pl is None
        assert result.overall_roi_percent is None
        assert result.market_data_complete is False

    async def test_missing_ticker_info_marks_incomplete(self, service, user_id, session):
        """When ticker info is entirely missing for a symbol, mark as incomplete."""
        await _create_transaction(session, user_id, "DRAM", "Buy", 100, "10.00")

        # No market data provided and no market_data_service
        market_data = {}

        result = await service.get_overview(user_id, market_data=market_data)

        assert result.total_market_value is None
        assert result.overall_pl is None
        assert result.market_data_complete is False


class TestDashboardTransfersOnlyNoPositions:
    """Tests for having transfers but no positions."""

    async def test_transfers_only_no_positions(self, service, user_id, session):
        """When only transfers exist but no positions, MV is 0.00."""
        await _create_transfer(session, user_id, "Webull", "In", "100000.00")
        await _create_transfer(session, user_id, "Webull", "Out", "20000.00")

        result = await service.get_overview(user_id)

        assert result.total_invested == Decimal("100000.00")
        assert result.total_withdrawn == Decimal("20000.00")
        assert result.net_invested == Decimal("80000.00")
        assert result.total_market_value == Decimal("0.00")
        assert result.overall_pl == Decimal("0.00")
        assert result.overall_roi_percent == Decimal("0.00")
        assert result.total_positions == 0
        assert result.market_data_complete is True
