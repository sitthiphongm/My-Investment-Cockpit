"""AI Insight Service — generates weekly memos and trade reviews.

Supports four modes per spec: Disabled, RuleBased, LocalLLM, HostedLLM.
MVP uses rule-based generation (no paid AI API required).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.realized_pl import RealizedPL
from app.models.transaction import Transaction


class AIInsightService:
    """Generates portfolio insights using rule-based templates or AI providers."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._mode = settings.ai_provider  # "disabled", "rule_based", "local_llm", "hosted_llm"

    @property
    def is_enabled(self) -> bool:
        return self._mode != "disabled"

    @property
    def generation_mode(self) -> str:
        return self._mode

    async def generate_weekly_memo(self, user_id: uuid.UUID) -> dict:
        """Generate a weekly portfolio memo.

        Returns a dict with: content, generation_mode, generated_at, stale_warnings.
        """
        if not self.is_enabled:
            return {
                "content": "AI insights are disabled. Enable in settings to receive weekly portfolio memos.",
                "generation_mode": "Disabled",
                "generated_at": datetime.utcnow().isoformat(),
                "stale_warnings": [],
            }

        # Gather portfolio data for context
        context = await self._build_memo_context(user_id)

        if self._mode == "rule_based":
            content = self._rule_based_memo(context)
        else:
            # Future: local_llm / hosted_llm
            content = self._rule_based_memo(context)

        return {
            "content": content,
            "generation_mode": "RuleBased",
            "generated_at": datetime.utcnow().isoformat(),
            "stale_warnings": context.get("warnings", []),
        }

    async def generate_trade_review(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> dict:
        """Generate a post-trade review for a sell transaction.

        Returns a dict with: content, generation_mode, realized_pl, holding_days.
        """
        if not self.is_enabled:
            return {
                "content": "AI insights are disabled.",
                "generation_mode": "Disabled",
                "realized_pl": None,
                "holding_days": None,
            }

        # Get the realized P/L record for this sell
        result = await self.db.execute(
            select(RealizedPL).where(
                RealizedPL.user_id == user_id,
                RealizedPL.transaction_id == transaction_id,
            )
        )
        record = result.scalar_one_or_none()

        if not record:
            return {
                "content": "No realized P/L record found for this transaction.",
                "generation_mode": "RuleBased",
                "realized_pl": None,
                "holding_days": None,
            }

        content = self._rule_based_trade_review(record)

        return {
            "content": content,
            "generation_mode": "RuleBased",
            "realized_pl": str(record.realized_pl),
            "holding_days": record.hold_duration_days,
        }

    def _rule_based_memo(self, context: dict) -> str:
        """Generate a rule-based weekly memo from portfolio context."""
        lines = ["## Weekly Portfolio Memo", ""]

        # Performance summary
        total_value = context.get("total_value", Decimal("0"))
        total_cost = context.get("total_cost", Decimal("0"))
        unrealized = total_value - total_cost if total_value and total_cost else Decimal("0")
        roi = (unrealized / total_cost * 100) if total_cost > 0 else Decimal("0")

        lines.append(f"**Portfolio Value:** ${total_value:,.2f}")
        lines.append(f"**Total Cost:** ${total_cost:,.2f}")
        lines.append(f"**Unrealized P/L:** ${unrealized:,.2f} ({roi:+.1f}%)")
        lines.append("")

        # Position count
        position_count = context.get("position_count", 0)
        lines.append(f"**Active Positions:** {position_count}")
        lines.append("")

        # Recent trades
        recent_trades = context.get("recent_trades", 0)
        if recent_trades > 0:
            lines.append(f"**Trades This Week:** {recent_trades}")
        else:
            lines.append("**Trades This Week:** None — consider reviewing watchlist opportunities.")
        lines.append("")

        # Suggested actions
        lines.append("### Suggested Actions")
        if position_count == 0:
            lines.append("- Portfolio is empty. Consider adding your first position or importing snapshots.")
        else:
            if roi < -10:
                lines.append("- Portfolio is down significantly. Review thesis for losing positions.")
            if position_count < 5:
                lines.append("- Low diversification. Consider adding positions in different sectors.")
            lines.append("- Review any triggered alerts and watchlist near-target opportunities.")

        lines.append("")
        lines.append("*This memo was generated by rule-based analysis. Enable AI provider for more detailed insights.*")

        return "\n".join(lines)

    def _rule_based_trade_review(self, record: RealizedPL) -> str:
        """Generate a rule-based trade review from realized P/L record."""
        pl = record.realized_pl
        days = record.hold_duration_days
        symbol = record.stock_symbol
        outcome = "profitable" if pl > 0 else "unprofitable"
        term = record.term_type

        lines = [
            f"## Trade Review: {symbol}",
            "",
            f"**Outcome:** {'✅ Gain' if pl > 0 else '❌ Loss'} of ${abs(pl):,.2f}",
            f"**Holding Period:** {days} days ({term})",
            "",
        ]

        # Analysis
        if pl > 0:
            if days < 30:
                lines.append("Quick profitable exit. Consider whether you left gains on the table.")
            elif days > 365:
                lines.append("Long-term winner. Patient holding paid off.")
            else:
                lines.append("Solid medium-term trade. Review if exit timing matched your original plan.")
        else:
            if days > 180:
                lines.append("Extended holding of a losing position. Was the original thesis still valid?")
            elif days < 14:
                lines.append("Quick exit on a loss. Good discipline if thesis broke early.")
            else:
                lines.append("Loss within reasonable holding period. Review what changed from entry thesis.")

        lines.append("")
        lines.append("*This review was generated by rule-based analysis.*")

        return "\n".join(lines)

    async def _build_memo_context(self, user_id: uuid.UUID) -> dict:
        """Build context data for memo generation."""
        # Get position count and total cost
        result = await self.db.execute(
            select(
                func.count(Transaction.stock_symbol.distinct()),
                func.sum(Transaction.gross_value),
            ).where(
                Transaction.user_id == user_id,
                Transaction.action.in_(["Buy", "Snapshot"]),
            )
        )
        row = result.one_or_none()
        position_count = row[0] if row else 0
        total_cost = row[1] if row and row[1] else Decimal("0")

        # Recent trade count (last 7 days)
        week_ago = date.today().replace(day=max(1, date.today().day - 7))
        recent_count = await self.db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == user_id,
                Transaction.date >= week_ago,
            )
        )

        return {
            "total_value": total_cost,  # Approximate without market data
            "total_cost": total_cost,
            "position_count": position_count,
            "recent_trades": recent_count or 0,
            "warnings": [],
        }
