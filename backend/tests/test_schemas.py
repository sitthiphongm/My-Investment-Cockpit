"""Unit tests for Pydantic schemas and validators."""

from datetime import date, timedelta, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    ActionType,
    AlertCreate,
    AlertType,
    DividendCreate,
    IdeaCreate,
    IdeaStatus,
    IdeaUpdate,
    RiskLevel,
    SentimentType,
    SnapshotCreate,
    TargetAllocationEntry,
    TargetAllocationUpdate,
    TransactionCreate,
    TransactionResponse,
    TransferCreate,
    TransferType,
    UserStatus,
    WatchlistItemCreate,
)
from app.schemas.enums import TargetType, TermType
from app.schemas.transactions import SnapshotEntry, TransactionUpdate
from app.schemas.transfers import TransferUpdate


class TestEnums:
    """Test enum values are correct."""

    def test_action_type_values(self):
        assert ActionType.BUY.value == "Buy"
        assert ActionType.SELL.value == "Sell"
        assert ActionType.SNAPSHOT.value == "Snapshot"

    def test_transfer_type_values(self):
        assert TransferType.IN.value == "In"
        assert TransferType.OUT.value == "Out"

    def test_alert_type_values(self):
        assert AlertType.ABOVE.value == "Above"
        assert AlertType.BELOW.value == "Below"

    def test_risk_level_values(self):
        assert RiskLevel.LOW.value == "Low"
        assert RiskLevel.MEDIUM.value == "Medium"
        assert RiskLevel.HIGH.value == "High"

    def test_idea_status_values(self):
        assert IdeaStatus.RESEARCHING.value == "Researching"
        assert IdeaStatus.WATCHING.value == "Watching"
        assert IdeaStatus.BOUGHT.value == "Bought"
        assert IdeaStatus.PASSED.value == "Passed"
        assert IdeaStatus.CLOSED.value == "Closed"

    def test_user_status_values(self):
        assert UserStatus.APPROVED.value == "Approved"
        assert UserStatus.PENDING.value == "Pending"
        assert UserStatus.BLOCKED.value == "Blocked"

    def test_sentiment_type_values(self):
        assert SentimentType.BEAR.value == "Bear"
        assert SentimentType.BULL.value == "Bull"

    def test_term_type_values(self):
        assert TermType.SHORT_TERM.value == "Short-term"
        assert TermType.LONG_TERM.value == "Long-term"


class TestTransactionCreate:
    """Test TransactionCreate schema validators."""

    def _valid_data(self, **overrides):
        data = {
            "date": date(2024, 1, 15),
            "stock_symbol": "AAPL",
            "action": ActionType.BUY,
            "quantity": 100,
            "price_per_share": Decimal("150.00"),
            "brokerage_fee": Decimal("22.50"),
            "vat": Decimal("1.58"),
            "broker": "Webull",
        }
        data.update(overrides)
        return data

    def test_valid_transaction(self):
        t = TransactionCreate(**self._valid_data())
        assert t.stock_symbol == "AAPL"
        assert t.quantity == 100

    def test_symbol_uppercase_conversion(self):
        t = TransactionCreate(**self._valid_data(stock_symbol="aapl"))
        assert t.stock_symbol == "AAPL"

    def test_symbol_with_dot(self):
        t = TransactionCreate(**self._valid_data(stock_symbol="brk.b"))
        assert t.stock_symbol == "BRK.B"

    def test_symbol_invalid_chars(self):
        with pytest.raises(ValidationError, match="uppercase letters"):
            TransactionCreate(**self._valid_data(stock_symbol="AA PL"))

    def test_date_not_future(self):
        with pytest.raises(ValidationError, match="future"):
            TransactionCreate(**self._valid_data(date=date.today() + timedelta(days=1)))

    def test_date_today_is_valid(self):
        t = TransactionCreate(**self._valid_data(date=date.today()))
        assert t.date == date.today()

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            TransactionCreate(**self._valid_data(quantity=0))

    def test_quantity_must_not_exceed_max(self):
        with pytest.raises(ValidationError):
            TransactionCreate(**self._valid_data(quantity=100_000_000))

    def test_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            TransactionCreate(**self._valid_data(price_per_share=Decimal("0")))

    def test_brokerage_fee_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            TransactionCreate(**self._valid_data(brokerage_fee=Decimal("-1")))

    def test_vat_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            TransactionCreate(**self._valid_data(vat=Decimal("-0.01")))

    def test_broker_not_blank(self):
        with pytest.raises(ValidationError, match="blank"):
            TransactionCreate(**self._valid_data(broker="   "))

    def test_broker_trimmed(self):
        t = TransactionCreate(**self._valid_data(broker="  Webull  "))
        assert t.broker == "Webull"


class TestTransferCreate:
    """Test TransferCreate schema validators."""

    def _valid_data(self, **overrides):
        data = {
            "date": date(2024, 1, 15),
            "broker": "Webull",
            "transfer_type": TransferType.IN,
            "amount": Decimal("10000.00"),
        }
        data.update(overrides)
        return data

    def test_valid_transfer(self):
        t = TransferCreate(**self._valid_data())
        assert t.amount == Decimal("10000.00")

    def test_date_not_future(self):
        with pytest.raises(ValidationError, match="future"):
            TransferCreate(**self._valid_data(date=date.today() + timedelta(days=1)))

    def test_broker_not_blank(self):
        with pytest.raises(ValidationError, match="blank"):
            TransferCreate(**self._valid_data(broker="   "))

    def test_broker_trimmed(self):
        t = TransferCreate(**self._valid_data(broker="  Dime  "))
        assert t.broker == "Dime"

    def test_amount_max_2_decimals(self):
        with pytest.raises(ValidationError, match="decimal"):
            TransferCreate(**self._valid_data(amount=Decimal("100.123")))

    def test_amount_min_001(self):
        with pytest.raises(ValidationError):
            TransferCreate(**self._valid_data(amount=Decimal("0.001")))

    def test_amount_max_limit(self):
        with pytest.raises(ValidationError):
            TransferCreate(**self._valid_data(amount=Decimal("1000000000.00")))

    def test_amount_2_decimals_valid(self):
        t = TransferCreate(**self._valid_data(amount=Decimal("0.01")))
        assert t.amount == Decimal("0.01")


class TestTargetAllocation:
    """Test target allocation sum constraint."""

    def test_valid_targets_sum_to_100(self):
        targets = TargetAllocationUpdate(targets=[
            TargetAllocationEntry(
                target_key="AAPL", target_type=TargetType.SYMBOL,
                target_percentage=Decimal("60.00")
            ),
            TargetAllocationEntry(
                target_key="GOOGL", target_type=TargetType.SYMBOL,
                target_percentage=Decimal("40.00")
            ),
        ])
        assert len(targets.targets) == 2

    def test_rejects_targets_not_sum_to_100(self):
        with pytest.raises(ValidationError, match="100"):
            TargetAllocationUpdate(targets=[
                TargetAllocationEntry(
                    target_key="AAPL", target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("60.00")
                ),
                TargetAllocationEntry(
                    target_key="GOOGL", target_type=TargetType.SYMBOL,
                    target_percentage=Decimal("30.00")
                ),
            ])


class TestIdeaCreate:
    """Test investment idea schema validators."""

    def test_valid_idea(self):
        idea = IdeaCreate(
            stock_symbol="meta", title="AI Play", risk_level=RiskLevel.HIGH
        )
        assert idea.stock_symbol == "META"
        assert idea.status == IdeaStatus.RESEARCHING

    def test_title_not_blank(self):
        with pytest.raises(ValidationError, match="blank"):
            IdeaCreate(stock_symbol="META", title="   ", risk_level=RiskLevel.LOW)

    def test_symbol_uppercase(self):
        idea = IdeaCreate(
            stock_symbol="googl", title="Search", risk_level=RiskLevel.MEDIUM
        )
        assert idea.stock_symbol == "GOOGL"


class TestSnapshotCreate:
    """Test performance snapshot create validators."""

    def test_valid_snapshot(self):
        s = SnapshotCreate(
            date=date(2024, 6, 1),
            total_portfolio_value=Decimal("500000.00"),
            total_cost=Decimal("400000.00"),
        )
        assert s.total_portfolio_value == Decimal("500000.00")

    def test_date_not_future(self):
        with pytest.raises(ValidationError, match="future"):
            SnapshotCreate(
                date=date.today() + timedelta(days=1),
                total_portfolio_value=Decimal("500000.00"),
                total_cost=Decimal("400000.00"),
            )

    def test_value_max_2_decimals(self):
        with pytest.raises(ValidationError, match="decimal"):
            SnapshotCreate(
                date=date(2024, 6, 1),
                total_portfolio_value=Decimal("500000.123"),
                total_cost=Decimal("400000.00"),
            )
