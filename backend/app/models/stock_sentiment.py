"""StockSentiment model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StockSentiment(Base):
    """User's sentiment (Bear/Bull) on a stock."""

    __tablename__ = "stock_sentiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    sentiment: Mapped[str] = mapped_column(
        Enum("Bear", "Bull", name="sentiment_type"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="stock_sentiments")

    __table_args__ = (
        UniqueConstraint("user_id", "stock_symbol", name="uq_stock_sentiment_user_symbol"),
        Index("ix_stock_sentiments_user_id", "user_id"),
        {"comment": "User sentiment on stocks (Bear/Bull)"},
    )
