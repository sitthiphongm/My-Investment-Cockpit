"""TargetAllocation model."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TargetAllocation(Base):
    """Target portfolio allocation for rebalancing."""

    __tablename__ = "target_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_key: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(
        Enum("Symbol", "Sector", name="target_type"), nullable=False
    )
    target_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="target_allocations")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_key", "target_type", name="uq_target_allocation"
        ),
        Index("ix_target_allocations_user_id", "user_id"),
        {"comment": "Target portfolio allocations for rebalancing"},
    )
