"""Alert service - Business logic for price alert operations."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_alert import PriceAlert
from app.schemas.alerts import AlertCreate
from app.schemas.enums import AlertType


class AlertService:
    """Service for managing price alerts.

    Provides CRUD operations for price alerts and trigger checking logic.
    Alerts are per-user and support multiple alerts per symbol.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_alert(self, user_id: uuid.UUID, data: AlertCreate) -> PriceAlert:
        """Create a new price alert.

        Args:
            user_id: The authenticated user's ID.
            data: Validated alert creation data (symbol, alert_type, target_price, note).

        Returns:
            The newly created PriceAlert record.
        """
        alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            stock_symbol=data.stock_symbol,
            alert_type=data.alert_type.value,
            target_price=data.target_price,
            note=data.note,
            triggered=False,
            created_at=datetime.utcnow(),
        )
        self.db.add(alert)
        await self.db.flush()
        await self.db.refresh(alert)
        return alert

    async def list_active_alerts(self, user_id: uuid.UUID) -> list[PriceAlert]:
        """List active (non-triggered) alerts for a user, sorted by symbol.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            List of active PriceAlert records sorted by stock_symbol ascending.
        """
        stmt = (
            select(PriceAlert)
            .where(
                PriceAlert.user_id == user_id,
                PriceAlert.triggered == False,  # noqa: E712
            )
            .order_by(PriceAlert.stock_symbol.asc(), PriceAlert.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_alert(self, user_id: uuid.UUID, alert_id: uuid.UUID) -> None:
        """Delete a price alert.

        Args:
            user_id: The authenticated user's ID.
            alert_id: The alert ID to delete.

        Raises:
            HTTPException(404): If the alert does not exist or does not belong to the user.
        """
        alert = await self._get_alert_or_404(user_id, alert_id)
        await self.db.delete(alert)
        await self.db.flush()

    async def check_and_trigger_alerts(
        self, market_prices: dict[str, Optional[Decimal]]
    ) -> list[PriceAlert]:
        """Check all active alerts against current market prices and trigger those that match.

        Trigger logic:
        - Above: triggered when current_price >= target_price
        - Below: triggered when current_price <= target_price

        This method checks alerts across ALL users since market data is shared.

        Args:
            market_prices: Dictionary mapping symbol -> current price.
                           Symbols with None price are skipped.

        Returns:
            List of alerts that were triggered during this check.
        """
        triggered_alerts: list[PriceAlert] = []

        # Get all active alerts for symbols that have market prices
        symbols_with_prices = [
            symbol for symbol, price in market_prices.items() if price is not None
        ]
        if not symbols_with_prices:
            return triggered_alerts

        stmt = select(PriceAlert).where(
            PriceAlert.triggered == False,  # noqa: E712
            PriceAlert.stock_symbol.in_(symbols_with_prices),
        )
        result = await self.db.execute(stmt)
        active_alerts = list(result.scalars().all())

        for alert in active_alerts:
            current_price = market_prices.get(alert.stock_symbol)
            if current_price is None:
                continue

            should_trigger = self._should_trigger(
                alert_type=alert.alert_type,
                target_price=alert.target_price,
                current_price=current_price,
            )

            if should_trigger:
                alert.triggered = True
                triggered_alerts.append(alert)

        if triggered_alerts:
            await self.db.flush()

            # Send email notifications for triggered alerts
            await self._send_trigger_emails(triggered_alerts, market_prices)

        return triggered_alerts

    async def _send_trigger_emails(
        self, triggered_alerts: list[PriceAlert], market_prices: dict[str, Optional[Decimal]]
    ) -> None:
        """Send email notifications for triggered alerts.

        Fetches user emails and sends notification for each triggered alert.
        Failures are logged but do not block the alert trigger flow.
        """
        from app.models.user import User
        from app.services.email_service import EmailService

        # Get unique user IDs from triggered alerts
        user_ids = list(set(alert.user_id for alert in triggered_alerts))

        # Fetch user emails
        stmt = select(User).where(User.id.in_(user_ids))
        result = await self.db.execute(stmt)
        users = {user.id: user for user in result.scalars().all()}

        for alert in triggered_alerts:
            user = users.get(alert.user_id)
            if not user or not user.email:
                continue

            current_price = market_prices.get(alert.stock_symbol)
            if current_price is None:
                continue

            EmailService.send_alert_email(
                to_email=user.email,
                stock_symbol=alert.stock_symbol,
                alert_type=alert.alert_type,
                target_price=alert.target_price,
                current_price=current_price,
                note=alert.note,
            )

    @staticmethod
    def _should_trigger(
        alert_type: str, target_price: Decimal, current_price: Decimal
    ) -> bool:
        """Determine if an alert should be triggered based on type and prices.

        Args:
            alert_type: "Above" or "Below".
            target_price: The alert's target price threshold.
            current_price: The current market price.

        Returns:
            True if the alert condition is met.
        """
        if alert_type == AlertType.ABOVE.value:
            return current_price >= target_price
        elif alert_type == AlertType.BELOW.value:
            return current_price <= target_price
        return False

    async def _get_alert_or_404(
        self, user_id: uuid.UUID, alert_id: uuid.UUID
    ) -> PriceAlert:
        """Fetch an alert by ID, ensuring it belongs to the given user.

        Raises:
            HTTPException(404): If the alert is not found.
        """
        stmt = select(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        alert = result.scalar_one_or_none()
        if alert is None:
            raise HTTPException(
                status_code=404,
                detail="Price alert not found",
            )
        return alert
