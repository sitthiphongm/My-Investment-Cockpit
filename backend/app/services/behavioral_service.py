"""Behavioral Analytics service — analyzes trading patterns and decision quality."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.realized_pl import RealizedPL
from app.models.transaction import Transaction


@dataclass
class BehavioralStats:
    """Aggregated behavioral statistics from realized trades."""

    total_closed_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Decimal = Decimal("0")
    avg_winner: Decimal = Decimal("0")
    avg_loser: Decimal = Decimal("0")
    payoff_ratio: Decimal = Decimal("0")
    avg_holding_days: Decimal = Decimal("0")
    best_trade_pl: Decimal = Decimal("0")
    worst_trade_pl: Decimal = Decimal("0")
    total_realized_pl: Decimal = Decimal("0")


@dataclass
class BehaviorPattern:
    """Identified behavioral pattern."""

    pattern_id: str
    label: str
    description: str
    severity: str  # "info", "warning", "concern"
    count: int = 0


class BehavioralAnalyticsService:
    """Analyzes realized trades, journal tags, and holding periods for behavior insights."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self, user_id: uuid.UUID) -> BehavioralStats:
        """Calculate behavioral statistics from realized P/L records."""
        result = await self.db.execute(
            select(RealizedPL).where(RealizedPL.user_id == user_id)
        )
        records = list(result.scalars().all())

        if not records:
            return BehavioralStats()

        winners = [r for r in records if r.realized_pl > 0]
        losers = [r for r in records if r.realized_pl < 0]

        total = len(records)
        win_count = len(winners)
        lose_count = len(losers)

        win_rate = Decimal(str(win_count)) / Decimal(str(total)) * 100 if total > 0 else Decimal("0")
        avg_winner = (
            sum(r.realized_pl for r in winners) / Decimal(str(win_count))
            if win_count > 0 else Decimal("0")
        )
        avg_loser = (
            sum(r.realized_pl for r in losers) / Decimal(str(lose_count))
            if lose_count > 0 else Decimal("0")
        )
        payoff_ratio = (
            avg_winner / abs(avg_loser) if avg_loser != 0 else Decimal("0")
        )
        avg_holding = (
            Decimal(str(sum(r.hold_duration_days for r in records))) / Decimal(str(total))
            if total > 0 else Decimal("0")
        )
        total_pl = sum(r.realized_pl for r in records)
        best_trade = max(r.realized_pl for r in records) if records else Decimal("0")
        worst_trade = min(r.realized_pl for r in records) if records else Decimal("0")

        return BehavioralStats(
            total_closed_trades=total,
            winning_trades=win_count,
            losing_trades=lose_count,
            win_rate=round(win_rate, 2),
            avg_winner=round(avg_winner, 2),
            avg_loser=round(avg_loser, 2),
            payoff_ratio=round(payoff_ratio, 2),
            avg_holding_days=round(avg_holding, 1),
            best_trade_pl=best_trade,
            worst_trade_pl=worst_trade,
            total_realized_pl=total_pl,
        )

    async def get_patterns(self, user_id: uuid.UUID) -> list[BehaviorPattern]:
        """Identify common behavioral patterns from trading history."""
        stats = await self.get_stats(user_id)
        patterns = []

        if stats.total_closed_trades < 5:
            return [BehaviorPattern(
                pattern_id="insufficient_data",
                label="Not enough data",
                description="Need at least 5 closed trades for pattern detection.",
                severity="info",
            )]

        # Pattern: Selling winners too early (short holding on winners)
        result = await self.db.execute(
            select(func.avg(RealizedPL.hold_duration_days)).where(
                RealizedPL.user_id == user_id,
                RealizedPL.realized_pl > 0,
            )
        )
        avg_winner_hold = result.scalar() or 0

        result = await self.db.execute(
            select(func.avg(RealizedPL.hold_duration_days)).where(
                RealizedPL.user_id == user_id,
                RealizedPL.realized_pl < 0,
            )
        )
        avg_loser_hold = result.scalar() or 0

        if avg_winner_hold > 0 and avg_loser_hold > avg_winner_hold * 2:
            patterns.append(BehaviorPattern(
                pattern_id="holding_losers_long",
                label="Holding losers too long",
                description=f"Average losing hold: {int(avg_loser_hold)} days vs winning: {int(avg_winner_hold)} days. Consider reviewing exit discipline.",
                severity="warning",
            ))

        if avg_loser_hold > 0 and avg_winner_hold < avg_loser_hold * 0.5:
            patterns.append(BehaviorPattern(
                pattern_id="selling_winners_early",
                label="Selling winners too early",
                description=f"Winners held {int(avg_winner_hold)} days on average vs losers {int(avg_loser_hold)} days. You may be cutting gains short.",
                severity="warning",
            ))

        # Pattern: Low win rate with poor payoff
        if stats.win_rate < 40 and stats.payoff_ratio < Decimal("1.5"):
            patterns.append(BehaviorPattern(
                pattern_id="low_edge",
                label="Low win rate without compensating payoff",
                description=f"Win rate {stats.win_rate}% with payoff ratio {stats.payoff_ratio}x. Consider being more selective.",
                severity="concern",
            ))

        # Pattern: Overtrading (many short-term trades)
        short_term_count = await self.db.scalar(
            select(func.count(RealizedPL.id)).where(
                RealizedPL.user_id == user_id,
                RealizedPL.hold_duration_days < 7,
            )
        )
        if short_term_count and short_term_count > stats.total_closed_trades * 0.5:
            patterns.append(BehaviorPattern(
                pattern_id="overtrading",
                label="Frequent short-term trading",
                description=f"{short_term_count} of {stats.total_closed_trades} trades held less than 7 days. This increases fees and may reduce returns.",
                severity="warning",
                count=short_term_count,
            ))

        if not patterns:
            patterns.append(BehaviorPattern(
                pattern_id="no_patterns",
                label="No concerning patterns detected",
                description="Your trading behavior appears disciplined based on available data.",
                severity="info",
            ))

        return patterns
