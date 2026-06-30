"""Unit tests for TagService."""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.stock_tag_assignment import StockTagAssignment
from app.models.tag import Tag
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.tags import StockTagsUpdate, TagCreate
from app.services.tag_service import TagService


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
    """Create a TagService instance."""
    return TagService(session)


class TestCreateTag:
    """Tests for TagService.create_tag."""

    async def test_create_tag_success(self, service, user_id):
        """Create a tag with a valid name."""
        data = TagCreate(name="Growth")
        tag = await service.create_tag(user_id, data)

        assert tag.id is not None
        assert tag.user_id == user_id
        assert tag.name == "Growth"
        assert tag.created_at is not None

    async def test_create_tag_strips_whitespace(self, service, user_id):
        """Tag name is stripped of leading/trailing whitespace."""
        data = TagCreate(name="  Dividend  ")
        tag = await service.create_tag(user_id, data)

        assert tag.name == "Dividend"

    async def test_create_duplicate_tag_case_insensitive_raises_409(self, service, user_id):
        """Cannot create tag with same name (case-insensitive)."""
        data1 = TagCreate(name="Growth")
        await service.create_tag(user_id, data1)

        data2 = TagCreate(name="growth")
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tag(user_id, data2)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail

    async def test_create_duplicate_tag_mixed_case_raises_409(self, service, user_id):
        """Case-insensitive check works for mixed case."""
        data1 = TagCreate(name="Tech Stock")
        await service.create_tag(user_id, data1)

        data2 = TagCreate(name="TECH STOCK")
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tag(user_id, data2)

        assert exc_info.value.status_code == 409

    async def test_different_users_can_have_same_tag_name(
        self, service, user_id, other_user_id, session
    ):
        """Different users can create tags with the same name."""
        data = TagCreate(name="Growth")
        await service.create_tag(user_id, data)

        other_service = TagService(session)
        tag = await other_service.create_tag(other_user_id, data)
        assert tag.name == "Growth"
        assert tag.user_id == other_user_id


class TestListTags:
    """Tests for TagService.list_tags."""

    async def test_list_empty(self, service, user_id):
        """List returns empty when no tags exist."""
        tags = await service.list_tags(user_id)
        assert tags == []

    async def test_list_returns_user_tags_sorted_by_name(self, service, user_id):
        """List returns tags sorted alphabetically by name."""
        await service.create_tag(user_id, TagCreate(name="Zzz"))
        await service.create_tag(user_id, TagCreate(name="Aaa"))
        await service.create_tag(user_id, TagCreate(name="Mmm"))

        tags = await service.list_tags(user_id)

        assert len(tags) == 3
        assert tags[0].name == "Aaa"
        assert tags[1].name == "Mmm"
        assert tags[2].name == "Zzz"

    async def test_list_does_not_return_other_users_tags(
        self, service, user_id, other_user_id, session
    ):
        """List only returns tags for the requesting user."""
        await service.create_tag(user_id, TagCreate(name="MyTag"))

        other_service = TagService(session)
        await other_service.create_tag(other_user_id, TagCreate(name="TheirTag"))

        tags = await service.list_tags(user_id)
        assert len(tags) == 1
        assert tags[0].name == "MyTag"


class TestDeleteTag:
    """Tests for TagService.delete_tag."""

    async def test_delete_tag_removes_it(self, service, user_id):
        """Delete removes the tag."""
        tag = await service.create_tag(user_id, TagCreate(name="ToDelete"))
        await service.delete_tag(user_id, tag.id)

        tags = await service.list_tags(user_id)
        assert len(tags) == 0

    async def test_delete_tag_removes_stock_assignments(self, service, user_id, session):
        """Deleting a tag removes all its stock assignments."""
        tag = await service.create_tag(user_id, TagCreate(name="Growth"))

        # Assign tag to a stock
        data = StockTagsUpdate(tag_ids=[str(tag.id)])
        await service.assign_tags_to_stock(user_id, "AAPL", data)

        # Delete the tag
        await service.delete_tag(user_id, tag.id)

        # Verify assignments are gone
        from sqlalchemy import select

        stmt = select(StockTagAssignment).where(
            StockTagAssignment.user_id == user_id
        )
        result = await session.execute(stmt)
        assignments = result.scalars().all()
        assert len(list(assignments)) == 0

    async def test_delete_nonexistent_raises_404(self, service, user_id):
        """Delete a non-existent tag raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_tag(user_id, uuid.uuid4())

        assert exc_info.value.status_code == 404

    async def test_delete_other_users_tag_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot delete another user's tag."""
        other_service = TagService(session)
        tag = await other_service.create_tag(other_user_id, TagCreate(name="OtherTag"))

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_tag(user_id, tag.id)

        assert exc_info.value.status_code == 404


class TestAssignTagsToStock:
    """Tests for TagService.assign_tags_to_stock."""

    async def test_assign_single_tag(self, service, user_id):
        """Assign a single tag to a stock."""
        tag = await service.create_tag(user_id, TagCreate(name="Growth"))
        data = StockTagsUpdate(tag_ids=[str(tag.id)])

        result = await service.assign_tags_to_stock(user_id, "AAPL", data)

        assert result == ["Growth"]

    async def test_assign_multiple_tags(self, service, user_id):
        """Assign multiple tags to a stock."""
        tag1 = await service.create_tag(user_id, TagCreate(name="Growth"))
        tag2 = await service.create_tag(user_id, TagCreate(name="Tech"))
        data = StockTagsUpdate(tag_ids=[str(tag1.id), str(tag2.id)])

        result = await service.assign_tags_to_stock(user_id, "AAPL", data)

        assert sorted(result) == ["Growth", "Tech"]

    async def test_assign_replaces_existing_tags(self, service, user_id):
        """Assigning tags replaces all existing assignments for that stock."""
        tag1 = await service.create_tag(user_id, TagCreate(name="Growth"))
        tag2 = await service.create_tag(user_id, TagCreate(name="Tech"))
        tag3 = await service.create_tag(user_id, TagCreate(name="Dividend"))

        # First assignment
        data1 = StockTagsUpdate(tag_ids=[str(tag1.id), str(tag2.id)])
        await service.assign_tags_to_stock(user_id, "AAPL", data1)

        # Replace with different tag
        data2 = StockTagsUpdate(tag_ids=[str(tag3.id)])
        result = await service.assign_tags_to_stock(user_id, "AAPL", data2)

        assert result == ["Dividend"]

        # Verify via get_stocks_by_tag
        response = await service.get_stocks_by_tag(user_id, tag3.id)
        assert "AAPL" in response.stocks

        # Old tag should not have AAPL
        response1 = await service.get_stocks_by_tag(user_id, tag1.id)
        assert "AAPL" not in response1.stocks

    async def test_assign_empty_list_removes_all_tags(self, service, user_id):
        """Assigning empty list removes all tags from the stock."""
        tag = await service.create_tag(user_id, TagCreate(name="Growth"))
        data = StockTagsUpdate(tag_ids=[str(tag.id)])
        await service.assign_tags_to_stock(user_id, "AAPL", data)

        # Clear all tags
        data_empty = StockTagsUpdate(tag_ids=[])
        result = await service.assign_tags_to_stock(user_id, "AAPL", data_empty)

        assert result == []

    async def test_assign_uppercases_symbol(self, service, user_id):
        """Stock symbol is stored in uppercase."""
        tag = await service.create_tag(user_id, TagCreate(name="Growth"))
        data = StockTagsUpdate(tag_ids=[str(tag.id)])

        await service.assign_tags_to_stock(user_id, "aapl", data)

        response = await service.get_stocks_by_tag(user_id, tag.id)
        assert "AAPL" in response.stocks

    async def test_assign_invalid_tag_id_raises_400(self, service, user_id):
        """Invalid tag ID raises 400."""
        data = StockTagsUpdate(tag_ids=[str(uuid.uuid4())])

        with pytest.raises(HTTPException) as exc_info:
            await service.assign_tags_to_stock(user_id, "AAPL", data)

        assert exc_info.value.status_code == 400
        assert "not found" in exc_info.value.detail

    async def test_assign_other_users_tag_raises_400(
        self, service, user_id, other_user_id, session
    ):
        """Cannot assign another user's tag to a stock."""
        other_service = TagService(session)
        other_tag = await other_service.create_tag(other_user_id, TagCreate(name="OtherTag"))

        data = StockTagsUpdate(tag_ids=[str(other_tag.id)])

        with pytest.raises(HTTPException) as exc_info:
            await service.assign_tags_to_stock(user_id, "AAPL", data)

        assert exc_info.value.status_code == 400


class TestGetStocksByTag:
    """Tests for TagService.get_stocks_by_tag."""

    async def test_get_stocks_with_tag(self, service, user_id):
        """Get stocks assigned to a specific tag."""
        tag = await service.create_tag(user_id, TagCreate(name="Growth"))
        data = StockTagsUpdate(tag_ids=[str(tag.id)])

        await service.assign_tags_to_stock(user_id, "AAPL", data)
        await service.assign_tags_to_stock(user_id, "MSFT", data)

        response = await service.get_stocks_by_tag(user_id, tag.id)

        assert response.tag_id == str(tag.id)
        assert response.tag_name == "Growth"
        assert sorted(response.stocks) == ["AAPL", "MSFT"]

    async def test_get_stocks_empty_tag(self, service, user_id):
        """Tag with no stocks returns empty list."""
        tag = await service.create_tag(user_id, TagCreate(name="Empty"))

        response = await service.get_stocks_by_tag(user_id, tag.id)

        assert response.stocks == []

    async def test_get_stocks_nonexistent_tag_raises_404(self, service, user_id):
        """Non-existent tag raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            await service.get_stocks_by_tag(user_id, uuid.uuid4())

        assert exc_info.value.status_code == 404


class TestGetTagPerformance:
    """Tests for TagService.get_tag_performance."""

    async def test_performance_no_tags(self, service, user_id):
        """No tags returns empty performance list."""
        response = await service.get_tag_performance(user_id)
        assert response.tags == []

    async def test_performance_with_holdings_and_market_data(
        self, service, user_id, session
    ):
        """Performance calculation with holdings and market data."""
        # Create a tag
        tag = await service.create_tag(user_id, TagCreate(name="Tech"))

        # Create a buy transaction for AAPL
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 1, 15),
            stock_symbol="AAPL",
            action="Buy",
            quantity=10,
            price_per_share=Decimal("150.00"),
            gross_value=Decimal("1500.00"),
            brokerage_fee=Decimal("2.25"),
            vat=Decimal("0.16"),
            net_capital_flow=Decimal("1502.41"),
            broker="TestBroker",
        )
        session.add(tx)
        await session.flush()

        # Assign tag to AAPL
        data = StockTagsUpdate(tag_ids=[str(tag.id)])
        await service.assign_tags_to_stock(user_id, "AAPL", data)

        # Create mock market data
        class MockTickerInfo:
            current_price = Decimal("170.00")

        market_data = {"AAPL": MockTickerInfo()}

        response = await service.get_tag_performance(user_id, market_data)

        assert len(response.tags) == 1
        item = response.tags[0]
        assert item.tag_name == "Tech"
        assert item.total_cost == Decimal("1500.00")
        assert item.total_market_value == Decimal("1700.00")
        assert item.unrealized_pl == Decimal("200.00")
        assert item.roi_percent == Decimal("13.33")
        assert item.stock_count == 1

    async def test_performance_without_market_data(self, service, user_id, session):
        """Performance without market data returns None for MV fields."""
        tag = await service.create_tag(user_id, TagCreate(name="Tech"))

        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 1, 15),
            stock_symbol="AAPL",
            action="Buy",
            quantity=10,
            price_per_share=Decimal("150.00"),
            gross_value=Decimal("1500.00"),
            brokerage_fee=Decimal("2.25"),
            vat=Decimal("0.16"),
            net_capital_flow=Decimal("1502.41"),
            broker="TestBroker",
        )
        session.add(tx)
        await session.flush()

        data = StockTagsUpdate(tag_ids=[str(tag.id)])
        await service.assign_tags_to_stock(user_id, "AAPL", data)

        # No market data
        response = await service.get_tag_performance(user_id, market_data=None)

        assert len(response.tags) == 1
        item = response.tags[0]
        assert item.total_cost == Decimal("1500.00")
        assert item.total_market_value is None
        assert item.unrealized_pl is None
        assert item.roi_percent is None
        assert item.stock_count == 1

    async def test_performance_tag_with_no_holdings(self, service, user_id):
        """Tag with no stocks shows zero metrics."""
        await service.create_tag(user_id, TagCreate(name="Empty"))

        response = await service.get_tag_performance(user_id)

        assert len(response.tags) == 1
        item = response.tags[0]
        assert item.total_cost == Decimal("0.00")
        assert item.stock_count == 0

    async def test_performance_multiple_stocks_per_tag(
        self, service, user_id, session
    ):
        """Performance aggregates across multiple stocks in the same tag."""
        tag = await service.create_tag(user_id, TagCreate(name="Portfolio"))

        # AAPL: buy 10 @ 150
        tx1 = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 1, 15),
            stock_symbol="AAPL",
            action="Buy",
            quantity=10,
            price_per_share=Decimal("150.00"),
            gross_value=Decimal("1500.00"),
            brokerage_fee=Decimal("0"),
            vat=Decimal("0"),
            net_capital_flow=Decimal("1500.00"),
            broker="TestBroker",
        )
        # MSFT: buy 5 @ 300
        tx2 = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=date(2024, 1, 15),
            stock_symbol="MSFT",
            action="Buy",
            quantity=5,
            price_per_share=Decimal("300.00"),
            gross_value=Decimal("1500.00"),
            brokerage_fee=Decimal("0"),
            vat=Decimal("0"),
            net_capital_flow=Decimal("1500.00"),
            broker="TestBroker",
        )
        session.add(tx1)
        session.add(tx2)
        await session.flush()

        # Assign both to tag
        data = StockTagsUpdate(tag_ids=[str(tag.id)])
        await service.assign_tags_to_stock(user_id, "AAPL", data)
        await service.assign_tags_to_stock(user_id, "MSFT", data)

        class MockTickerInfo:
            def __init__(self, price):
                self.current_price = price

        market_data = {
            "AAPL": MockTickerInfo(Decimal("170.00")),
            "MSFT": MockTickerInfo(Decimal("350.00")),
        }

        response = await service.get_tag_performance(user_id, market_data)

        assert len(response.tags) == 1
        item = response.tags[0]
        # total_cost = 10*150 + 5*300 = 1500 + 1500 = 3000
        assert item.total_cost == Decimal("3000.00")
        # total_mv = 10*170 + 5*350 = 1700 + 1750 = 3450
        assert item.total_market_value == Decimal("3450.00")
        # unrealized_pl = 3450 - 3000 = 450
        assert item.unrealized_pl == Decimal("450.00")
        # roi = (450/3000)*100 = 15.00
        assert item.roi_percent == Decimal("15.00")
        assert item.stock_count == 2
