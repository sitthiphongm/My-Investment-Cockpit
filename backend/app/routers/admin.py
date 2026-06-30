"""Admin router with user management endpoints protected by admin-only guard."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import UserListResponse, UserResponse, UserStatusUpdate
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Cookie name must match auth router
SESSION_COOKIE_NAME = "session_token"


async def get_current_admin_user(
    request: Request, db: AsyncSession = Depends(get_db)
):
    """Dependency that extracts and validates the current user, ensuring they are an admin.

    Raises:
        HTTPException 401: If the user is not authenticated.
        HTTPException 403: If the user is not an admin (ACCESS_DENIED).
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_service = AuthService(db)
    user = await auth_service.validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if not user.is_admin:
        raise HTTPException(status_code=403, detail="ACCESS_DENIED")

    return user


@router.get("/users", response_model=UserListResponse)
async def list_users(
    _admin=Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users (admin only)."""
    admin_service = AdminService(db)
    users, total = await admin_service.list_users()

    return UserListResponse(
        users=[
            UserResponse(
                id=str(u.id),
                display_name=u.display_name,
                email=u.email,
                profile_picture_url=u.profile_picture_url,
                oauth_provider=u.oauth_provider,
                status=u.status,
                is_admin=u.is_admin,
                registered_at=u.registered_at,
                last_login_at=u.last_login_at,
            )
            for u in users
        ],
        total=total,
    )


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: uuid.UUID,
    _admin=Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a user, granting them full access (admin only)."""
    admin_service = AdminService(db)
    user = await admin_service.approve_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        display_name=user.display_name,
        email=user.email,
        profile_picture_url=user.profile_picture_url,
        oauth_provider=user.oauth_provider,
        status=user.status,
        is_admin=user.is_admin,
        registered_at=user.registered_at,
        last_login_at=user.last_login_at,
    )


@router.post("/users/{user_id}/block", response_model=UserResponse)
async def block_user(
    user_id: uuid.UUID,
    _admin=Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Block a user, revoking their access (admin only)."""
    admin_service = AdminService(db)
    user = await admin_service.block_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        display_name=user.display_name,
        email=user.email,
        profile_picture_url=user.profile_picture_url,
        oauth_provider=user.oauth_provider,
        status=user.status,
        is_admin=user.is_admin,
        registered_at=user.registered_at,
        last_login_at=user.last_login_at,
    )


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def set_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    _admin=Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a user's status to any valid value (admin only)."""
    admin_service = AdminService(db)
    try:
        user = await admin_service.set_user_status(user_id, body.status.value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        display_name=user.display_name,
        email=user.email,
        profile_picture_url=user.profile_picture_url,
        oauth_provider=user.oauth_provider,
        status=user.status,
        is_admin=user.is_admin,
        registered_at=user.registered_at,
        last_login_at=user.last_login_at,
    )
