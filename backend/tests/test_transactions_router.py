"""Tests for the transactions API router."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_id
from main import app


# Helpers

def _make_user_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_transaction(user_id: uuid.UUID, **overrides):
    """Create a mock transaction-like object with all necessary attributes."""
    from unittest.mock import MagicMock

    defaults = dict(
        id=uuid.uuid4(),
        user_id=user_id,
        date=date(2024, 6, 15),
        stock_symbol="KBANK",
        action="Buy",
        quantity=100,
        price_per_share=Decimal("150.00"),
        gross_value=Decimal("15000.00"),
        brokerage_fee=Decimal("21.40"),
        vat=Decimal("1.50"),
        net_capital_flow=Decimal("15022.90"),
        broker="Bualuang",
        created_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        note=None,
        tags=[],
    )
    defaults.update(overrides)
    tx = MagicMock()
    for key, val in defaults.items():
        setattr(tx, key, val)
    return tx


@pytest.fixture
def user_id():
    return _make_user_id()


@pytest.fixture
def override_auth(user_id):
    """Override the get_current_user_id dependency with a fixed user_id."""
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


# Tests

@pytest.mark.asyncio
class TestCreateTransaction:
    async def test_unauthenticated_returns_401(self):
        """Requests without auth should return 401."""
        # Remove any overrides to test default behavior
        app.dependency_overrides.pop(get_current_user_id, None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/transactions", json={
                "date": "2024-06-15",
                "stock_symbol": "KBANK",
                "action": "Buy",
                "quantity": 100,
                "price_per_share": "150.00",
                "brokerage_fee": "21.40",
                "vat": "1.50",
                "broker": "Bualuang",
            })
            assert response.status_code == 401

    async def test_create_transaction_success(self, user_id, override_auth):
        """Authenticated POST /api/transactions should create a transaction."""
        tx = _make_transaction(user_id)

        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.create_transaction = AsyncMock(return_value=tx)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/transactions", json={
                    "date": "2024-06-15",
                    "stock_symbol": "KBANK",
                    "action": "Buy",
                    "quantity": 100,
                    "price_per_share": "150.00",
                    "brokerage_fee": "21.40",
                    "vat": "1.50",
                    "broker": "Bualuang",
                })

            assert response.status_code == 201
            data = response.json()
            assert data["stock_symbol"] == "KBANK"
            assert data["action"] == "Buy"
            assert data["quantity"] == 100


@pytest.mark.asyncio
class TestListTransactions:
    async def test_list_returns_transactions(self, user_id, override_auth):
        """GET /api/transactions returns a list of transactions."""
        tx1 = _make_transaction(user_id, stock_symbol="KBANK")
        tx2 = _make_transaction(user_id, stock_symbol="SCB")

        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.list_transactions = AsyncMock(return_value=[tx1, tx2])

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/transactions")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["stock_symbol"] == "KBANK"
            assert data[1]["stock_symbol"] == "SCB"

    async def test_list_with_filters(self, user_id, override_auth):
        """GET /api/transactions with query params passes filters to service."""
        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.list_transactions = AsyncMock(return_value=[])

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/transactions",
                    params={"symbol": "KBANK", "broker": "Bualuang", "action": "Buy"},
                )

            assert response.status_code == 200
            # Verify filters were passed to service
            call_args = mock_instance.list_transactions.call_args
            filters = call_args[0][1]
            assert filters.stock_symbol == "KBANK"
            assert filters.broker == "Bualuang"

    async def test_list_accepts_stock_symbol_alias(self, user_id, override_auth):
        """GET /api/transactions should also accept the stock_symbol alias."""
        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.list_transactions = AsyncMock(return_value=[])

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/transactions",
                    params={"stock_symbol": "AAPL", "broker": "Robinhood"},
                )

            assert response.status_code == 200
            call_args = mock_instance.list_transactions.call_args
            filters = call_args[0][1]
            assert filters.stock_symbol == "AAPL"
            assert filters.broker == "Robinhood"


@pytest.mark.asyncio
class TestEditTransaction:
    async def test_edit_transaction_success(self, user_id, override_auth):
        """PUT /api/transactions/{id} should update transaction."""
        tx_id = uuid.uuid4()
        tx = _make_transaction(user_id, id=tx_id, quantity=200)

        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.edit_transaction = AsyncMock(return_value=tx)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    f"/api/transactions/{tx_id}",
                    json={"quantity": 200},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["quantity"] == 200


@pytest.mark.asyncio
class TestDeleteTransaction:
    async def test_delete_transaction_success(self, user_id, override_auth):
        """DELETE /api/transactions/{id} should return 204."""
        tx_id = uuid.uuid4()

        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.delete_transaction = AsyncMock(return_value=None)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete(f"/api/transactions/{tx_id}")

            assert response.status_code == 204


@pytest.mark.asyncio
class TestImportSnapshot:
    async def test_import_snapshot_success(self, user_id, override_auth):
        """POST /api/transactions/snapshot should bulk import entries."""
        tx1 = _make_transaction(user_id, action="Snapshot", stock_symbol="KBANK")
        tx2 = _make_transaction(user_id, action="Snapshot", stock_symbol="SCB")

        with patch(
            "app.routers.transactions.TradingService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.import_snapshot = AsyncMock(return_value=[tx1, tx2])

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/transactions/snapshot", json={
                    "entries": [
                        {
                            "stock_symbol": "KBANK",
                            "quantity": 100,
                            "price_per_share": "150.00",
                            "broker": "Bualuang",
                        },
                        {
                            "stock_symbol": "SCB",
                            "quantity": 50,
                            "price_per_share": "120.00",
                            "broker": "Bualuang",
                        },
                    ]
                })

            assert response.status_code == 201
            data = response.json()
            assert len(data) == 2
            assert data[0]["action"] == "Snapshot"
