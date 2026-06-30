"""User model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """User account model for OAuth-authenticated users."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    profile_picture_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    oauth_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    oauth_provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("Approved", "Pending", "Blocked", name="user_status"),
        nullable=False,
        default="Pending",
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    transactions = relationship("Transaction", back_populates="user", lazy="selectin")
    transfers = relationship("Transfer", back_populates="user", lazy="selectin")
    performance_snapshots = relationship(
        "PerformanceSnapshot", back_populates="user", lazy="selectin"
    )
    price_alerts = relationship("PriceAlert", back_populates="user", lazy="selectin")
    dividend_records = relationship(
        "DividendRecord", back_populates="user", lazy="selectin"
    )
    watchlist_items = relationship(
        "WatchlistItem", back_populates="user", lazy="selectin"
    )
    investment_ideas = relationship(
        "InvestmentIdea", back_populates="user", lazy="selectin"
    )
    screener_presets = relationship(
        "ScreenerPreset", back_populates="user", lazy="selectin"
    )
    stock_sentiments = relationship(
        "StockSentiment", back_populates="user", lazy="selectin"
    )
    target_allocations = relationship(
        "TargetAllocation", back_populates="user", lazy="selectin"
    )
    tags = relationship("Tag", back_populates="user", lazy="selectin")
    sessions = relationship("Session", back_populates="user", lazy="selectin")

    __table_args__ = (
        {"comment": "User accounts with OAuth authentication"},
    )
