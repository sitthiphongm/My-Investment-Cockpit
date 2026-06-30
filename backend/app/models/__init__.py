"""Data Access Layer - SQLAlchemy ORM models."""

from app.models.dividend_record import DividendRecord
from app.models.investment_idea import InvestmentIdea
from app.models.performance_snapshot import PerformanceSnapshot
from app.models.price_alert import PriceAlert
from app.models.realized_pl import RealizedPL
from app.models.screener_preset import ScreenerPreset
from app.models.session import Session
from app.models.stock_sentiment import StockSentiment
from app.models.stock_tag_assignment import StockTagAssignment
from app.models.tag import Tag, TransactionTag
from app.models.target_allocation import TargetAllocation
from app.models.transaction import Transaction
from app.models.transaction_note import TransactionNote
from app.models.transfer import Transfer
from app.models.user import User
from app.models.watchlist_item import WatchlistItem

# New models for v2 (Premium Investment Cockpit)
from app.models.alert_history import AlertHistory
from app.models.cash_adjustment import CashAdjustment
from app.models.fx_rate_entry import FXRateEntry
from app.models.tax_lot import TaxLot
from app.models.thesis_break_condition import ThesisBreakCondition

__all__ = [
    "AlertHistory",
    "CashAdjustment",
    "DividendRecord",
    "FXRateEntry",
    "InvestmentIdea",
    "PerformanceSnapshot",
    "PriceAlert",
    "RealizedPL",
    "ScreenerPreset",
    "Session",
    "StockSentiment",
    "StockTagAssignment",
    "Tag",
    "TargetAllocation",
    "TaxLot",
    "ThesisBreakCondition",
    "Transaction",
    "TransactionNote",
    "TransactionTag",
    "Transfer",
    "User",
    "WatchlistItem",
]
