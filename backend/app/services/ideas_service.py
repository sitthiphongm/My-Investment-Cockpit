"""Investment Ideas service - Business logic for thesis board operations."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investment_idea import InvestmentIdea
from app.schemas.enums import IdeaStatus
from app.schemas.ideas import IdeaCreate, IdeaFilters, IdeaUpdate


class IdeasService:
    """Service for managing a user's investment ideas (thesis board).

    Provides CRUD operations for investment ideas with filtering by status,
    risk level, and stock symbol. Supports linking an idea to a transaction
    when the idea status transitions to "Bought".

    All operations are scoped to a specific user_id for data isolation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_idea(
        self, user_id: uuid.UUID, data: IdeaCreate
    ) -> InvestmentIdea:
        """Create a new investment idea.

        Args:
            user_id: The authenticated user's ID.
            data: Validated idea creation data.

        Returns:
            The newly created InvestmentIdea record.
        """
        idea = InvestmentIdea(
            id=uuid.uuid4(),
            user_id=user_id,
            stock_symbol=data.stock_symbol,
            title=data.title,
            thesis=data.thesis,
            target_entry_price=data.target_entry_price,
            risk_level=data.risk_level.value,
            source_link=data.source_link,
            status=data.status.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(idea)
        await self.db.flush()
        await self.db.refresh(idea)
        return idea

    async def list_ideas(
        self, user_id: uuid.UUID, filters: Optional[IdeaFilters] = None
    ) -> list[InvestmentIdea]:
        """List all investment ideas for a user, sorted by updated_at descending.

        Supports optional filtering by status, risk_level, and stock_symbol.

        Args:
            user_id: The authenticated user's ID.
            filters: Optional filters (status, risk_level, stock_symbol).

        Returns:
            List of InvestmentIdea records matching the filters.
        """
        stmt = (
            select(InvestmentIdea)
            .where(InvestmentIdea.user_id == user_id)
        )

        if filters:
            if filters.status is not None:
                stmt = stmt.where(InvestmentIdea.status == filters.status.value)
            if filters.risk_level is not None:
                stmt = stmt.where(InvestmentIdea.risk_level == filters.risk_level.value)
            if filters.stock_symbol is not None:
                stmt = stmt.where(InvestmentIdea.stock_symbol == filters.stock_symbol)

        stmt = stmt.order_by(InvestmentIdea.updated_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_idea(
        self, user_id: uuid.UUID, idea_id: uuid.UUID, data: IdeaUpdate
    ) -> InvestmentIdea:
        """Update an existing investment idea.

        When status is set to "Bought", the linked_transaction_id field can also
        be set to link the idea to a specific transaction.

        Args:
            user_id: The authenticated user's ID.
            idea_id: The idea ID to update.
            data: Update data with optional fields.

        Returns:
            The updated InvestmentIdea record.

        Raises:
            HTTPException(404): If the idea does not exist or does not belong to the user.
            HTTPException(400): If linked_transaction_id is set but status is not "Bought".
        """
        idea = await self._get_idea_or_404(user_id, idea_id)

        # Determine the effective status after update
        effective_status = data.status.value if data.status is not None else idea.status

        # Validate linked_transaction_id only allowed when status is "Bought"
        if data.linked_transaction_id is not None and effective_status != IdeaStatus.BOUGHT.value:
            raise HTTPException(
                status_code=400,
                detail="linked_transaction_id can only be set when status is 'Bought'",
            )

        # Apply updates for fields that are provided
        if data.stock_symbol is not None:
            idea.stock_symbol = data.stock_symbol
        if data.title is not None:
            idea.title = data.title
        if data.thesis is not None:
            idea.thesis = data.thesis
        if data.target_entry_price is not None:
            idea.target_entry_price = data.target_entry_price
        if data.risk_level is not None:
            idea.risk_level = data.risk_level.value
        if data.source_link is not None:
            idea.source_link = data.source_link
        if data.status is not None:
            idea.status = data.status.value
        if data.linked_transaction_id is not None:
            idea.linked_transaction_id = uuid.UUID(data.linked_transaction_id)

        idea.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(idea)
        return idea

    async def delete_idea(self, user_id: uuid.UUID, idea_id: uuid.UUID) -> None:
        """Delete an investment idea.

        Args:
            user_id: The authenticated user's ID.
            idea_id: The idea ID to delete.

        Raises:
            HTTPException(404): If the idea does not exist or does not belong to the user.
        """
        idea = await self._get_idea_or_404(user_id, idea_id)
        await self.db.delete(idea)
        await self.db.flush()

    async def _get_idea_or_404(
        self, user_id: uuid.UUID, idea_id: uuid.UUID
    ) -> InvestmentIdea:
        """Fetch an idea by ID, ensuring it belongs to the given user.

        Raises:
            HTTPException(404): If the idea is not found.
        """
        stmt = select(InvestmentIdea).where(
            InvestmentIdea.id == idea_id,
            InvestmentIdea.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        idea = result.scalar_one_or_none()
        if idea is None:
            raise HTTPException(
                status_code=404,
                detail="Investment idea not found",
            )
        return idea
