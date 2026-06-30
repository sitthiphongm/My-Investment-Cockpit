"""InvestmentIdea model."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestmentIdea(Base):
    """Investment thesis/idea for a stock."""

    __tablename__ = "investment_ideas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    risk_level: Mapped[str] = mapped_column(
        Enum("Low", "Medium", "High", name="risk_level"), nullable=False
    )
    source_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "Researching", "Watching", "Bought", "Passed", "Closed",
            name="idea_status",
        ),
        nullable=False,
        default="Researching",
    )
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="investment_ideas")
    break_conditions = relationship("ThesisBreakCondition", back_populates="idea", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_investment_ideas_user_id", "user_id"),
        Index("ix_investment_ideas_user_status", "user_id", "status"),
        Index("ix_investment_ideas_user_symbol", "user_id", "stock_symbol"),
        {"comment": "Investment thesis and idea tracking"},
    )
