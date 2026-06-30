"""Unit tests for IdeasService."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.investment_idea import InvestmentIdea
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.enums import IdeaStatus, RiskLevel
from app.schemas.ideas import IdeaCreate, IdeaFilters, IdeaUpdate
from app.services.ideas_service import IdeasService


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
    """Create an IdeasService instance."""
    return IdeasService(session)


class TestCreateIdea:
    """Tests for IdeasService.create_idea."""

    async def test_create_idea_with_all_fields(self, service, user_id):
        """Create an idea with all fields populated."""
        data = IdeaCreate(
            stock_symbol="AAPL",
            title="Apple Growth Play",
            thesis="Strong services revenue growth",
            target_entry_price=Decimal("150.00"),
            risk_level=RiskLevel.MEDIUM,
            source_link="https://example.com/analysis",
            status=IdeaStatus.RESEARCHING,
        )

        result = await service.create_idea(user_id, data)

        assert result.id is not None
        assert result.user_id == user_id
        assert result.stock_symbol == "AAPL"
        assert result.title == "Apple Growth Play"
        assert result.thesis == "Strong services revenue growth"
        assert result.target_entry_price == Decimal("150.00")
        assert result.risk_level == "Medium"
        assert result.source_link == "https://example.com/analysis"
        assert result.status == "Researching"
        assert result.linked_transaction_id is None
        assert result.created_at is not None
        assert result.updated_at is not None

    async def test_create_idea_minimal_fields(self, service, user_id):
        """Create an idea with only required fields."""
        data = IdeaCreate(
            stock_symbol="TSLA",
            title="Tesla EV Thesis",
            risk_level=RiskLevel.HIGH,
        )

        result = await service.create_idea(user_id, data)

        assert result.stock_symbol == "TSLA"
        assert result.title == "Tesla EV Thesis"
        assert result.risk_level == "High"
        assert result.status == "Researching"  # default
        assert result.thesis is None
        assert result.target_entry_price is None
        assert result.source_link is None

    async def test_create_idea_symbol_uppercased(self, service, user_id):
        """Stock symbol is stored in uppercase."""
        data = IdeaCreate(
            stock_symbol="msft",
            title="Microsoft AI",
            risk_level=RiskLevel.LOW,
        )

        result = await service.create_idea(user_id, data)

        assert result.stock_symbol == "MSFT"


class TestListIdeas:
    """Tests for IdeasService.list_ideas."""

    async def test_list_empty(self, service, user_id):
        """List returns empty when no ideas exist."""
        ideas = await service.list_ideas(user_id)
        assert ideas == []

    async def test_list_returns_user_ideas_sorted_by_updated_at_desc(self, service, user_id):
        """List returns ideas sorted by updated_at descending (newest first)."""
        data1 = IdeaCreate(stock_symbol="AAPL", title="Idea 1", risk_level=RiskLevel.LOW)
        data2 = IdeaCreate(stock_symbol="TSLA", title="Idea 2", risk_level=RiskLevel.MEDIUM)
        data3 = IdeaCreate(stock_symbol="MSFT", title="Idea 3", risk_level=RiskLevel.HIGH)

        await service.create_idea(user_id, data1)
        await service.create_idea(user_id, data2)
        await service.create_idea(user_id, data3)

        ideas = await service.list_ideas(user_id)

        assert len(ideas) == 3
        # Most recently updated should be first
        assert ideas[0].stock_symbol == "MSFT"
        assert ideas[1].stock_symbol == "TSLA"
        assert ideas[2].stock_symbol == "AAPL"

    async def test_list_does_not_return_other_users_ideas(
        self, service, user_id, other_user_id, session
    ):
        """List only returns ideas for the requesting user."""
        data = IdeaCreate(stock_symbol="AAPL", title="My Idea", risk_level=RiskLevel.LOW)
        await service.create_idea(user_id, data)

        # Add idea for other user directly
        other_idea = InvestmentIdea(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            title="Their Idea",
            risk_level="Medium",
            status="Researching",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_idea)
        await session.flush()

        ideas = await service.list_ideas(user_id)

        assert len(ideas) == 1
        assert ideas[0].stock_symbol == "AAPL"

    async def test_list_filter_by_status(self, service, user_id):
        """Filter ideas by status."""
        data1 = IdeaCreate(stock_symbol="AAPL", title="Idea 1", risk_level=RiskLevel.LOW, status=IdeaStatus.RESEARCHING)
        data2 = IdeaCreate(stock_symbol="TSLA", title="Idea 2", risk_level=RiskLevel.MEDIUM, status=IdeaStatus.WATCHING)
        data3 = IdeaCreate(stock_symbol="MSFT", title="Idea 3", risk_level=RiskLevel.HIGH, status=IdeaStatus.RESEARCHING)

        await service.create_idea(user_id, data1)
        await service.create_idea(user_id, data2)
        await service.create_idea(user_id, data3)

        filters = IdeaFilters(status=IdeaStatus.RESEARCHING)
        ideas = await service.list_ideas(user_id, filters)

        assert len(ideas) == 2
        assert all(i.status == "Researching" for i in ideas)

    async def test_list_filter_by_risk_level(self, service, user_id):
        """Filter ideas by risk level."""
        data1 = IdeaCreate(stock_symbol="AAPL", title="Idea 1", risk_level=RiskLevel.LOW)
        data2 = IdeaCreate(stock_symbol="TSLA", title="Idea 2", risk_level=RiskLevel.HIGH)
        data3 = IdeaCreate(stock_symbol="MSFT", title="Idea 3", risk_level=RiskLevel.HIGH)

        await service.create_idea(user_id, data1)
        await service.create_idea(user_id, data2)
        await service.create_idea(user_id, data3)

        filters = IdeaFilters(risk_level=RiskLevel.HIGH)
        ideas = await service.list_ideas(user_id, filters)

        assert len(ideas) == 2
        assert all(i.risk_level == "High" for i in ideas)

    async def test_list_filter_by_symbol(self, service, user_id):
        """Filter ideas by stock symbol."""
        data1 = IdeaCreate(stock_symbol="AAPL", title="Idea 1", risk_level=RiskLevel.LOW)
        data2 = IdeaCreate(stock_symbol="TSLA", title="Idea 2", risk_level=RiskLevel.MEDIUM)
        data3 = IdeaCreate(stock_symbol="AAPL", title="Idea 3", risk_level=RiskLevel.HIGH)

        await service.create_idea(user_id, data1)
        await service.create_idea(user_id, data2)
        await service.create_idea(user_id, data3)

        filters = IdeaFilters(stock_symbol="AAPL")
        ideas = await service.list_ideas(user_id, filters)

        assert len(ideas) == 2
        assert all(i.stock_symbol == "AAPL" for i in ideas)

    async def test_list_combined_filters(self, service, user_id):
        """Filter ideas by multiple criteria (AND logic)."""
        data1 = IdeaCreate(stock_symbol="AAPL", title="Idea 1", risk_level=RiskLevel.HIGH, status=IdeaStatus.RESEARCHING)
        data2 = IdeaCreate(stock_symbol="AAPL", title="Idea 2", risk_level=RiskLevel.LOW, status=IdeaStatus.RESEARCHING)
        data3 = IdeaCreate(stock_symbol="TSLA", title="Idea 3", risk_level=RiskLevel.HIGH, status=IdeaStatus.RESEARCHING)

        await service.create_idea(user_id, data1)
        await service.create_idea(user_id, data2)
        await service.create_idea(user_id, data3)

        filters = IdeaFilters(stock_symbol="AAPL", risk_level=RiskLevel.HIGH)
        ideas = await service.list_ideas(user_id, filters)

        assert len(ideas) == 1
        assert ideas[0].title == "Idea 1"


class TestUpdateIdea:
    """Tests for IdeasService.update_idea."""

    async def test_update_title(self, service, user_id):
        """Update the title field."""
        data = IdeaCreate(stock_symbol="AAPL", title="Original", risk_level=RiskLevel.LOW)
        idea = await service.create_idea(user_id, data)

        update_data = IdeaUpdate(title="Updated Title")
        updated = await service.update_idea(user_id, idea.id, update_data)

        assert updated.title == "Updated Title"

    async def test_update_status(self, service, user_id):
        """Update the status field."""
        data = IdeaCreate(stock_symbol="AAPL", title="Test", risk_level=RiskLevel.LOW)
        idea = await service.create_idea(user_id, data)

        update_data = IdeaUpdate(status=IdeaStatus.WATCHING)
        updated = await service.update_idea(user_id, idea.id, update_data)

        assert updated.status == "Watching"

    async def test_update_link_transaction_when_bought(self, service, user_id, session):
        """Can link a transaction_id when status is Bought."""
        data = IdeaCreate(stock_symbol="AAPL", title="Test", risk_level=RiskLevel.LOW)
        idea = await service.create_idea(user_id, data)

        tx_id = uuid.uuid4()
        # Create a transaction to link to
        tx = Transaction(
            id=tx_id,
            user_id=user_id,
            date=datetime.utcnow().date(),
            stock_symbol="AAPL",
            action="Buy",
            quantity=100,
            price_per_share=Decimal("150.00"),
            gross_value=Decimal("15000.00"),
            brokerage_fee=Decimal("22.50"),
            vat=Decimal("1.58"),
            net_capital_flow=Decimal("15024.08"),
            broker="Webull",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(tx)
        await session.flush()

        update_data = IdeaUpdate(
            status=IdeaStatus.BOUGHT,
            linked_transaction_id=str(tx_id),
        )
        updated = await service.update_idea(user_id, idea.id, update_data)

        assert updated.status == "Bought"
        assert updated.linked_transaction_id == tx_id

    async def test_update_link_transaction_without_bought_status_raises_400(self, service, user_id):
        """Cannot link a transaction_id when status is not Bought."""
        data = IdeaCreate(stock_symbol="AAPL", title="Test", risk_level=RiskLevel.LOW)
        idea = await service.create_idea(user_id, data)

        update_data = IdeaUpdate(
            linked_transaction_id=str(uuid.uuid4()),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.update_idea(user_id, idea.id, update_data)

        assert exc_info.value.status_code == 400
        assert "linked_transaction_id" in exc_info.value.detail

    async def test_update_nonexistent_raises_404(self, service, user_id):
        """Update a non-existent idea raises 404."""
        fake_id = uuid.uuid4()
        update_data = IdeaUpdate(title="test")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_idea(user_id, fake_id, update_data)

        assert exc_info.value.status_code == 404

    async def test_update_other_users_idea_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot update another user's idea."""
        other_idea = InvestmentIdea(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            title="Their Idea",
            risk_level="High",
            status="Researching",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_idea)
        await session.flush()

        update_data = IdeaUpdate(title="Hacked")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_idea(user_id, other_idea.id, update_data)

        assert exc_info.value.status_code == 404

    async def test_update_multiple_fields(self, service, user_id):
        """Update multiple fields at once."""
        data = IdeaCreate(
            stock_symbol="AAPL",
            title="Original",
            thesis="Old thesis",
            risk_level=RiskLevel.LOW,
            target_entry_price=Decimal("100.00"),
        )
        idea = await service.create_idea(user_id, data)

        update_data = IdeaUpdate(
            title="New Title",
            thesis="New thesis",
            risk_level=RiskLevel.HIGH,
            target_entry_price=Decimal("120.00"),
            source_link="https://new-source.com",
        )
        updated = await service.update_idea(user_id, idea.id, update_data)

        assert updated.title == "New Title"
        assert updated.thesis == "New thesis"
        assert updated.risk_level == "High"
        assert updated.target_entry_price == Decimal("120.00")
        assert updated.source_link == "https://new-source.com"


class TestDeleteIdea:
    """Tests for IdeasService.delete_idea."""

    async def test_delete_removes_idea(self, service, user_id):
        """Delete removes the idea."""
        data = IdeaCreate(stock_symbol="AAPL", title="Test", risk_level=RiskLevel.LOW)
        idea = await service.create_idea(user_id, data)

        await service.delete_idea(user_id, idea.id)

        ideas = await service.list_ideas(user_id)
        assert len(ideas) == 0

    async def test_delete_nonexistent_raises_404(self, service, user_id):
        """Delete a non-existent idea raises 404."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_idea(user_id, fake_id)

        assert exc_info.value.status_code == 404

    async def test_delete_other_users_idea_raises_404(
        self, service, user_id, other_user_id, session
    ):
        """Cannot delete another user's idea."""
        other_idea = InvestmentIdea(
            id=uuid.uuid4(),
            user_id=other_user_id,
            stock_symbol="TSLA",
            title="Their Idea",
            risk_level="Medium",
            status="Researching",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(other_idea)
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_idea(user_id, other_idea.id)

        assert exc_info.value.status_code == 404
