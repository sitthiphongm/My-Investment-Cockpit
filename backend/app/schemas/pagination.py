"""Pagination schemas for API responses."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""

    offset: int = 0
    limit: int = 50


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""

    items: list
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + self.limit < self.total
