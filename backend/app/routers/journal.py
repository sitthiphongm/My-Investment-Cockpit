"""Trade journal API routes for notes, tags, and journal views."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.journal import (
    NoteUpdate,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagsUpdate,
)
from app.services.journal_service import JournalService

router = APIRouter(tags=["journal"])


# --- Notes on transactions ---


@router.put("/api/transactions/{transaction_id}/notes")
async def attach_note(
    transaction_id: uuid.UUID,
    data: NoteUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Attach or update a note on a transaction (max 1000 chars)."""
    service = JournalService(db)
    note = await service.attach_note(user_id, transaction_id, data.note)
    return {
        "id": str(note.id),
        "transaction_id": str(note.transaction_id),
        "note": note.note,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


# --- Tags on transactions ---


@router.put("/api/transactions/{transaction_id}/tags")
async def set_transaction_tags(
    transaction_id: uuid.UUID,
    data: TagsUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set tags on a transaction (replaces existing tags)."""
    service = JournalService(db)
    tags = await service.set_tags(user_id, transaction_id, data.tag_ids)
    return {
        "transaction_id": str(transaction_id),
        "tags": [
            {
                "id": str(tag.id),
                "name": tag.name,
            }
            for tag in tags
        ],
    }


# --- Journal tag management ---


@router.get("/api/journal/tags")
async def list_journal_tags(
    include_predefined: bool = Query(True, description="Include predefined tags"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all user tags (custom + predefined) with optional filtering."""
    service = JournalService(db)
    tags = await service.list_tags(user_id, include_predefined=include_predefined)
    return {"tags": tags}


@router.post("/api/journal/tags", status_code=201)
async def create_tag(
    data: TagCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom tag (1-50 characters, unique per user case-insensitive)."""
    service = JournalService(db)
    tag = await service.create_tag(user_id, data.name)
    return {
        "id": str(tag.id),
        "name": tag.name,
        "created_at": tag.created_at,
    }


@router.delete("/api/journal/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom tag."""
    service = JournalService(db)
    await service.delete_tag(user_id, tag_id)
