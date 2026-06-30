"""RealizedPL model."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RealizedPL(Base):
    """Realized profit/loss record from sell transactions."""

    __tablename__ = "realized_pl"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    sell_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    avg_cost_at_sale: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    realized_pl: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    hold_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    term_type: Mapped[str] = mapped_column(
        Enum("Short-term", "Long-term", name="term_type"), nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_realized_pl_user_id", "user_id"),
        Index("ix_realized_pl_user_date", "user_id", "date"),
        Index("ix_realized_pl_user_symbol", "user_id", "stock_symbol"),
        {"comment": "Realized profit/loss records from sell transactions"},
    )
