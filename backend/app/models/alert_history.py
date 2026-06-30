"""Alert History model for tracking alert lifecycle events."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AlertHistory(Base):
    """Records lifecycle events for alerts (created, triggered, snoozed, resolved, email)."""

    __tablename__ = "alert_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_alerts.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(
        Enum(
            "Created", "Triggered", "Snoozed", "Resolved", "EmailSent", "EmailFailed",
            name="alert_event_type",
        ),
        nullable=False,
    )
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    alert = relationship("PriceAlert", back_populates="history")

    __table_args__ = (
        {"comment": "Alert lifecycle event history"},
    )
