"""Authentication router with OAuth login/callback, logout, and user info endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.auth import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Cookie settings
SESSION_COOKIE_NAME = "session_token"
SESSION_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


def _set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie with secure HTTP-only settings."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,  # Secure in production, not in debug
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
    )


# ------------------------------------------------------------------
# OAuth login initiation
# ------------------------------------------------------------------


@router.get("/login/google")
async def login_google(request: Request, db: AsyncSession = Depends(get_db)):
    """Initiate Google OAuth login flow."""
    auth_service = AuthService(db)
    url, state = auth_service.get_authorization_url("google")
    # Store state in a temporary cookie for CSRF protection
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,  # 10 minutes
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        path="/",
    )
    return response


@router.get("/login/facebook")
async def login_facebook(request: Request, db: AsyncSession = Depends(get_db)):
    """Initiate Facebook OAuth login flow."""
    auth_service = AuthService(db)
    url, state = auth_service.get_authorization_url("facebook")
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        path="/",
    )
    return response


# ------------------------------------------------------------------
# OAuth callbacks
# ------------------------------------------------------------------


@router.get("/callback/google")
async def callback_google(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback."""
    # Check for OAuth errors
    error = request.query_params.get("error")
    if error:
        error_description = request.query_params.get(
            "error_description", "Authentication failed"
        )
        # Redirect to frontend login with error
        return RedirectResponse(
            url=f"{settings.cors_origins[0]}/login?error={error_description}",
            status_code=302,
        )

    auth_service = AuthService(db)
    try:
        user, session_token = await auth_service.handle_callback(
            provider="google",
            authorization_response_url=str(request.url),
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.cors_origins[0]}/login?error=Authentication+failed",
            status_code=302,
        )

    # Set session cookie and redirect to frontend
    response = RedirectResponse(
        url=f"{settings.cors_origins[0]}/", status_code=302
    )
    _set_session_cookie(response, session_token)
    # Clean up OAuth state cookie
    response.delete_cookie(key="oauth_state", path="/")
    return response


@router.get("/callback/facebook")
async def callback_facebook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Facebook OAuth callback."""
    error = request.query_params.get("error")
    if error:
        error_description = request.query_params.get(
            "error_description", "Authentication failed"
        )
        return RedirectResponse(
            url=f"{settings.cors_origins[0]}/login?error={error_description}",
            status_code=302,
        )

    auth_service = AuthService(db)
    try:
        user, session_token = await auth_service.handle_callback(
            provider="facebook",
            authorization_response_url=str(request.url),
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.cors_origins[0]}/login?error=Authentication+failed",
            status_code=302,
        )

    response = RedirectResponse(
        url=f"{settings.cors_origins[0]}/", status_code=302
    )
    _set_session_cookie(response, session_token)
    response.delete_cookie(key="oauth_state", path="/")
    return response


# ------------------------------------------------------------------
# Session endpoints
# ------------------------------------------------------------------


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Terminate the current session and clear the cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        auth_service = AuthService(db)
        await auth_service.logout(token)

    response = Response(status_code=200)
    _clear_session_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Get the currently authenticated user's info."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_service = AuthService(db)
    user = await auth_service.validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

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
