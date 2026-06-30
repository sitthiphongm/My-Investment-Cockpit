"""Property-based tests for per-user data isolation.

Property 24: Per-User Data Isolation
- Generate multi-user data sets, verify no cross-contamination in queries.
- For each user, querying their data returns ONLY their records.
- No other user's data appears in the results.
- The user_id filter is always applied.

**Validates: Requirements 27.1, 27.2, 27.3, 27.4**
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.models.user import User
from app.services.trading_service import TradingService
from app.services.transfer_service import TransferService
from app.schemas.transactions import TransactionFilters
from app.schemas.transfers import TransferFilters


# --- In-memory SQLite engine for testing ---

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def create_test_session() -> AsyncSession:
    """Create a fresh in-memory SQLite database session with all tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # SQLite needs this to support UUID columns stored as CHAR(32)
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    return session


# --- Hypothesis strategies ---

# Generate 2-5 unique user IDs
def user_ids_strategy(min_users=2, max_users=5):
    return st.integers(min_value=min_users, max_value=max_users).flatmap(
        lambda n: st.lists(st.uuids(), min_size=n, max_size=n, unique=True)
    )


# Generate a list of transactions for a given user
stock_symbols = st.sampled_from(["DRAM", "META", "AAPL", "TSLA", "GOOG", "NVDA", "AMZN"])
brokers = st.sampled_from(["Webull", "Dime", "SCB", "KBANK", "Bualuang"])
actions = st.sampled_from(["Buy", "Snapshot"])

transaction_strategy = st.fixed_dictionaries({
    "stock_symbol": stock_symbols,
    "action": actions,
    "quantity": st.integers(min_value=1, max_value=1000),
    "price_per_share": st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("9999.99"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    "broker": brokers,
    "date": st.dates(min_value=date(2020, 1, 1), max_value=date(2024, 12, 31)),
})

transfer_strategy = st.fixed_dictionaries({
    "broker": brokers,
    "transfer_type": st.sampled_from(["In", "Out"]),
    "amount": st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("999999.99"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    "date": st.dates(min_value=date(2020, 1, 1), max_value=date(2024, 12, 31)),
})


# Per-user data generation: each user gets 1-5 transactions and 1-3 transfers
per_user_data_strategy = st.fixed_dictionaries({
    "transactions": st.lists(transaction_strategy, min_size=1, max_size=5),
    "transfers": st.lists(transfer_strategy, min_size=1, max_size=3),
})


class TestPerUserDataIsolationProperty:
    """Property 24: Per-User Data Isolation.

    Generate multi-user data sets, verify no cross-contamination in queries.
    For each user, querying their data returns ONLY their records (no other user's data).

    **Validates: Requirements 27.1, 27.2, 27.3, 27.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        user_ids=user_ids_strategy(),
        data=st.data(),
    )
    async def test_transaction_queries_return_only_own_user_data(
        self,
        user_ids: list[uuid.UUID],
        data,
    ):
        """Querying transactions for a user returns ONLY that user's records.

        **Validates: Requirements 27.1, 27.2**
        """
        session = await create_test_session()
        try:
            # Generate per-user data
            user_data = {}
            for uid in user_ids:
                user_data[uid] = data.draw(per_user_data_strategy)

            # Insert transactions directly into the database for each user
            all_tx_ids = {}  # user_id -> list of tx ids
            for uid, udata in user_data.items():
                all_tx_ids[uid] = []
                for tx_data in udata["transactions"]:
                    gross_value = Decimal(tx_data["quantity"]) * tx_data["price_per_share"]
                    net_capital_flow = gross_value  # Simplified: no fees in test

                    tx = Transaction(
                        id=uuid.uuid4(),
                        user_id=uid,
                        date=tx_data["date"],
                        stock_symbol=tx_data["stock_symbol"],
                        action=tx_data["action"],
                        quantity=tx_data["quantity"],
                        price_per_share=tx_data["price_per_share"],
                        gross_value=gross_value,
                        brokerage_fee=Decimal("0"),
                        vat=Decimal("0"),
                        net_capital_flow=net_capital_flow,
                        broker=tx_data["broker"],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(tx)
                    all_tx_ids[uid].append(tx.id)

            await session.flush()

            # For each user, query via TradingService and verify isolation
            for uid in user_ids:
                service = TradingService(session)
                results = await service.list_transactions(uid)

                # Every returned transaction must belong to this user
                for tx in results:
                    assert tx.user_id == uid, (
                        f"Cross-contamination detected! User {uid} received "
                        f"transaction belonging to user {tx.user_id}"
                    )

                # Verify we got exactly the transactions for this user
                returned_ids = {tx.id for tx in results}
                expected_ids = set(all_tx_ids[uid])
                assert returned_ids == expected_ids, (
                    f"User {uid}: expected {len(expected_ids)} transactions, "
                    f"got {len(returned_ids)}. "
                    f"Missing: {expected_ids - returned_ids}, "
                    f"Extra: {returned_ids - expected_ids}"
                )
        finally:
            await session.close()

    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        user_ids=user_ids_strategy(),
        data=st.data(),
    )
    async def test_transfer_queries_return_only_own_user_data(
        self,
        user_ids: list[uuid.UUID],
        data,
    ):
        """Querying transfers for a user returns ONLY that user's records.

        **Validates: Requirements 27.1, 27.2**
        """
        session = await create_test_session()
        try:
            # Generate per-user data
            user_data = {}
            for uid in user_ids:
                user_data[uid] = data.draw(per_user_data_strategy)

            # Insert transfers directly into the database for each user
            all_transfer_ids = {}  # user_id -> list of transfer ids
            for uid, udata in user_data.items():
                all_transfer_ids[uid] = []
                for tr_data in udata["transfers"]:
                    transfer = Transfer(
                        id=uuid.uuid4(),
                        user_id=uid,
                        date=tr_data["date"],
                        broker=tr_data["broker"],
                        transfer_type=tr_data["transfer_type"],
                        amount=tr_data["amount"],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(transfer)
                    all_transfer_ids[uid].append(transfer.id)

            await session.flush()

            # For each user, query via TransferService and verify isolation
            for uid in user_ids:
                service = TransferService(session)
                filters = TransferFilters()
                results = await service.list_transfers(uid, filters)

                # Every returned transfer must belong to this user
                for tr in results:
                    assert tr.user_id == uid, (
                        f"Cross-contamination detected! User {uid} received "
                        f"transfer belonging to user {tr.user_id}"
                    )

                # Verify we got exactly the transfers for this user
                returned_ids = {tr.id for tr in results}
                expected_ids = set(all_transfer_ids[uid])
                assert returned_ids == expected_ids, (
                    f"User {uid}: expected {len(expected_ids)} transfers, "
                    f"got {len(returned_ids)}. "
                    f"Missing: {expected_ids - returned_ids}, "
                    f"Extra: {returned_ids - expected_ids}"
                )
        finally:
            await session.close()

    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        user_ids=user_ids_strategy(),
        data=st.data(),
    )
    async def test_user_cannot_see_other_users_transactions_via_filters(
        self,
        user_ids: list[uuid.UUID],
        data,
    ):
        """Even with filters applied, user_id isolation is maintained.

        **Validates: Requirements 27.3, 27.4**
        """
        session = await create_test_session()
        try:
            # Generate per-user data
            user_data = {}
            for uid in user_ids:
                user_data[uid] = data.draw(per_user_data_strategy)

            # Insert transactions
            for uid, udata in user_data.items():
                for tx_data in udata["transactions"]:
                    gross_value = Decimal(tx_data["quantity"]) * tx_data["price_per_share"]
                    tx = Transaction(
                        id=uuid.uuid4(),
                        user_id=uid,
                        date=tx_data["date"],
                        stock_symbol=tx_data["stock_symbol"],
                        action=tx_data["action"],
                        quantity=tx_data["quantity"],
                        price_per_share=tx_data["price_per_share"],
                        gross_value=gross_value,
                        brokerage_fee=Decimal("0"),
                        vat=Decimal("0"),
                        net_capital_flow=gross_value,
                        broker=tx_data["broker"],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(tx)

            await session.flush()

            # Collect all other users' data to verify non-leakage
            for uid in user_ids:
                other_user_symbols = set()
                other_user_brokers = set()
                for other_uid, udata in user_data.items():
                    if other_uid != uid:
                        for tx_data in udata["transactions"]:
                            other_user_symbols.add(tx_data["stock_symbol"])
                            other_user_brokers.add(tx_data["broker"])

                service = TradingService(session)

                # Query with various filters - user_id isolation must hold
                # Try filtering by a symbol that another user has
                for symbol in list(other_user_symbols)[:2]:
                    filters = TransactionFilters(stock_symbol=symbol)
                    results = await service.list_transactions(uid, filters)
                    for tx in results:
                        assert tx.user_id == uid, (
                            f"Cross-contamination via symbol filter! "
                            f"User {uid} received tx from user {tx.user_id} "
                            f"when filtering by symbol={symbol}"
                        )

                # Try filtering by a broker that another user has
                for broker in list(other_user_brokers)[:2]:
                    filters = TransactionFilters(broker=broker)
                    results = await service.list_transactions(uid, filters)
                    for tx in results:
                        assert tx.user_id == uid, (
                            f"Cross-contamination via broker filter! "
                            f"User {uid} received tx from user {tx.user_id} "
                            f"when filtering by broker={broker}"
                        )
        finally:
            await session.close()
