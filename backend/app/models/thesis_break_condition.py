"""Thesis Break Condition model for investment idea monitoring."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ThesisBreakCondition(Base):
    """User-defined condition that invalidates an investment thesis."""

    __tablename__ = "thesis_break_conditions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_ideas.id", ondelete="CASCADE"), nullable=False
    )
    condition_type: Mapped[str] = mapped_column(
        Enum("price_below", "drawdown_pct", "time_elapsed", "custom", name="condition_type"),
        nullable=False,
    )
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    idea = relationship("InvestmentIdea", back_populates="break_conditions")

    __table_args__ = (
        {"comment": "Thesis break conditions that invalidate investment ideas"},
    )
