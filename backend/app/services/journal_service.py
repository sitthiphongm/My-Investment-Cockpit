"""Trade journal service - Business logic for notes and tags on transactions."""

import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tag import Tag, TransactionTag
from app.models.transaction import Transaction
from app.models.transaction_note import TransactionNote


# Predefined tags available to all users
PREDEFINED_TAGS = [
    "Earnings Play",
    "Momentum",
    "Value",
    "Dividend",
    "Speculative",
    "Technical",
]


class JournalService:
    """Service for managing trade journal notes and tags."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def attach_note(
        self, user_id: uuid.UUID, transaction_id: uuid.UUID, note_text: str
    ) -> TransactionNote:
        """Attach or update a note on a transaction.

        - Verify transaction belongs to user
        - Max 1000 characters
        - One note per transaction (upsert)
        """
        if len(note_text) > 1000:
            raise HTTPException(
                status_code=400,
                detail="Note must be at most 1000 characters.",
            )

        if not note_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Note cannot be empty.",
            )

        # Verify transaction belongs to user
        transaction = await self._get_user_transaction(user_id, transaction_id)

        # Check if note already exists
        stmt = select(TransactionNote).where(
            TransactionNote.transaction_id == transaction_id
        )
        result = await self.db.execute(stmt)
        existing_note = result.scalar_one_or_none()

        if existing_note:
            existing_note.note = note_text
            await self.db.flush()
            await self.db.refresh(existing_note)
            return existing_note
        else:
            new_note = TransactionNote(
                id=uuid.uuid4(),
                transaction_id=transaction_id,
                note=note_text,
            )
            self.db.add(new_note)
            await self.db.flush()
            await self.db.refresh(new_note)
            return new_note

    async def set_tags(
        self, user_id: uuid.UUID, transaction_id: uuid.UUID, tag_ids: list[str]
    ) -> list[Tag]:
        """Set tags on a transaction (replaces existing tags).

        - Verify transaction belongs to user
        - Verify all tag_ids belong to user
        - Replace all existing transaction tags
        """
        # Verify transaction belongs to user
        transaction = await self._get_user_transaction(user_id, transaction_id)

        # Remove existing transaction tags
        stmt = select(TransactionTag).where(
            TransactionTag.transaction_id == transaction_id
        )
        result = await self.db.execute(stmt)
        existing_tags = result.scalars().all()
        for tt in existing_tags:
            await self.db.delete(tt)

        if not tag_ids:
            await self.db.flush()
            return []

        # Verify all tags belong to user
        tag_uuids = []
        for tid in tag_ids:
            try:
                tag_uuids.append(uuid.UUID(tid))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tag ID: {tid}",
                )

        stmt = select(Tag).where(Tag.id.in_(tag_uuids), Tag.user_id == user_id)
        result = await self.db.execute(stmt)
        valid_tags = list(result.scalars().all())

        if len(valid_tags) != len(tag_uuids):
            raise HTTPException(
                status_code=400,
                detail="One or more tag IDs are invalid or do not belong to user.",
            )

        # Create new transaction tag associations
        for tag in valid_tags:
            tt = TransactionTag(
                transaction_id=transaction_id,
                tag_id=tag.id,
            )
            self.db.add(tt)

        await self.db.flush()
        return valid_tags

    async def create_tag(self, user_id: uuid.UUID, name: str) -> Tag:
        """Create a custom tag for the user.

        - Name must be 1-50 characters
        - Unique per user (case-insensitive)
        """
        name = name.strip()
        if not name or len(name) < 1 or len(name) > 50:
            raise HTTPException(
                status_code=400,
                detail="Tag name must be between 1 and 50 characters.",
            )

        # Check uniqueness (case-insensitive)
        stmt = select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == name.lower(),
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Tag '{name}' already exists.",
            )

        tag = Tag(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
        )
        self.db.add(tag)
        await self.db.flush()
        await self.db.refresh(tag)
        return tag

    async def delete_tag(self, user_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        """Delete a user's tag.

        - Removes the tag and all associations (cascade in DB)
        """
        stmt = select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
        result = await self.db.execute(stmt)
        tag = result.scalar_one_or_none()

        if tag is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tag {tag_id} not found.",
            )

        await self.db.delete(tag)
        await self.db.flush()

    async def list_tags(
        self, user_id: uuid.UUID, include_predefined: bool = True
    ) -> list[dict]:
        """List all user tags, optionally including predefined tags.

        Returns both user-created tags and predefined tags.
        """
        # Get user's custom tags
        stmt = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
        result = await self.db.execute(stmt)
        user_tags = list(result.scalars().all())

        tags_list = []

        # Add predefined tags (available to all users)
        if include_predefined:
            for name in PREDEFINED_TAGS:
                tags_list.append({
                    "id": None,
                    "name": name,
                    "is_predefined": True,
                    "created_at": None,
                })

        # Add user's custom tags
        for tag in user_tags:
            tags_list.append({
                "id": str(tag.id),
                "name": tag.name,
                "is_predefined": False,
                "created_at": tag.created_at,
            })

        return tags_list

    async def get_user_tags(self, user_id: uuid.UUID) -> list[Tag]:
        """Get all tags owned by a user."""
        stmt = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_transactions_by_tag(
        self, user_id: uuid.UUID, tag_name: str
    ) -> list[Transaction]:
        """List transactions filtered by a specific tag name.

        Supports both predefined and custom tags (case-insensitive).
        """
        # Find the tag by name (case-insensitive)
        stmt = select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == tag_name.lower(),
        )
        result = await self.db.execute(stmt)
        tag = result.scalar_one_or_none()

        if tag is None:
            # Return empty list if tag doesn't exist
            return []

        # Find transactions with this tag
        stmt = (
            select(Transaction)
            .join(TransactionTag, TransactionTag.transaction_id == Transaction.id)
            .where(
                Transaction.user_id == user_id,
                TransactionTag.tag_id == tag.id,
            )
            .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_user_transaction(
        self, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Transaction:
        """Get a transaction by ID, verifying it belongs to the user."""
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        transaction = result.scalar_one_or_none()
        if transaction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction {transaction_id} not found.",
            )
        return transaction
