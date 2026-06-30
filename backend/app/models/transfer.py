"""Transfer model with FX support (backward-compatible with v1 'amount' field)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transfer(Base):
    """Money transfer (deposit/withdrawal) record with multi-currency FX support.

    Backward compatibility: The 'amount' column is preserved as the primary amount field
    (always stored in USD). New FX fields are added alongside for multi-currency tracking.
    """

    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    broker: Mapped[str] = mapped_column(String(100), nullable=False)
    transfer_type: Mapped[str] = mapped_column(
        Enum("In", "Out", name="transfer_type"), nullable=False
    )
    # Primary amount field (USD, backward-compatible with v1)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # ─── New v2 FX fields (nullable for backward compatibility) ───────────
    original_currency: Mapped[Optional[str]] = mapped_column(
        String(3), nullable=True, default="USD"
    )
    original_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    fx_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    converted_usd_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    fx_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, default=Decimal("0")
    )
    # FX audit fields
    fx_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fx_source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fx_fetch_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Optional note (new in v2)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="transfers")

    @property
    def effective_usd_amount(self) -> Decimal:
        """The USD amount to use for accounting.

        Uses converted_usd_amount if available (FX transfer),
        otherwise falls back to the 'amount' field (direct USD).
        """
        if self.converted_usd_amount is not None:
            return self.converted_usd_amount
        return self.amount

    __table_args__ = (
        Index("ix_transfers_user_id", "user_id"),
        Index("ix_transfers_user_date", "user_id", "date"),
        Index("ix_transfers_user_broker", "user_id", "broker"),
        {"comment": "Money transfer records with FX conversion support"},
    )
