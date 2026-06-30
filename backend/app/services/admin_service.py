"""Admin service for user management operations."""

import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class AdminService:
    """Service for admin user management: list, approve, block, and status changes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self) -> tuple[list[User], int]:
        """List all registered users with total count.

        Returns:
            Tuple of (list of users, total count)
        """
        count_stmt = select(func.count()).select_from(User)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = select(User).order_by(User.registered_at.desc())
        result = await self.db.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a user by their ID.

        Returns:
            The user if found, otherwise None.
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def approve_user(self, user_id: uuid.UUID) -> Optional[User]:
        """Set a user's status to Approved.

        Returns:
            The updated user, or None if not found.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        user.status = "Approved"
        await self.db.flush()
        return user

    async def block_user(self, user_id: uuid.UUID) -> Optional[User]:
        """Set a user's status to Blocked.

        Returns:
            The updated user, or None if not found.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        user.status = "Blocked"
        await self.db.flush()
        return user

    async def set_user_status(self, user_id: uuid.UUID, status: str) -> Optional[User]:
        """Set a user's status to an arbitrary valid status.

        Args:
            user_id: The user's UUID.
            status: One of "Approved", "Pending", or "Blocked".

        Returns:
            The updated user, or None if not found.
        """
        valid_statuses = {"Approved", "Pending", "Blocked"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        user.status = status
        await self.db.flush()
        return user
