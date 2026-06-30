"""FastAPI dependency injection for authentication and authorization.

Provides reusable dependencies that extract the authenticated user from the session
cookie, enforce account status rules, and support per-user data isolation.

Dependencies:
    - get_current_user: Validates session cookie, returns User or raises 401.
    - get_current_active_user: Ensures user is Approved (blocks Pending/Blocked).
    - get_admin_user: Ensures user is an Approved admin.
    - get_current_user_id: Convenience to extract user_id for per-user data queries.
"""

import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService

# Name of the HTTP-only cookie that holds the session token
SESSION_COOKIE_NAME = "session_token"


async def get_current_user(
    session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the session token from cookie, returning the User.

    Raises HTTPException 401 if:
    - No session cookie is present
    - The session token is invalid or expired
    """
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(db)
    user = await auth_service.validate_session(session_token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user has an active (Approved) account.

    Raises HTTPException 403 if:
    - User status is "Pending" → error code PENDING_APPROVAL
    - User status is "Blocked" → error code ACCOUNT_BLOCKED
    """
    if user.status == "Pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PENDING_APPROVAL",
        )

    if user.status == "Blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ACCOUNT_BLOCKED",
        )

    return user


async def get_admin_user(
    user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the authenticated user is an admin.

    Depends on get_current_active_user so the user must also be Approved.

    Raises HTTPException 403 if the user is not an admin.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ACCESS_DENIED",
        )

    return user


async def get_current_user_id(
    current_user: User = Depends(get_current_active_user),
) -> uuid.UUID:
    """Convenience dependency that returns the user_id for per-user data queries.

    This enables per-user data isolation by providing the authenticated user's ID
    to route handlers, ensuring all data queries filter by user_id without relying
    on request parameters that could be tampered with.
    """
    return current_user.id
