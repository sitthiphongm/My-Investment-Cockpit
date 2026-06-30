"""Scenario Simulator service — models portfolio impact without mutating real data."""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


@dataclass
class ScenarioInput:
    """Input parameters for a portfolio scenario simulation."""

    # Price change simulation
    price_changes: dict[str, Decimal] | None = None  # symbol -> new_price

    # Buy/Sell simulation
    simulated_buys: list[dict] | None = None  # [{symbol, quantity, price}]
    simulated_sells: list[dict] | None = None  # [{symbol, quantity, price}]

    # Cash simulation
    cash_deposit: Decimal | None = None
    fx_rate_change: Decimal | None = None


@dataclass
class SimulationResult:
    """Result of a portfolio scenario simulation."""

    current_total_cost: Decimal = Decimal("0")
    current_market_value: Decimal = Decimal("0")
    simulated_market_value: Decimal = Decimal("0")
    current_pl: Decimal = Decimal("0")
    simulated_pl: Decimal = Decimal("0")
    current_position_count: int = 0
    simulated_position_count: int = 0
    impact_on_value: Decimal = Decimal("0")
    impact_on_pl: Decimal = Decimal("0")
    warnings: list[str] | None = None


class ScenarioSimulatorService:
    """Models what-if scenarios without modifying real portfolio data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_simulation(
        self, user_id: uuid.UUID, scenario: ScenarioInput
    ) -> SimulationResult:
        """Run a simulation and return projected impact.

        IMPORTANT: This method NEVER modifies real data.
        """
        # Get current positions
        positions = await self._get_current_positions(user_id)
        warnings = []

        current_cost = sum(p["total_cost"] for p in positions.values())
        # Without live market data, use cost as proxy for current value
        current_value = current_cost

        # Apply price changes
        simulated_value = current_value
        if scenario.price_changes:
            for symbol, new_price in scenario.price_changes.items():
                if symbol in positions:
                    pos = positions[symbol]
                    old_value = pos["total_cost"]  # approximation without market data
                    new_value = new_price * pos["quantity"]
                    simulated_value += (new_value - old_value)
                else:
                    warnings.append(f"{symbol} not in portfolio, price change ignored.")

        # Apply simulated buys
        sim_positions = dict(positions)
        if scenario.simulated_buys:
            for buy in scenario.simulated_buys:
                symbol = buy.get("symbol", "")
                qty = buy.get("quantity", 0)
                price = Decimal(str(buy.get("price", 0)))
                cost = qty * price
                simulated_value += cost
                if symbol in sim_positions:
                    sim_positions[symbol]["quantity"] += qty
                    sim_positions[symbol]["total_cost"] += cost
                else:
                    sim_positions[symbol] = {"quantity": qty, "total_cost": cost}

        # Apply simulated sells
        if scenario.simulated_sells:
            for sell in scenario.simulated_sells:
                symbol = sell.get("symbol", "")
                qty = sell.get("quantity", 0)
                price = Decimal(str(sell.get("price", 0)))
                if symbol in sim_positions:
                    if qty > sim_positions[symbol]["quantity"]:
                        warnings.append(f"Cannot sell {qty} of {symbol}, only {sim_positions[symbol]['quantity']} held.")
                        qty = sim_positions[symbol]["quantity"]
                    proceeds = qty * price
                    sim_positions[symbol]["quantity"] -= qty
                    simulated_value -= (sim_positions[symbol]["total_cost"] / max(1, sim_positions[symbol]["quantity"] + qty)) * qty
                    simulated_value += proceeds
                    if sim_positions[symbol]["quantity"] == 0:
                        del sim_positions[symbol]
                else:
                    warnings.append(f"{symbol} not in portfolio, sell ignored.")

        # Apply cash deposit
        if scenario.cash_deposit:
            simulated_value += scenario.cash_deposit

        simulated_cost = sum(p["total_cost"] for p in sim_positions.values())
        simulated_pl = simulated_value - simulated_cost
        current_pl = current_value - current_cost

        return SimulationResult(
            current_total_cost=current_cost,
            current_market_value=current_value,
            simulated_market_value=simulated_value,
            current_pl=current_pl,
            simulated_pl=simulated_pl,
            current_position_count=len(positions),
            simulated_position_count=len(sim_positions),
            impact_on_value=simulated_value - current_value,
            impact_on_pl=simulated_pl - current_pl,
            warnings=warnings or None,
        )

    async def _get_current_positions(self, user_id: uuid.UUID) -> dict:
        """Get current positions as {symbol: {quantity, total_cost}}."""
        result = await self.db.execute(
            select(
                Transaction.stock_symbol,
                Transaction.action,
                func.sum(Transaction.quantity).label("total_qty"),
                func.sum(Transaction.gross_value).label("total_value"),
            )
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.stock_symbol, Transaction.action)
        )
        rows = result.all()

        positions: dict[str, dict] = {}
        for row in rows:
            symbol = row.stock_symbol
            if symbol not in positions:
                positions[symbol] = {"quantity": 0, "total_cost": Decimal("0")}

            if row.action in ("Buy", "Snapshot"):
                positions[symbol]["quantity"] += row.total_qty
                positions[symbol]["total_cost"] += row.total_value
            elif row.action == "Sell":
                positions[symbol]["quantity"] -= row.total_qty

        # Remove zero-quantity positions
        return {k: v for k, v in positions.items() if v["quantity"] > 0}
