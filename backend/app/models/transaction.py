"""Transaction model."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    """Stock transaction (buy/sell/snapshot) model."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(
        Enum("Buy", "Sell", "Snapshot", name="action_type"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    price_per_share: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    gross_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    brokerage_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    vat: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    net_capital_flow: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    broker: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="transactions")
    note = relationship(
        "TransactionNote", back_populates="transaction", uselist=False, lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True
    )
    tags = relationship(
        "Tag", secondary="transaction_tags", back_populates="transactions", lazy="selectin",
        passive_deletes=True
    )

    __table_args__ = (
        Index("ix_transactions_user_id", "user_id"),
        Index("ix_transactions_user_date", "user_id", "date"),
        Index("ix_transactions_user_symbol", "user_id", "stock_symbol"),
        Index("ix_transactions_user_broker", "user_id", "broker"),
        {"comment": "Stock buy/sell/snapshot transactions"},
    )
