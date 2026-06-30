"""Shared enumerations for the Investment History application."""

from enum import Enum


class ActionType(str, Enum):
    """Transaction action types."""

    BUY = "Buy"
    SELL = "Sell"
    SNAPSHOT = "Snapshot"


class TransferType(str, Enum):
    """Money transfer direction types."""

    IN = "In"
    OUT = "Out"


class Currency(str, Enum):
    """Supported currencies for transfers."""

    THB = "THB"
    USD = "USD"


class AlertType(str, Enum):
    """Price alert trigger types."""

    ABOVE = "Above"
    BELOW = "Below"


class RiskLevel(str, Enum):
    """Investment idea risk levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class IdeaStatus(str, Enum):
    """Investment idea lifecycle statuses."""

    RESEARCHING = "Researching"
    WATCHING = "Watching"
    BOUGHT = "Bought"
    PASSED = "Passed"
    CLOSED = "Closed"


class UserStatus(str, Enum):
    """User account statuses."""

    APPROVED = "Approved"
    PENDING = "Pending"
    BLOCKED = "Blocked"


class SentimentType(str, Enum):
    """Portfolio position sentiment types."""

    BEAR = "Bear"
    BULL = "Bull"


class TermType(str, Enum):
    """Realized P/L holding period classification."""

    SHORT_TERM = "Short-term"
    LONG_TERM = "Long-term"


class TargetType(str, Enum):
    """Target allocation category types."""

    SYMBOL = "Symbol"
    SECTOR = "Sector"
