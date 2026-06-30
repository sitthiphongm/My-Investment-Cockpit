"""Pydantic schemas for trade journal (notes and tags)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NoteUpdate(BaseModel):
    """Schema for attaching or updating a note on a transaction."""

    note: str = Field(max_length=1000)


class TagCreate(BaseModel):
    """Schema for creating a custom tag."""

    name: str = Field(min_length=1, max_length=50)

    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Tag name cannot be blank")
        return v.strip()


class TagResponse(BaseModel):
    """Schema for tag response."""

    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TagsUpdate(BaseModel):
    """Schema for setting tags on a transaction."""

    tag_ids: list[str]


class TagListResponse(BaseModel):
    """Schema for tag list response."""

    tags: list[TagResponse]
