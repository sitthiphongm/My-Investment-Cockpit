"""Integration tests for critical API flows.

Tests cover:
- Full transaction lifecycle: create → list → edit → delete
- Portfolio calculation with market data mocked
- Admin approval workflow
- Multi-user data isolation at API level
- Market data caching behavior

Requirements: 1.1–1.8, 5.1–5.10, 26.1–26.9, 27.1–27.6
"""

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.dependencies import get_current_active_user, get_current_user_id
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.models.user import User
from app.redis import get_redis
from app.schemas.market_data import TickerInfo
from main import app


# ============================================================================
# Fixtures for DB-backed integration tests
# ============================================================================


@pytest.fixture
async def engine():
    """Create an async SQLite in-memory engine for integration tests."""
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
async def session_factory(engine):
    """Provide a session factory for creating DB sessions."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    """Provide a test database session."""
    async with session_factory() as sess:
        yield sess


@pytest.fixture
async def user_a(session):
    """Create test user A and return it."""
    uid = uuid.uuid4()
    user = User(
        id=uid,
        display_name="User A",
        email="usera@test.com",
        oauth_provider="google",
        oauth_provider_id="google_a",
        status="Approved",
        is_admin=False,
        registered_at=datetime.utcnow(),
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def user_b(session):
    """Create test user B and return it."""
    uid = uuid.uuid4()
    user = User(
        id=uid,
        display_name="User B",
        email="userb@test.com",
        oauth_provider="google",
        oauth_provider_id="google_b",
        status="Approved",
        is_admin=False,
        registered_at=datetime.utcnow(),
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


# ============================================================================
# Test 1: Full Transaction Lifecycle (create → list → edit → delete)
# ============================================================================


@pytest.mark.asyncio
class TestTransactionLifecycle:
    """Test the full transaction lifecycle through the API layer."""

    async def test_full_lifecycle_create_list_edit_delete(
        self, session_factory, user_a, mock_redis
    ):
        """Create a transaction, verify it in list, edit it, verify changes, delete, verify gone."""

        # Override dependencies to use our test DB and user
        async def override_get_db():
            async with session_factory() as sess:
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise

        app.dependency_overrides[get_current_user_id] = lambda: user_a.id
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # --- STEP 1: Create a buy transaction ---
                create_payload = {
                    "date": "2024-06-15",
                    "stock_symbol": "KBANK",
                    "action": "Buy",
                    "quantity": 100,
                    "price_per_share": "150.00",
                    "brokerage_fee": "22.50",
                    "vat": "1.58",
                    "broker": "Bualuang",
                }
                resp = await client.post("/api/transactions", json=create_payload)
                assert resp.status_code == 201, f"Create failed: {resp.text}"
                created = resp.json()
                tx_id = created["id"]

                assert created["stock_symbol"] == "KBANK"
                assert created["action"] == "Buy"
                assert created["quantity"] == 100
                assert Decimal(created["price_per_share"]) == Decimal("150.00")
                assert Decimal(created["gross_value"]) == Decimal("15000.00")
                assert Decimal(created["brokerage_fee"]) == Decimal("22.50")
                assert Decimal(created["vat"]) == Decimal("1.58")
                # Net capital flow for buy: gross + fee + vat = 15000 + 22.50 + 1.58 = 15024.08
                assert Decimal(created["net_capital_flow"]) == Decimal("15024.08")

                # --- STEP 2: List and verify it exists ---
                resp = await client.get("/api/transactions")
                assert resp.status_code == 200
                items = resp.json()
                assert len(items) >= 1
                found = [tx for tx in items if tx["id"] == tx_id]
                assert len(found) == 1
                assert found[0]["stock_symbol"] == "KBANK"

                # --- STEP 3: Edit the transaction ---
                edit_payload = {
                    "quantity": 200,
                    "price_per_share": "155.00",
                }
                resp = await client.put(f"/api/transactions/{tx_id}", json=edit_payload)
                assert resp.status_code == 200, f"Edit failed: {resp.text}"
                edited = resp.json()
                assert edited["quantity"] == 200
                assert Decimal(edited["price_per_share"]) == Decimal("155.00")
                assert Decimal(edited["gross_value"]) == Decimal("31000.00")

                # --- STEP 4: Verify changes in listing ---
                resp = await client.get("/api/transactions")
                assert resp.status_code == 200
                items = resp.json()
                found = [tx for tx in items if tx["id"] == tx_id]
                assert len(found) == 1
                assert found[0]["quantity"] == 200
                assert Decimal(found[0]["price_per_share"]) == Decimal("155.00")

                # --- STEP 5: Delete the transaction ---
                resp = await client.delete(f"/api/transactions/{tx_id}")
                assert resp.status_code == 204

                # --- STEP 6: Verify it's gone ---
                resp = await client.get("/api/transactions")
                assert resp.status_code == 200
                items = resp.json()
                found = [tx for tx in items if tx["id"] == tx_id]
                assert len(found) == 0
        finally:
            app.dependency_overrides.pop(get_current_user_id, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)


# ============================================================================
# Test 2: Portfolio Calculation with Market Data Mocked
# ============================================================================


@pytest.mark.asyncio
class TestPortfolioWithMarketData:
    """Test portfolio summary with mocked market data."""

    async def test_portfolio_summary_with_market_data(
        self, session_factory, user_a, mock_redis
    ):
        """Portfolio returns calculated fields with market data merged."""

        # First, create some buy transactions in the DB
        async with session_factory() as sess:
            tx1 = Transaction(
                id=uuid.uuid4(),
                user_id=user_a.id,
                date=date(2024, 1, 10),
                stock_symbol="KBANK",
                action="Buy",
                quantity=100,
                price_per_share=Decimal("150.00"),
                gross_value=Decimal("15000.00"),
                brokerage_fee=Decimal("22.50"),
                vat=Decimal("1.58"),
                net_capital_flow=Decimal("15024.08"),
                broker="Bualuang",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            tx2 = Transaction(
                id=uuid.uuid4(),
                user_id=user_a.id,
                date=date(2024, 2, 15),
                stock_symbol="SCB",
                action="Buy",
                quantity=50,
                price_per_share=Decimal("120.00"),
                gross_value=Decimal("6000.00"),
                brokerage_fee=Decimal("9.00"),
                vat=Decimal("0.63"),
                net_capital_flow=Decimal("6009.63"),
                broker="Bualuang",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            sess.add_all([tx1, tx2])
            await sess.commit()

        # Override dependencies
        async def override_get_db():
            async with session_factory() as sess:
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise

        app.dependency_overrides[get_current_user_id] = lambda: user_a.id
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        # Mock market data service to return controlled prices
        kbank_ticker = TickerInfo(
            symbol="KBANK",
            current_price=Decimal("160.00"),
            company_name="Kasikornbank",
            sector="Financial Services",
        )
        scb_ticker = TickerInfo(
            symbol="SCB",
            current_price=Decimal("130.00"),
            company_name="Siam Commercial Bank",
            sector="Financial Services",
        )

        async def mock_get_ticker_info(symbol):
            tickers = {"KBANK": kbank_ticker, "SCB": scb_ticker}
            return tickers.get(symbol, TickerInfo(symbol=symbol))

        try:
            with patch(
                "app.routers.portfolio.MarketDataService"
            ) as MockMarketSvc:
                mock_market = MockMarketSvc.return_value
                mock_market.get_ticker_info = AsyncMock(side_effect=mock_get_ticker_info)

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/portfolio/summary")

                assert resp.status_code == 200
                data = resp.json()

                # Should have 2 positions
                positions = data["positions"]
                assert len(positions) == 2

                # Find KBANK position
                kbank_pos = next(p for p in positions if p["stock_symbol"] == "KBANK")
                assert kbank_pos["quantity"] == 100
                assert Decimal(kbank_pos["avg_cost"]) == Decimal("150.00")
                assert Decimal(kbank_pos["total_cost"]) == Decimal("15000.00")
                # Market value = 100 * 160 = 16000
                assert Decimal(kbank_pos["market_value"]) == Decimal("16000.00")
                # Unrealized P/L = 16000 - 15000 = 1000
                assert Decimal(kbank_pos["unrealized_pl"]) == Decimal("1000.00")

                # Find SCB position
                scb_pos = next(p for p in positions if p["stock_symbol"] == "SCB")
                assert scb_pos["quantity"] == 50
                assert Decimal(scb_pos["avg_cost"]) == Decimal("120.00")
                # Market value = 50 * 130 = 6500
                assert Decimal(scb_pos["market_value"]) == Decimal("6500.00")
        finally:
            app.dependency_overrides.pop(get_current_user_id, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)


# ============================================================================
# Test 3: Admin Approval Workflow
# ============================================================================


@pytest.mark.asyncio
class TestAdminApprovalWorkflow:
    """Test admin user management: approve and block users."""

    async def test_admin_approve_and_block_workflow(self, session_factory, mock_redis):
        """Admin can list users, approve pending users, and block them."""

        # Create admin user and pending user
        admin_id = uuid.uuid4()
        pending_id = uuid.uuid4()

        async with session_factory() as sess:
            admin_user = User(
                id=admin_id,
                display_name="Admin",
                email="admin@test.com",
                oauth_provider="google",
                oauth_provider_id="google_admin",
                status="Approved",
                is_admin=True,
                registered_at=datetime.utcnow(),
                last_login_at=datetime.utcnow(),
            )
            pending_user = User(
                id=pending_id,
                display_name="Pending User",
                email="pending@test.com",
                oauth_provider="facebook",
                oauth_provider_id="fb_pending",
                status="Pending",
                is_admin=False,
                registered_at=datetime.utcnow(),
                last_login_at=None,
            )
            sess.add_all([admin_user, pending_user])
            await sess.commit()

        # Override dependencies - admin needs a special auth override
        async def override_get_db():
            async with session_factory() as sess:
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Admin needs a session cookie. We'll mock the admin's auth.
                # The admin router uses its own get_current_admin_user dependency
                # which reads the session_token cookie directly.
                # We'll patch the AuthService.validate_session to return our admin.
                async with session_factory() as sess:
                    # Reload admin user for the mock
                    from sqlalchemy import select
                    result = await sess.execute(
                        select(User).where(User.id == admin_id)
                    )
                    admin_obj = result.scalar_one()

                with patch(
                    "app.routers.admin.AuthService"
                ) as MockAuthSvc:
                    mock_auth = MockAuthSvc.return_value
                    mock_auth.validate_session = AsyncMock(return_value=admin_obj)

                    # --- List users ---
                    resp = await client.get(
                        "/api/admin/users",
                        cookies={"session_token": "fake_admin_token"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["total"] >= 2

                    # --- Approve the pending user ---
                    resp = await client.post(
                        f"/api/admin/users/{pending_id}/approve",
                        cookies={"session_token": "fake_admin_token"},
                    )
                    assert resp.status_code == 200
                    approved = resp.json()
                    assert approved["status"] == "Approved"

                    # --- Block the user ---
                    resp = await client.post(
                        f"/api/admin/users/{pending_id}/block",
                        cookies={"session_token": "fake_admin_token"},
                    )
                    assert resp.status_code == 200
                    blocked = resp.json()
                    assert blocked["status"] == "Blocked"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)

    async def test_non_admin_cannot_access_admin_endpoints(
        self, session_factory, user_a, mock_redis
    ):
        """Non-admin users get 403 ACCESS_DENIED on admin endpoints."""

        async def override_get_db():
            async with session_factory() as sess:
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                with patch(
                    "app.routers.admin.AuthService"
                ) as MockAuthSvc:
                    mock_auth = MockAuthSvc.return_value
                    mock_auth.validate_session = AsyncMock(return_value=user_a)

                    resp = await client.get(
                        "/api/admin/users",
                        cookies={"session_token": "fake_user_token"},
                    )
                    assert resp.status_code == 403
                    assert resp.json()["detail"] == "ACCESS_DENIED"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)
            app.dependency_overrides.pop(get_current_user_id, None)


# ============================================================================
# Test 4: Multi-User Data Isolation at API Level
# ============================================================================


@pytest.mark.asyncio
class TestMultiUserDataIsolation:
    """Verify that user A cannot see user B's data through the API."""

    async def test_user_cannot_see_other_users_transactions(
        self, session_factory, user_a, user_b, mock_redis
    ):
        """User A's transactions are not visible to User B."""

        # Create a transaction for user A
        async with session_factory() as sess:
            tx = Transaction(
                id=uuid.uuid4(),
                user_id=user_a.id,
                date=date(2024, 3, 1),
                stock_symbol="PTT",
                action="Buy",
                quantity=500,
                price_per_share=Decimal("36.00"),
                gross_value=Decimal("18000.00"),
                brokerage_fee=Decimal("27.00"),
                vat=Decimal("1.89"),
                net_capital_flow=Decimal("18028.89"),
                broker="KTB",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            sess.add(tx)
            await sess.commit()

        async def override_get_db():
            async with session_factory() as sess:
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # User A should see their transaction
                app.dependency_overrides[get_current_user_id] = lambda: user_a.id
                resp = await client.get("/api/transactions")
                assert resp.status_code == 200
                user_a_txns = resp.json()
                assert len(user_a_txns) == 1
                assert user_a_txns[0]["stock_symbol"] == "PTT"

                # User B should NOT see user A's transaction
                app.dependency_overrides[get_current_user_id] = lambda: user_b.id
                resp = await client.get("/api/transactions")
                assert resp.status_code == 200
                user_b_txns = resp.json()
                assert len(user_b_txns) == 0
        finally:
            app.dependency_overrides.pop(get_current_user_id, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)

    async def test_user_cannot_see_other_users_transfers(
        self, session_factory, user_a, user_b, mock_redis
    ):
        """User A's transfers are not visible to User B."""

        # Create a transfer for user A
        async with session_factory() as sess:
            transfer = Transfer(
                id=uuid.uuid4(),
                user_id=user_a.id,
                date=date(2024, 4, 1),
                broker="Bualuang",
                transfer_type="In",
                amount=Decimal("100000.00"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            sess.add(transfer)
            await sess.commit()

        async def override_get_db():
            async with session_factory() as sess:
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise

        # The transfers router uses get_current_active_user instead of get_current_user_id
        # We need to mock it to return a User object
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # User A sees their transfer
                app.dependency_overrides[get_current_active_user] = lambda: user_a
                resp = await client.get("/api/transfers")
                assert resp.status_code == 200
                user_a_transfers = resp.json()
                assert len(user_a_transfers) == 1
                assert user_a_transfers[0]["broker"] == "Bualuang"

                # User B sees nothing
                app.dependency_overrides[get_current_active_user] = lambda: user_b
                resp = await client.get("/api/transfers")
                assert resp.status_code == 200
                user_b_transfers = resp.json()
                assert len(user_b_transfers) == 0
        finally:
            app.dependency_overrides.pop(get_current_active_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)


# ============================================================================
# Test 5: Market Data Caching Behavior
# ============================================================================


@pytest.mark.asyncio
class TestMarketDataCaching:
    """Test that market data caching uses Redis correctly."""

    async def test_cache_hit_returns_cached_data(self):
        """When Redis has fresh cached data, yfinance is not called."""
        from app.services.market_data_service import MarketDataService

        mock_redis = AsyncMock()

        # Simulate cached data in Redis (fresh cache, not stale)
        cached_ticker = json.dumps({
            "symbol": "KBANK",
            "current_price": "160.00",
            "company_name": "Kasikornbank",
            "sector": "Financial Services",
        })
        mock_redis.get = AsyncMock(return_value=cached_ticker)
        mock_redis.ttl = AsyncMock(return_value=1800)  # 30 min remaining = not stale

        service = MarketDataService(mock_redis)

        with patch.object(service, "_fetch_from_yfinance") as mock_fetch, \
             patch.object(service, "is_cache_stale", return_value=False):
            result = await service.get_ticker_info("KBANK")

            # yfinance should NOT be called because cache is fresh
            mock_fetch.assert_not_called()
            assert result.symbol == "KBANK"
            assert result.current_price == Decimal("160.00")

    async def test_cache_miss_fetches_from_yfinance(self):
        """When Redis has no cached data, the service fetches from yfinance."""
        from app.services.market_data_service import MarketDataService

        mock_redis = AsyncMock()
        # No cached data
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        service = MarketDataService(mock_redis)

        with patch.object(service, "_fetch_from_yfinance") as mock_fetch:
            mock_fetch.return_value = TickerInfo(
                symbol="KBANK",
                current_price=Decimal("160.00"),
                company_name="Kasikornbank",
            )

            result = await service.get_ticker_info("KBANK")

            # Should have fetched from yfinance
            mock_fetch.assert_called_once_with("KBANK")
            assert result.symbol == "KBANK"
            assert result.current_price == Decimal("160.00")

            # Should have cached the result
            mock_redis.set.assert_called_once()

    async def test_stale_cache_still_returns_data_on_fetch_failure(self):
        """When fetch fails, stale cached data is returned with staleness flag."""
        from app.services.market_data_service import MarketDataService, NetworkError

        mock_redis = AsyncMock()

        # Simulate stale cached data (TTL expired)
        cached_data = json.dumps({
            "symbol": "KBANK",
            "current_price": "155.00",
            "company_name": "Kasikornbank",
            "sector": "Financial Services",
        })
        mock_redis.get = AsyncMock(return_value=cached_data)
        mock_redis.ttl = AsyncMock(return_value=-1)  # Expired

        service = MarketDataService(mock_redis)

        with patch.object(service, "_fetch_from_yfinance") as mock_fetch, \
             patch.object(service, "is_cache_stale", return_value=True):
            mock_fetch.side_effect = NetworkError("Connection timeout")

            result = await service.get_ticker_info("KBANK")

            # Should return stale data with is_stale flag
            assert result.symbol == "KBANK"
            assert result.is_stale is True
