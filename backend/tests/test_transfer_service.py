"""Unit tests for TransferService."""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.transfer import Transfer
from app.models.user import User
from app.schemas.transfers import TransferCreate, TransferFilters, TransferUpdate
from app.schemas.enums import TransferType
from app.services.transfer_service import TransferService


@pytest.fixture
async def engine():
    """Create an async SQLite engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Enable foreign key support for SQLite
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
    """Create a TransferService instance."""
    return TransferService(session)


class TestCreateTransfer:
    """Tests for TransferService.create_transfer."""

    async def test_create_transfer_persists_correctly(self, service, user_id, session):
        """Create persists all fields correctly."""
        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("50000.00"),
        )

        result = await service.create_transfer(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.date == date(2024, 6, 15)
        assert result.broker == "Webull"
        assert result.transfer_type == "In"
        assert result.amount == Decimal("50000.00")
        assert result.created_at is not None
        assert result.updated_at is not None

    async def test_create_transfer_out_type(self, service, user_id):
        """Create transfer with Out type persists correctly."""
        data = TransferCreate(
            date=date(2024, 3, 10),
            broker="Dime",
            transfer_type=TransferType.OUT,
            amount=Decimal("10000.50"),
        )

        result = await service.create_transfer(user_id, data)

        assert result.transfer_type == "Out"
        assert result.amount == Decimal("10000.50")
        assert result.broker == "Dime"


class TestEditTransfer:
    """Tests for TransferService.edit_transfer."""

    async def test_edit_merges_fields_properly(self, service, user_id):
        """Edit only updates non-None fields, preserving others."""
        # Create a transfer first
        create_data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("50000.00"),
        )
        transfer = await service.create_transfer(user_id, create_data)

        # Edit only the amount
        update_data = TransferUpdate(amount=Decimal("75000.00"))
        result = await service.edit_transfer(user_id, transfer.id, update_data)

        # Amount should be updated
        assert result.amount == Decimal("75000.00")
        # Other fields should be preserved
        assert result.date == date(2024, 6, 15)
        assert result.broker == "Webull"
        assert result.transfer_type == "In"

    async def test_edit_transfer_type(self, service, user_id):
        """Edit transfer type updates correctly."""
        create_data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("50000.00"),
        )
        transfer = await service.create_transfer(user_id, create_data)

        update_data = TransferUpdate(transfer_type=TransferType.OUT)
        result = await service.edit_transfer(user_id, transfer.id, update_data)

        assert result.transfer_type == "Out"

    async def test_edit_multiple_fields(self, service, user_id):
        """Edit multiple fields at once."""
        create_data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("50000.00"),
        )
        transfer = await service.create_transfer(user_id, create_data)

        update_data = TransferUpdate(
            broker="Dime",
            amount=Decimal("100000.00"),
            date=date(2024, 7, 1),
        )
        result = await service.edit_transfer(user_id, transfer.id, update_data)

        assert result.broker == "Dime"
        assert result.amount == Decimal("100000.00")
        assert result.date == date(2024, 7, 1)
        assert result.transfer_type == "In"  # preserved

    async def test_edit_not_found_raises_404(self, service, user_id):
        """Edit a non-existent transfer raises 404."""
        fake_id = uuid.uuid4()
        update_data = TransferUpdate(amount=Decimal("1000.00"))

        with pytest.raises(HTTPException) as exc_info:
            await service.edit_transfer(user_id, fake_id, update_data)

        assert exc_info.value.status_code == 404


class TestDeleteTransfer:
    """Tests for TransferService.delete_transfer."""

    async def test_delete_removes_record(self, service, user_id, session):
        """Delete removes the transfer record."""
        create_data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("50000.00"),
        )
        transfer = await service.create_transfer(user_id, create_data)
        transfer_id = transfer.id

        await service.delete_transfer(user_id, transfer_id)

        # Verify the record is gone
        with pytest.raises(HTTPException) as exc_info:
            await service._get_transfer_or_404(user_id, transfer_id)
        assert exc_info.value.status_code == 404

    async def test_delete_not_found_raises_404(self, service, user_id):
        """Delete a non-existent transfer raises 404."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_transfer(user_id, fake_id)

        assert exc_info.value.status_code == 404


class TestListTransfers:
    """Tests for TransferService.list_transfers."""

    async def test_list_returns_sorted_by_date_desc(self, service, user_id):
        """List returns results sorted by date descending."""
        dates = [date(2024, 1, 10), date(2024, 6, 20), date(2024, 3, 15)]
        for d in dates:
            data = TransferCreate(
                date=d,
                broker="Webull",
                transfer_type=TransferType.IN,
                amount=Decimal("10000.00"),
            )
            await service.create_transfer(user_id, data)

        filters = TransferFilters()
        results = await service.list_transfers(user_id, filters)

        assert len(results) == 3
        assert results[0].date == date(2024, 6, 20)
        assert results[1].date == date(2024, 3, 15)
        assert results[2].date == date(2024, 1, 10)

    async def test_list_empty_returns_empty_list(self, service, user_id):
        """List returns empty list when no records exist."""
        filters = TransferFilters()
        results = await service.list_transfers(user_id, filters)

        assert results == []

    async def test_broker_filter_case_insensitive(self, service, user_id):
        """Broker filter matches case-insensitively."""
        # Create transfers with different brokers
        for broker in ["Webull", "Dime", "webull"]:
            data = TransferCreate(
                date=date(2024, 6, 15),
                broker=broker,
                transfer_type=TransferType.IN,
                amount=Decimal("10000.00"),
            )
            await service.create_transfer(user_id, data)

        # Filter by "webull" (lowercase) should match both "Webull" and "webull"
        filters = TransferFilters(broker="webull")
        results = await service.list_transfers(user_id, filters)

        assert len(results) == 2
        for r in results:
            assert r.broker.lower() == "webull"

    async def test_broker_filter_uppercase_matches(self, service, user_id):
        """Broker filter with uppercase matches lowercase records."""
        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="dime",
            transfer_type=TransferType.OUT,
            amount=Decimal("5000.00"),
        )
        await service.create_transfer(user_id, data)

        filters = TransferFilters(broker="DIME")
        results = await service.list_transfers(user_id, filters)

        assert len(results) == 1
        assert results[0].broker == "dime"

    async def test_list_does_not_return_other_users_records(self, service, session, user_id):
        """List only returns records belonging to the requesting user."""
        # Create a transfer for the test user
        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("10000.00"),
        )
        await service.create_transfer(user_id, data)

        # Create another user and their transfer
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

        other_transfer = Transfer(
            id=uuid.uuid4(),
            user_id=other_user_id,
            date=date(2024, 6, 15),
            broker="Dime",
            transfer_type="Out",
            amount=Decimal("5000.00"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_transfer)
        await session.flush()

        # List should only show the first user's transfer
        filters = TransferFilters()
        results = await service.list_transfers(user_id, filters)

        assert len(results) == 1
        assert results[0].user_id == user_id


class TestFXConversion:
    """Tests for FX conversion logic in TransferService."""

    async def test_create_usd_transfer_sets_fx_fields(self, service, user_id):
        """USD transfer sets fx_rate=1.0, converted_usd_amount=amount."""
        from app.schemas.enums import Currency

        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("10000.00"),
            original_currency=Currency.USD,
        )

        result = await service.create_transfer(user_id, data)

        assert result.original_currency == "USD"
        assert result.original_amount == Decimal("10000.00")
        assert result.fx_rate == Decimal("1.0")
        assert result.converted_usd_amount == Decimal("10000.00")
        assert result.amount == Decimal("10000.00")
        assert result.fx_provider == "manual"
        assert result.fx_fetch_timestamp is not None

    async def test_create_thb_transfer_calculates_conversion(self, service, user_id):
        """THB transfer calculates converted_usd_amount = original_amount / fx_rate."""
        from app.schemas.enums import Currency

        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("1000.00"),  # This gets overridden by the FX calculation
            original_currency=Currency.THB,
            original_amount=Decimal("350000.00"),
            fx_rate=Decimal("35.00"),
        )

        result = await service.create_transfer(user_id, data)

        assert result.original_currency == "THB"
        assert result.original_amount == Decimal("350000.00")
        assert result.fx_rate == Decimal("35.00")
        assert result.converted_usd_amount == Decimal("10000.00")
        # amount field set to USD equivalent for backward compat
        assert result.amount == Decimal("10000.00")
        assert result.fx_provider == "manual"

    async def test_create_thb_transfer_with_fx_fee(self, service, user_id):
        """THB transfer with fx_fee stores fee correctly."""
        from app.schemas.enums import Currency

        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("1000.00"),
            original_currency=Currency.THB,
            original_amount=Decimal("350000.00"),
            fx_rate=Decimal("35.00"),
            fx_fee=Decimal("150.00"),
            note="Transfer from Bangkok Bank",
        )

        result = await service.create_transfer(user_id, data)

        assert result.fx_fee == Decimal("150.00")
        assert result.note == "Transfer from Bangkok Bank"

    async def test_create_usd_transfer_default_currency(self, service, user_id):
        """Transfer without specifying currency defaults to USD."""
        data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("5000.00"),
        )

        result = await service.create_transfer(user_id, data)

        assert result.original_currency == "USD"
        assert result.fx_rate == Decimal("1.0")
        assert result.converted_usd_amount == Decimal("5000.00")
        assert result.amount == Decimal("5000.00")

    async def test_edit_fx_fields_recalculates_converted_amount(self, service, user_id):
        """Editing FX fields recalculates converted_usd_amount."""
        from app.schemas.enums import Currency

        # Create a THB transfer
        create_data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("1000.00"),
            original_currency=Currency.THB,
            original_amount=Decimal("350000.00"),
            fx_rate=Decimal("35.00"),
        )
        transfer = await service.create_transfer(user_id, create_data)
        assert transfer.converted_usd_amount == Decimal("10000.00")

        # Edit the FX rate
        update_data = TransferUpdate(fx_rate=Decimal("34.00"))
        result = await service.edit_transfer(user_id, transfer.id, update_data)

        # Recalculated: 350000 / 34 = 10294.12 (rounded)
        expected = (Decimal("350000.00") / Decimal("34.00")).quantize(Decimal("0.01"))
        assert result.converted_usd_amount == expected
        assert result.amount == expected

    async def test_edit_currency_to_usd_resets_fx_rate(self, service, user_id):
        """Changing currency to USD sets fx_rate=1.0 and converted=original."""
        from app.schemas.enums import Currency

        # Create a THB transfer
        create_data = TransferCreate(
            date=date(2024, 6, 15),
            broker="Webull",
            transfer_type=TransferType.IN,
            amount=Decimal("1000.00"),
            original_currency=Currency.THB,
            original_amount=Decimal("350000.00"),
            fx_rate=Decimal("35.00"),
        )
        transfer = await service.create_transfer(user_id, create_data)

        # Change to USD
        update_data = TransferUpdate(original_currency=Currency.USD)
        result = await service.edit_transfer(user_id, transfer.id, update_data)

        assert result.original_currency == "USD"
        assert result.fx_rate == Decimal("1.0")
        # converted_usd_amount should equal original_amount
        assert result.converted_usd_amount == Decimal("350000.00")
        assert result.amount == Decimal("350000.00")

