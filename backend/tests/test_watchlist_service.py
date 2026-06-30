"""Unit tests for WatchlistService."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemUpdate
from app.services.watchlist_service import WatchlistService


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
    """Create a WatchlistService instance."""
    return WatchlistService(session)


class TestAddItem:
    """Tests for WatchlistService.add_item."""

    async def test_add_item_with_all_fields(self, service, user_id):
        """Add a watchlist item with symbol, target price, and notes."""
        data = WatchlistItemCreate(
            stock_symbol="AAPL",
            interested_at_price=Decimal("150.00"),
            notes="Waiting for dip",
        )

        result = await service.add_item(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.stock_symbol == "AAPL"
        assert result.interested_at_price == Decimal("150.00")
        assert result.notes == "Waiting for dip"
        assert result.created_at is not None
        assert result.updated_at is not None

    async def test_add_item_symbol_only(self, service, user_id):
        """Add a watchlist item with only symbol (no target price, no notes)."""
        data = WatchlistItemCreate(stock_symbol="TSLA")

        result = await service.add_item(user_id, data)

        assert result.stock_symbol == "TSLA"
        assert result.interested_at_price is None
        assert result.notes is None

    async def test_add_item_symbol_uppercased(self, service, user_id):
        """Stock symbol is stored in uppercase."""
        data = WatchlistItemCreate(stock_symbol="msft")

        result = await service.add_item(user_id, data)

        assert result.stock_symbol == "MSFT"

    async def test_add_duplicate_symbol_raises_409(self, service, user_id):
        """Cannot add the same symbol twice."""
        data = WatchlistItemCreate(stock_symbol="AAPL")
        await service.add_item(user_id, data)

        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(user_id, data)

        assert exc_info.value.status_code == 409
        assert "already on your watchlist" in exc_info.value.detail

    async def test_add_same_symbol_different_users(self, service, user_id, other_user_id, session):
        """Different users can add the same symbol."""
        data = WatchlistItemCreate(stock_symbol="AAPL")
        await service.add_item(user_id, data)

        other_service = WatchlistService(session)
        result = await other_service.add_item(other_user_id, data)

        assert result.stock_symbol == "AAPL"
        assert result.user_id == other_user_id


class TestListItems:
    """Tests for WatchlistService.list_items."""

    async def test_list_empty(self, service, user_id):
        """List returns empty when no items exist."""
        items = await service.list_items(user_id)
        assert items == []

    async def test_list_returns_user_items_sorted_by_created_at_desc(self, service, user_id):
        """List returns items sorted by created_at descending (newest first)."""
        data1 = WatchlistItemCreate(stock_symbol="AAPL")
        data2 = WatchlistItemCreate(stock_symbol="TSLA")
        data3 = WatchlistItemCreate(stock_symbol="MSFT")

        await service.add_item(user_id, data1)
        await service.add_item(user_id, data2)
        await service.add_item(user_id, data3)

        items = await service.list_items(user_id)

        assert len(items) == 3
        # Most recently added should be first
        assert items[0].stock_symbol == "MSFT"
        assert items[1].stock_symbol == "TSLA"
        assert items[2].stock_symbol == "AAPL"

    async def test_list_does_not_return_other_users_items(
        self, service, user_id, other_user_id, session
    ):
        """List only returns items for the requesting user."""
        data = WatchlistItemCreate(stock_symbol="AAPL")
        await service.add_item(user_id, data)

        # Add item for other user
        other_item = WatchlistItem(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_item)
        await session.flush()

        items = await service.list_items(user_id)

        assert len(items) == 1
        assert items[0].stock_symbol == "AAPL"


class TestUpdateItem:
    """Tests for WatchlistService.update_item."""

    async def test_update_target_price(self, service, user_id):
        """Update the interested_at_price."""
        data = WatchlistItemCreate(
            stock_symbol="AAPL",
            interested_at_price=Decimal("150.00"),
        )
        item = await service.add_item(user_id, data)

        update_data = WatchlistItemUpdate(interested_at_price=Decimal("140.00"))
        updated = await service.update_item(user_id, item.id, update_data)

        assert updated.interested_at_price == Decimal("140.00")

    async def test_update_notes(self, service, user_id):
        """Update the notes field."""
        data = WatchlistItemCreate(stock_symbol="AAPL", notes="Original note")
        item = await service.add_item(user_id, data)

        update_data = WatchlistItemUpdate(notes="Updated note")
        updated = await service.update_item(user_id, item.id, update_data)

        assert updated.notes == "Updated note"

    async def test_update_both_fields(self, service, user_id):
        """Update both target price and notes."""
        data = WatchlistItemCreate(
            stock_symbol="AAPL",
            interested_at_price=Decimal("150.00"),
            notes="Old",
        )
        item = await service.add_item(user_id, data)

        update_data = WatchlistItemUpdate(
            interested_at_price=Decimal("130.00"),
            notes="New note",
        )
        updated = await service.update_item(user_id, item.id, update_data)

        assert updated.interested_at_price == Decimal("130.00")
        assert updated.notes == "New note"

    async def test_update_nonexistent_raises_404(self, service, user_id):
        """Update a non-existent item raises 404."""
        fake_id = uuid.uuid4()
        update_data = WatchlistItemUpdate(notes="test")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_item(user_id, fake_id, update_data)

        assert exc_info.value.status_code == 404

    async def test_update_other_users_item_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot update another user's watchlist item."""
        other_item = WatchlistItem(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            notes="Their note",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_item)
        await session.flush()

        update_data = WatchlistItemUpdate(notes="Hacked")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_item(user_id, other_item.id, update_data)

        assert exc_info.value.status_code == 404


class TestDeleteItem:
    """Tests for WatchlistService.delete_item."""

    async def test_delete_removes_item(self, service, user_id):
        """Delete removes the watchlist item."""
        data = WatchlistItemCreate(stock_symbol="AAPL")
        item = await service.add_item(user_id, data)

        await service.delete_item(user_id, item.id)

        items = await service.list_items(user_id)
        assert len(items) == 0

    async def test_delete_nonexistent_raises_404(self, service, user_id):
        """Delete a non-existent item raises 404."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_item(user_id, fake_id)

        assert exc_info.value.status_code == 404

    async def test_delete_other_users_item_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot delete another user's watchlist item."""
        other_item = WatchlistItem(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_item)
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_item(user_id, other_item.id)

        assert exc_info.value.status_code == 404


class TestIsAtTarget:
    """Tests for WatchlistService.is_at_target static method."""

    def test_at_target_when_price_equals_target(self):
        """At target when current price equals interested_at_price."""
        assert WatchlistService.is_at_target(
            Decimal("100.00"), Decimal("100.00")
        ) is True

    def test_at_target_when_price_below_target(self):
        """At target when current price is below interested_at_price."""
        assert WatchlistService.is_at_target(
            Decimal("100.00"), Decimal("95.00")
        ) is True

    def test_not_at_target_when_price_above_target(self):
        """Not at target when current price is above interested_at_price."""
        assert WatchlistService.is_at_target(
            Decimal("100.00"), Decimal("105.00")
        ) is False

    def test_not_at_target_when_no_interested_price(self):
        """Not at target when interested_at_price is None."""
        assert WatchlistService.is_at_target(None, Decimal("100.00")) is False

    def test_not_at_target_when_no_current_price(self):
        """Not at target when current_price is None."""
        assert WatchlistService.is_at_target(Decimal("100.00"), None) is False

    def test_not_at_target_when_both_none(self):
        """Not at target when both prices are None."""
        assert WatchlistService.is_at_target(None, None) is False
