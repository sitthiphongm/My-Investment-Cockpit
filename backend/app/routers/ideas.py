"""Investment Ideas API routes."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_user_id
from app.models.user import User
from app.schemas.enums import IdeaStatus, RiskLevel
from app.schemas.ideas import (
    IdeaCreate,
    IdeaFilters,
    IdeaListResponse,
    IdeaResponse,
    IdeaUpdate,
)
from app.services.ideas_service import IdeasService

router = APIRouter(prefix="/api/ideas", tags=["ideas"])


def _build_response(idea) -> IdeaResponse:
    """Build an IdeaResponse from an InvestmentIdea model."""
    return IdeaResponse(
        id=str(idea.id),
        stock_symbol=idea.stock_symbol,
        title=idea.title,
        thesis=idea.thesis,
        target_entry_price=idea.target_entry_price,
        risk_level=RiskLevel(idea.risk_level),
        source_link=idea.source_link,
        status=IdeaStatus(idea.status),
        linked_transaction_id=str(idea.linked_transaction_id) if idea.linked_transaction_id else None,
        created_at=idea.created_at,
        updated_at=idea.updated_at,
    )


@router.post("", response_model=IdeaResponse, status_code=201)
async def create_idea(
    data: IdeaCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new investment idea.

    Records a thesis/idea for a stock with risk level, target entry price,
    and optional source link.
    """
    service = IdeasService(db)
    idea = await service.create_idea(user.id, data)
    return _build_response(idea)


@router.get("", response_model=IdeaListResponse)
async def list_ideas(
    status: Optional[IdeaStatus] = Query(None, description="Filter by idea status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    stock_symbol: Optional[str] = Query(None, description="Filter by stock symbol"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all investment ideas sorted by updated_at descending.

    Supports filtering by status, risk_level, and stock_symbol.
    """
    filters = IdeaFilters(
        status=status,
        risk_level=risk_level,
        stock_symbol=stock_symbol,
    )
    service = IdeasService(db)
    ideas = await service.list_ideas(user_id, filters)
    return IdeaListResponse(ideas=[_build_response(idea) for idea in ideas])


@router.put("/{idea_id}", response_model=IdeaResponse)
async def update_idea(
    idea_id: uuid.UUID,
    data: IdeaUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an investment idea.

    Allows modifying any field. When status is set to "Bought", a
    linked_transaction_id can be provided to link the idea to a transaction.

    Returns 404 if the idea does not exist or does not belong to the user.
    Returns 400 if linked_transaction_id is set but status is not "Bought".
    """
    service = IdeasService(db)
    idea = await service.update_idea(user.id, idea_id, data)
    return _build_response(idea)


@router.delete("/{idea_id}", status_code=204)
async def delete_idea(
    idea_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an investment idea.

    Returns 404 if the idea does not exist or does not belong to the user.
    """
    service = IdeasService(db)
    await service.delete_idea(user.id, idea_id)
