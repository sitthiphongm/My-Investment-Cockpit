"""Rebalancing service - Business logic for portfolio rebalancing insights.

Provides:
- Setting target allocations (must sum to 100%)
- Comparing current vs target allocations
- Highlighting over/under-weight positions based on configurable deviation threshold
- Suggesting buy/sell actions to reach target allocations
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target_allocation import TargetAllocation
from app.schemas.enums import TargetType
from app.schemas.rebalancing import (
    RebalancingPositionResponse,
    RebalancingResponse,
    TargetAllocationEntry,
    TargetAllocationUpdate,
)

TWO_PLACES = Decimal("0.01")
DEFAULT_DEVIATION_THRESHOLD = Decimal("5.00")


class RebalancingService:
    """Service for portfolio rebalancing insights.

    Key logic:
    - Target allocations must sum to exactly 100%
    - Deviation threshold (default 5pp) determines over/under-weight highlighting
    - Suggested actions: buy/sell shares to move from current to target allocation
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_target_allocations(
        self, user_id: uuid.UUID, data: TargetAllocationUpdate
    ) -> list[TargetAllocation]:
        """Set target allocations for a user.

        Replaces all existing target allocations with the new set.
        Validation that targets sum to 100% is handled by the Pydantic schema.

        Args:
            user_id: The authenticated user's ID.
            data: TargetAllocationUpdate containing list of targets that sum to 100%.

        Returns:
            List of persisted TargetAllocation records.
        """
        # Delete all existing target allocations for this user
        await self.db.execute(
            delete(TargetAllocation).where(TargetAllocation.user_id == user_id)
        )

        # Insert new target allocations
        new_records = []
        for entry in data.targets:
            record = TargetAllocation(
                id=uuid.uuid4(),
                user_id=user_id,
                target_key=entry.target_key,
                target_type=entry.target_type.value,
                target_percentage=entry.target_percentage,
            )
            self.db.add(record)
            new_records.append(record)

        await self.db.flush()
        return new_records

    async def get_target_allocations(
        self, user_id: uuid.UUID
    ) -> list[TargetAllocation]:
        """Get all target allocations for a user.

        Returns:
            List of TargetAllocation records, empty if none set.
        """
        stmt = select(TargetAllocation).where(
            TargetAllocation.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_rebalancing_insights(
        self,
        user_id: uuid.UUID,
        current_allocations: dict[str, Decimal],
        current_prices: dict[str, Optional[Decimal]],
        position_quantities: dict[str, int],
        total_portfolio_value: Optional[Decimal],
        deviation_threshold: Decimal = DEFAULT_DEVIATION_THRESHOLD,
    ) -> RebalancingResponse:
        """Get rebalancing insights comparing current vs target allocations.

        Args:
            user_id: The authenticated user's ID.
            current_allocations: Dict mapping target_key -> current allocation %.
            current_prices: Dict mapping symbol -> current price (for buy/sell suggestions).
            position_quantities: Dict mapping symbol -> current held quantity.
            total_portfolio_value: Total portfolio market value for calculating share counts.
            deviation_threshold: Percentage points deviation to trigger over/under-weight
                                 highlighting (default 5pp).

        Returns:
            RebalancingResponse with position comparison and suggested actions.
        """
        # Get target allocations
        targets = await self.get_target_allocations(user_id)

        if not targets:
            return RebalancingResponse(
                positions=[],
                deviation_threshold=deviation_threshold,
            )

        positions: list[RebalancingPositionResponse] = []

        for target in targets:
            target_key = target.target_key
            target_type = TargetType(target.target_type)
            target_pct = Decimal(str(target.target_percentage))
            current_pct = current_allocations.get(target_key, Decimal("0.00"))

            # Calculate difference: current - target
            difference = (current_pct - target_pct).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )

            # Determine over/under-weight based on deviation threshold
            is_overweight = difference > deviation_threshold
            is_underweight = difference < -deviation_threshold

            # Generate suggested action
            suggested_action = self._generate_suggestion(
                target_key=target_key,
                target_type=target_type,
                difference=difference,
                is_overweight=is_overweight,
                is_underweight=is_underweight,
                current_price=current_prices.get(target_key),
                current_quantity=position_quantities.get(target_key, 0),
                total_portfolio_value=total_portfolio_value,
                target_pct=target_pct,
                current_pct=current_pct,
            )

            position = RebalancingPositionResponse(
                target_key=target_key,
                target_type=target_type,
                current_allocation=current_pct,
                target_allocation=target_pct,
                difference=difference,
                is_overweight=is_overweight,
                is_underweight=is_underweight,
                suggested_action=suggested_action,
            )
            positions.append(position)

        return RebalancingResponse(
            positions=positions,
            deviation_threshold=deviation_threshold,
        )

    def _generate_suggestion(
        self,
        target_key: str,
        target_type: TargetType,
        difference: Decimal,
        is_overweight: bool,
        is_underweight: bool,
        current_price: Optional[Decimal],
        current_quantity: int,
        total_portfolio_value: Optional[Decimal],
        target_pct: Decimal,
        current_pct: Decimal,
    ) -> Optional[str]:
        """Generate a buy/sell suggestion to reach target allocation.

        Calculates the number of shares to buy or sell based on the difference
        between current and target allocation, using the current price.

        Returns:
            A suggestion string like "Buy 10 shares" or "Sell 5 shares",
            or None if no action needed or calculation not possible.
        """
        if not is_overweight and not is_underweight:
            return None

        # For Sector-based targets, suggest allocation adjustment (no share counts)
        if target_type != TargetType.SYMBOL:
            if is_overweight:
                return f"Reduce sector allocation by {abs(difference):.2f}pp"
            return f"Increase sector allocation by {abs(difference):.2f}pp"

        # Cannot suggest share counts without price or portfolio value
        if current_price is None or current_price <= 0:
            if is_overweight:
                return "Reduce position (price unavailable)"
            return "Increase position (price unavailable)"

        if total_portfolio_value is None or total_portfolio_value <= 0:
            if is_overweight:
                return "Reduce position (portfolio value unavailable)"
            return "Increase position (portfolio value unavailable)"

        # Calculate target value and current value
        target_value = (target_pct / Decimal("100")) * total_portfolio_value
        current_value = (current_pct / Decimal("100")) * total_portfolio_value
        value_diff = target_value - current_value

        # Calculate shares to trade
        shares_to_trade = int(
            abs(value_diff / current_price).to_integral_value()
        )

        if shares_to_trade == 0:
            return None

        if is_underweight:
            return f"Buy {shares_to_trade} shares"
        else:
            return f"Sell {shares_to_trade} shares"
