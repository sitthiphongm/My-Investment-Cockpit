"""Tax Lot model for cost basis tracking."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaxLot(Base):
    """Individual purchase lot for FIFO/LIFO/SpecificLot cost basis tracking."""

    __tablename__ = "tax_lots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    buy_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False)
    original_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_per_share: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    broker: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    fx_rate_at_purchase: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum("Open", "Closed", "Partial", name="tax_lot_status"),
        nullable=False,
        default="Open",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User")
    buy_transaction = relationship("Transaction")

    __table_args__ = (
        Index("ix_tax_lots_user_symbol", "user_id", "stock_symbol"),
        Index("ix_tax_lots_user_status", "user_id", "status"),
        {"comment": "Tax lot tracking for cost basis methods (FIFO/LIFO/AvgCost/SpecificLot)"},
    )
