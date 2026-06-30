"""Pydantic schemas for request/response validation."""

from .enums import (
    ActionType,
    AlertType,
    Currency,
    IdeaStatus,
    RiskLevel,
    SentimentType,
    TargetType,
    TermType,
    TransferType,
    UserStatus,
)
from .transactions import (
    SnapshotCreate as SnapshotImportCreate,
    SnapshotEntry,
    TransactionCreate,
    TransactionFilters,
    TransactionResponse,
    TransactionUpdate,
)
from .transfers import (
    TransferCreate,
    TransferFilters,
    TransferResponse,
    TransferUpdate,
)
from .portfolio import (
    PortfolioPositionResponse,
    PortfolioSummaryResponse,
    SectorHeatmapEntry,
    SectorHeatmapResponse,
    SentimentUpdate,
)
from .dashboard import (
    BrokerCapital,
    DashboardResponse,
)
from .performance import (
    CumulativeReturnResponse,
    PerformanceListResponse,
    PerformanceSnapshotResponse,
    SnapshotCreate,
    SnapshotFilters,
    SnapshotUpdate,
)
from .auth import (
    UserListResponse,
    UserResponse,
    UserStatusUpdate,
)
from .journal import (
    NoteUpdate,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagsUpdate,
)
from .alerts import (
    AlertCreate,
    AlertListResponse,
    AlertResponse,
)
from .dividends import (
    DividendCreate,
    DividendFilters,
    DividendProjectionEntry,
    DividendProjectionResponse,
    DividendResponse,
    DividendSummaryEntry,
    DividendSummaryResponse,
)
from .watchlist import (
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistResponse,
)
from .ideas import (
    IdeaCreate,
    IdeaFilters,
    IdeaListResponse,
    IdeaResponse,
    IdeaUpdate,
)
from .screener import (
    ScreenerFilterCreate,
    ScreenerPresetCreate,
    ScreenerPresetListResponse,
    ScreenerPresetResponse,
    ScreenerResultEntry,
    ScreenerSearchResponse,
)
from .rebalancing import (
    ConcentrationWarning,
    RebalancingPositionResponse,
    RebalancingResponse,
    RiskMetricsResponse,
    SectorConcentrationEntry,
    TargetAllocationEntry,
    TargetAllocationUpdate,
)
from .realized_pl import (
    RealizedPLFilters,
    RealizedPLListResponse,
    RealizedPLResponse,
    RealizedPLSummaryEntry,
    RealizedPLSummaryResponse,
)

__all__ = [
    # Enums
    "ActionType",
    "AlertType",
    "Currency",
    "IdeaStatus",
    "RiskLevel",
    "SentimentType",
    "TargetType",
    "TermType",
    "TransferType",
    "UserStatus",
    # Transactions
    "SnapshotEntry",
    "SnapshotImportCreate",
    "TransactionCreate",
    "TransactionFilters",
    "TransactionResponse",
    "TransactionUpdate",
    # Transfers
    "TransferCreate",
    "TransferFilters",
    "TransferResponse",
    "TransferUpdate",
    # Portfolio
    "PortfolioPositionResponse",
    "PortfolioSummaryResponse",
    "SectorHeatmapEntry",
    "SectorHeatmapResponse",
    "SentimentUpdate",
    # Dashboard
    "BrokerCapital",
    "DashboardResponse",
    # Performance
    "CumulativeReturnResponse",
    "PerformanceListResponse",
    "PerformanceSnapshotResponse",
    "SnapshotCreate",
    "SnapshotFilters",
    "SnapshotUpdate",
    # Auth
    "UserListResponse",
    "UserResponse",
    "UserStatusUpdate",
    # Journal
    "NoteUpdate",
    "TagCreate",
    "TagListResponse",
    "TagResponse",
    "TagsUpdate",
    # Alerts
    "AlertCreate",
    "AlertListResponse",
    "AlertResponse",
    # Dividends
    "DividendCreate",
    "DividendFilters",
    "DividendProjectionEntry",
    "DividendProjectionResponse",
    "DividendResponse",
    "DividendSummaryEntry",
    "DividendSummaryResponse",
    # Watchlist
    "WatchlistItemCreate",
    "WatchlistItemResponse",
    "WatchlistItemUpdate",
    "WatchlistResponse",
    # Ideas
    "IdeaCreate",
    "IdeaFilters",
    "IdeaListResponse",
    "IdeaResponse",
    "IdeaUpdate",
    # Screener
    "ScreenerFilterCreate",
    "ScreenerPresetCreate",
    "ScreenerPresetListResponse",
    "ScreenerPresetResponse",
    "ScreenerResultEntry",
    "ScreenerSearchResponse",
    # Rebalancing
    "ConcentrationWarning",
    "RebalancingPositionResponse",
    "RebalancingResponse",
    "RiskMetricsResponse",
    "SectorConcentrationEntry",
    "TargetAllocationEntry",
    "TargetAllocationUpdate",
    # Realized P/L
    "RealizedPLFilters",
    "RealizedPLListResponse",
    "RealizedPLResponse",
    "RealizedPLSummaryEntry",
    "RealizedPLSummaryResponse",
]
