"""PriceAlert model."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceAlert(Base):
    """Price alert configuration for a stock symbol."""

    __tablename__ = "price_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_type: Mapped[str] = mapped_column(
        Enum("Above", "Below", name="alert_type"), nullable=False
    )
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="price_alerts")
    history = relationship("AlertHistory", back_populates="alert", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_price_alerts_user_id", "user_id"),
        Index("ix_price_alerts_user_symbol", "user_id", "stock_symbol"),
        {"comment": "Price alert configurations"},
    )
