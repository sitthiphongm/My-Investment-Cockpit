"""FX Rate Entry model for cached and manual exchange rates."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FXRateEntry(Base):
    """Cached or manually entered FX rate for a currency pair and date."""

    __tablename__ = "fx_rate_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    provider_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetch_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staleness: Mapped[str] = mapped_column(
        Enum("Fresh", "Stale", "Manual", name="fx_staleness"),
        nullable=False,
        default="Fresh",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    user = relationship("User")

    __table_args__ = (
        Index("ix_fx_rates_user_pair_date", "user_id", "base_currency", "quote_currency", "rate_date"),
        {"comment": "FX rate cache entries with audit metadata"},
    )
