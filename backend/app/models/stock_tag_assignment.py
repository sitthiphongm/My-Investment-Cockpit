"""StockTagAssignment model."""

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StockTagAssignment(Base):
    """Assigns tags to stock symbols (not transactions)."""

    __tablename__ = "stock_tag_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    stock_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    tag = relationship("Tag", back_populates="stock_assignments")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "stock_symbol", "tag_id", name="uq_stock_tag_assignment"
        ),
        Index("ix_stock_tag_assignments_user_id", "user_id"),
        Index("ix_stock_tag_assignments_tag_id", "tag_id"),
        {"comment": "Assigns tags to stock symbols for categorization"},
    )
