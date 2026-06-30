"""Pydantic schemas for stock tags and categories."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    """Schema for creating a custom tag."""

    name: str = Field(min_length=1, max_length=50)


class TagResponse(BaseModel):
    """Schema for tag response."""

    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    """Schema for listing tags."""

    tags: list[TagResponse]


class StockTagsUpdate(BaseModel):
    """Schema for assigning tags to a stock symbol."""

    tag_ids: list[str]


class StockWithTagsResponse(BaseModel):
    """Schema for a stock that has a specific tag assigned."""

    stock_symbol: str
    tag_id: str
    tag_name: str


class StocksByTagResponse(BaseModel):
    """Schema for listing stocks associated with a tag."""

    tag_id: str
    tag_name: str
    stocks: list[str]


class TagPerformanceItem(BaseModel):
    """Performance metrics for a single tag."""

    tag_id: str
    tag_name: str
    total_cost: Decimal
    total_market_value: Optional[Decimal] = None
    unrealized_pl: Optional[Decimal] = None
    roi_percent: Optional[Decimal] = None
    stock_count: int


class TagPerformanceResponse(BaseModel):
    """Schema for aggregated performance per tag."""

    tags: list[TagPerformanceItem]
