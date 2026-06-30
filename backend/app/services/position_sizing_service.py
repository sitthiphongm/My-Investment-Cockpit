"""Position Sizing service — calculates recommended position size based on risk parameters."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PositionSizeInput:
    """Input parameters for position sizing calculation."""

    portfolio_value: Decimal
    max_risk_per_trade: Decimal  # As decimal, e.g., 0.02 for 2%
    entry_price: Decimal
    stop_loss_price: Decimal
    # Optional
    confidence_score: int | None = None  # 1-10
    target_allocation: Decimal | None = None  # max % of portfolio


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""

    suggested_shares: int
    capital_required: Decimal
    portfolio_allocation_pct: Decimal
    expected_downside: Decimal
    risk_per_share: Decimal
    max_position_value: Decimal
    warnings: list[str]


class PositionSizingService:
    """Calculates recommended position size using risk-based methodology.

    Formula:
        max_position_value = portfolio_value × max_risk_per_trade
        risk_per_share = entry_price - stop_loss_price
        suggested_shares = max_position_value / risk_per_share
        capital_required = suggested_shares × entry_price
        expected_downside = suggested_shares × risk_per_share
    """

    def calculate(self, params: PositionSizeInput) -> PositionSizeResult:
        """Calculate recommended position size.

        Validates inputs and returns sizing recommendation with warnings.
        """
        warnings = []

        # Validate inputs
        if params.entry_price <= 0:
            raise ValueError("Entry price must be positive")
        if params.stop_loss_price >= params.entry_price:
            raise ValueError("Stop loss must be below entry price")
        if params.portfolio_value <= 0:
            raise ValueError("Portfolio value must be positive")
        if params.max_risk_per_trade <= 0 or params.max_risk_per_trade > Decimal("0.5"):
            raise ValueError("Max risk per trade must be between 0 and 50%")

        risk_per_share = params.entry_price - params.stop_loss_price
        max_position_value = params.portfolio_value * params.max_risk_per_trade

        # Calculate shares
        suggested_shares_raw = max_position_value / risk_per_share
        suggested_shares = int(suggested_shares_raw)

        if suggested_shares == 0:
            suggested_shares = 1
            warnings.append("Minimum 1 share; risk per trade exceeds specified maximum.")

        capital_required = Decimal(str(suggested_shares)) * params.entry_price
        portfolio_allocation = capital_required / params.portfolio_value * 100
        expected_downside = Decimal(str(suggested_shares)) * risk_per_share

        # Check concentration warnings
        if portfolio_allocation > 25:
            warnings.append(f"Position would be {portfolio_allocation:.1f}% of portfolio — exceeds 25% concentration threshold.")

        if params.target_allocation and portfolio_allocation > params.target_allocation:
            warnings.append(f"Position would exceed target allocation of {params.target_allocation}%.")

        # Confidence adjustment hint
        if params.confidence_score and params.confidence_score < 5:
            warnings.append("Low confidence score — consider reducing position size.")

        return PositionSizeResult(
            suggested_shares=suggested_shares,
            capital_required=round(capital_required, 2),
            portfolio_allocation_pct=round(portfolio_allocation, 2),
            expected_downside=round(expected_downside, 2),
            risk_per_share=round(risk_per_share, 2),
            max_position_value=round(max_position_value, 2),
            warnings=warnings,
        )
