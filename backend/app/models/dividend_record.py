"""DividendRecord model."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DividendRecord(Base):
    """Record of dividend payments received."""

    __tablename__ = "dividend_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_per_share: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    shares_held: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="dividend_records")

    __table_args__ = (
        Index("ix_dividend_records_user_id", "user_id"),
        Index("ix_dividend_records_user_symbol", "user_id", "stock_symbol"),
        Index("ix_dividend_records_user_date", "user_id", "date"),
        {"comment": "Dividend payment records"},
    )
