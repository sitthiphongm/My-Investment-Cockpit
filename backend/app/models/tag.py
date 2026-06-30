"""Tag and TransactionTag models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tag(Base):
    """User-defined tag for categorizing transactions and stocks."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="tags")
    transactions = relationship(
        "Transaction", secondary="transaction_tags", back_populates="tags", lazy="selectin"
    )
    stock_assignments = relationship(
        "StockTagAssignment", back_populates="tag", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
        Index("ix_tags_user_id", "user_id"),
        {"comment": "User-defined tags for categorization"},
    )


class TransactionTag(Base):
    """Association table linking transactions to tags."""

    __tablename__ = "transaction_tags"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
