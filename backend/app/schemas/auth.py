"""Pydantic schemas for authentication and user management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .enums import UserStatus


class UserResponse(BaseModel):
    """Schema for user info response."""

    id: str
    display_name: str
    email: str
    profile_picture_url: Optional[str] = None
    oauth_provider: str
    status: UserStatus
    is_admin: bool
    registered_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserStatusUpdate(BaseModel):
    """Schema for updating user status (admin action)."""

    status: UserStatus


class UserListResponse(BaseModel):
    """Schema for admin user list response."""

    users: list[UserResponse]
    total: int
