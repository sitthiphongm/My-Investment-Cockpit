"""PerformanceSnapshot model."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PerformanceSnapshot(Base):
    """Portfolio performance snapshot recorded at a point in time."""

    __tablename__ = "performance_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_portfolio_value: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="performance_snapshots")

    __table_args__ = (
        Index("ix_performance_snapshots_user_id", "user_id"),
        Index("ix_performance_snapshots_user_date", "user_id", "date"),
        {"comment": "Portfolio performance snapshots over time"},
    )
