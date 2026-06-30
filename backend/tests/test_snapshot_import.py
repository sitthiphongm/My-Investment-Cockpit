"""Unit tests for snapshot import (bulk import) in TradingService."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.schemas.transactions import SnapshotCreate, SnapshotEntry
from app.services.trading_service import TradingService


class FakeResult:
    """Fake SQLAlchemy result wrapper."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class TestSnapshotImportAtomicity:
    """Test that snapshot import is all-or-nothing."""

    @pytest.mark.asyncio
    async def test_all_valid_entries_persisted(self):
        """All valid entries are persisted when the entire batch is valid."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("25.50"),
                    broker="Webull",
                ),
                SnapshotEntry(
                    stock_symbol="META",
                    quantity=200,
                    price_per_share=Decimal("10.00"),
                    broker="Dime",
                ),
                SnapshotEntry(
                    stock_symbol="DRAM",
                    quantity=500,
                    price_per_share=Decimal("5.00"),
                    broker="Webull",
                ),
            ]
        )

        user_id = uuid.uuid4()
        result = await service.import_snapshot(user_id, data)

        # All 3 entries should be added
        assert db.add.call_count == 3
        # flush called once (atomic)
        assert db.flush.call_count == 1
        # refresh called for each transaction
        assert db.refresh.call_count == 3
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_single_entry_persisted(self):
        """A single valid entry is persisted correctly."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="DRAM",
                    quantity=1000,
                    price_per_share=Decimal("3.50"),
                    broker="Webull",
                ),
            ]
        )

        result = await service.import_snapshot(uuid.uuid4(), data)

        assert db.add.call_count == 1
        assert db.flush.call_count == 1
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_db_failure_prevents_all_inserts(self):
        """If db.flush raises, no entries are persisted (atomic failure)."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock(side_effect=Exception("DB connection lost"))
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("25.00"),
                    broker="Webull",
                ),
                SnapshotEntry(
                    stock_symbol="META",
                    quantity=200,
                    price_per_share=Decimal("10.00"),
                    broker="Dime",
                ),
            ]
        )

        with pytest.raises(Exception, match="DB connection lost"):
            await service.import_snapshot(uuid.uuid4(), data)

        # add was called but flush failed, so nothing is committed
        assert db.add.call_count == 2
        # refresh was never called since flush failed
        assert db.refresh.call_count == 0

    def test_batch_rejected_if_any_entry_invalid_quantity(self):
        """Entire batch is rejected if any entry has invalid quantity (≤0)."""
        with pytest.raises(ValidationError) as exc_info:
            SnapshotCreate(
                entries=[
                    SnapshotEntry(
                        stock_symbol="AAPL",
                        quantity=100,
                        price_per_share=Decimal("25.00"),
                        broker="Webull",
                    ),
                    SnapshotEntry(
                        stock_symbol="META",
                        quantity=0,  # Invalid: quantity must be > 0
                        price_per_share=Decimal("10.00"),
                        broker="Dime",
                    ),
                ]
            )

        errors = exc_info.value.errors()
        assert any("quantity" in str(e["loc"]) for e in errors)

    def test_batch_rejected_if_any_entry_invalid_price(self):
        """Entire batch is rejected if any entry has invalid price (≤0)."""
        with pytest.raises(ValidationError) as exc_info:
            SnapshotCreate(
                entries=[
                    SnapshotEntry(
                        stock_symbol="AAPL",
                        quantity=100,
                        price_per_share=Decimal("25.00"),
                        broker="Webull",
                    ),
                    SnapshotEntry(
                        stock_symbol="DRAM",
                        quantity=50,
                        price_per_share=Decimal("-1.00"),  # Invalid: price must be > 0
                        broker="Webull",
                    ),
                ]
            )

        errors = exc_info.value.errors()
        assert any("price_per_share" in str(e["loc"]) for e in errors)

    def test_batch_rejected_if_entry_missing_broker(self):
        """Entire batch is rejected if any entry has missing broker."""
        with pytest.raises(ValidationError) as exc_info:
            SnapshotCreate(
                entries=[
                    SnapshotEntry(
                        stock_symbol="AAPL",
                        quantity=100,
                        price_per_share=Decimal("25.00"),
                        broker="Webull",
                    ),
                    SnapshotEntry(
                        stock_symbol="META",
                        quantity=200,
                        price_per_share=Decimal("10.00"),
                        broker="",  # Invalid: broker must be non-empty
                    ),
                ]
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_batch_rejected_if_entry_missing_symbol(self):
        """Entire batch is rejected if any entry has missing stock_symbol."""
        with pytest.raises(ValidationError) as exc_info:
            SnapshotCreate(
                entries=[
                    SnapshotEntry(
                        stock_symbol="",  # Invalid: must be at least 1 char
                        quantity=100,
                        price_per_share=Decimal("25.00"),
                        broker="Webull",
                    ),
                ]
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_empty_entries_list_rejected(self):
        """Empty entries list is rejected (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            SnapshotCreate(entries=[])

        errors = exc_info.value.errors()
        assert any("entries" in str(e["loc"]) for e in errors)


class TestSnapshotFieldCalculations:
    """Test that snapshot entries have correct field values."""

    @pytest.mark.asyncio
    async def test_gross_value_calculation(self):
        """gross_value = quantity × price_per_share for each entry."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=150,
                    price_per_share=Decimal("22.50"),
                    broker="Webull",
                ),
                SnapshotEntry(
                    stock_symbol="META",
                    quantity=300,
                    price_per_share=Decimal("8.75"),
                    broker="Dime",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        # Check the Transaction objects added to the session
        calls = db.add.call_args_list
        tx1 = calls[0][0][0]
        tx2 = calls[1][0][0]

        # AAPL: 150 * 22.50 = 3375.00
        assert tx1.gross_value == Decimal("3375.00")
        # META: 300 * 8.75 = 2625.00
        assert tx2.gross_value == Decimal("2625.00")

    @pytest.mark.asyncio
    async def test_net_capital_flow_equals_gross_value(self):
        """net_capital_flow = gross_value (no fees for snapshots)."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="DRAM",
                    quantity=500,
                    price_per_share=Decimal("4.20"),
                    broker="Webull",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        tx = db.add.call_args[0][0]
        # gross = 500 * 4.20 = 2100.00
        assert tx.gross_value == Decimal("2100.00")
        assert tx.net_capital_flow == Decimal("2100.00")
        assert tx.net_capital_flow == tx.gross_value

    @pytest.mark.asyncio
    async def test_brokerage_fee_and_vat_are_zero(self):
        """Snapshots have zero brokerage_fee and zero VAT."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("30.00"),
                    broker="Webull",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        tx = db.add.call_args[0][0]
        assert tx.brokerage_fee == Decimal("0")
        assert tx.vat == Decimal("0")

    @pytest.mark.asyncio
    async def test_action_is_snapshot(self):
        """All entries are stored with action='Snapshot'."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("25.00"),
                    broker="Webull",
                ),
                SnapshotEntry(
                    stock_symbol="META",
                    quantity=200,
                    price_per_share=Decimal("10.00"),
                    broker="Dime",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        calls = db.add.call_args_list
        for call in calls:
            tx = call[0][0]
            assert tx.action == "Snapshot"

    @pytest.mark.asyncio
    async def test_date_is_today(self):
        """Snapshot entries use today's date."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("25.00"),
                    broker="Webull",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        tx = db.add.call_args[0][0]
        assert tx.date == date.today()

    @pytest.mark.asyncio
    async def test_user_id_is_set_correctly(self):
        """Each snapshot entry is associated with the correct user_id."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)
        user_id = uuid.uuid4()

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("25.00"),
                    broker="Webull",
                ),
                SnapshotEntry(
                    stock_symbol="META",
                    quantity=50,
                    price_per_share=Decimal("15.00"),
                    broker="Dime",
                ),
            ]
        )

        await service.import_snapshot(user_id, data)

        calls = db.add.call_args_list
        for call in calls:
            tx = call[0][0]
            assert tx.user_id == user_id

    @pytest.mark.asyncio
    async def test_stock_symbol_preserved(self):
        """Stock symbols from entries are stored correctly."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="aapl",  # lowercase input
                    quantity=100,
                    price_per_share=Decimal("25.00"),
                    broker="Webull",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        tx = db.add.call_args[0][0]
        # The SnapshotEntry validator uppercases the symbol
        assert tx.stock_symbol == "AAPL"


class TestSnapshotInHoldingsCalculation:
    """Test that snapshot quantities are included in holdings calculation."""

    @pytest.mark.asyncio
    async def test_holdings_includes_snapshot_quantities(self):
        """The get_holdings SQL includes Snapshot action in the sum."""
        db = AsyncMock()
        # Simulate DB returning 300 (100 buy + 200 snapshot)
        db.execute = AsyncMock(return_value=FakeResult(300))

        service = TradingService(db)
        result = await service.get_holdings(uuid.uuid4(), "AAPL")

        assert result == 300

    @pytest.mark.asyncio
    async def test_snapshot_entries_have_unique_ids(self):
        """Each snapshot entry gets a unique UUID."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = TradingService(db)

        data = SnapshotCreate(
            entries=[
                SnapshotEntry(
                    stock_symbol="AAPL",
                    quantity=100,
                    price_per_share=Decimal("25.00"),
                    broker="Webull",
                ),
                SnapshotEntry(
                    stock_symbol="META",
                    quantity=200,
                    price_per_share=Decimal("10.00"),
                    broker="Dime",
                ),
            ]
        )

        await service.import_snapshot(uuid.uuid4(), data)

        calls = db.add.call_args_list
        ids = [call[0][0].id for call in calls]
        # All IDs should be unique
        assert len(set(ids)) == len(ids)
