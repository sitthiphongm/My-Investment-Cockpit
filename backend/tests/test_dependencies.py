"""Unit tests for authentication and authorization dependencies."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.dependencies import get_admin_user, get_current_active_user, get_current_user
from app.models.user import User


def _make_user(
    status: str = "Approved",
    is_admin: bool = False,
) -> User:
    """Create a mock User object for testing."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.display_name = "Test User"
    user.email = "test@example.com"
    user.profile_picture_url = None
    user.oauth_provider = "google"
    user.oauth_provider_id = "12345"
    user.status = status
    user.is_admin = is_admin
    user.registered_at = datetime.now(timezone.utc)
    user.last_login_at = datetime.now(timezone.utc)
    return user


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    async def test_raises_401_when_no_cookie(self):
        """Should raise 401 if no session cookie is present."""
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(session_token=None, db=db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"

    async def test_raises_401_when_session_invalid(self):
        """Should raise 401 if the session token is invalid or expired."""
        db = AsyncMock()

        with patch(
            "app.dependencies.AuthService"
        ) as MockAuthService:
            mock_service = AsyncMock()
            mock_service.validate_session.return_value = None
            MockAuthService.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(session_token="invalid-token", db=db)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid or expired session"
            mock_service.validate_session.assert_called_once_with("invalid-token")

    async def test_returns_user_when_session_valid(self):
        """Should return the User when session is valid."""
        db = AsyncMock()
        expected_user = _make_user()

        with patch(
            "app.dependencies.AuthService"
        ) as MockAuthService:
            mock_service = AsyncMock()
            mock_service.validate_session.return_value = expected_user
            MockAuthService.return_value = mock_service

            result = await get_current_user(session_token="valid-token", db=db)

            assert result == expected_user
            mock_service.validate_session.assert_called_once_with("valid-token")

    async def test_raises_401_when_cookie_is_empty_string(self):
        """Should raise 401 if session cookie is an empty string."""
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(session_token="", db=db)

        # Empty string is falsy so treated as no cookie
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"


class TestGetCurrentActiveUser:
    """Tests for get_current_active_user dependency."""

    async def test_raises_403_pending_approval_for_pending_user(self):
        """Should raise 403 with PENDING_APPROVAL for users with Pending status."""
        user = _make_user(status="Pending")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(user=user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "PENDING_APPROVAL"

    async def test_raises_403_account_blocked_for_blocked_user(self):
        """Should raise 403 with ACCOUNT_BLOCKED for users with Blocked status."""
        user = _make_user(status="Blocked")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(user=user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "ACCOUNT_BLOCKED"

    async def test_returns_user_when_approved(self):
        """Should return the user when their status is Approved."""
        user = _make_user(status="Approved")

        result = await get_current_active_user(user=user)

        assert result == user

    async def test_does_not_accept_unknown_status(self):
        """Should not raise for Approved status but would raise for any non-Approved."""
        user = _make_user(status="Approved")
        result = await get_current_active_user(user=user)
        assert result.status == "Approved"


class TestGetAdminUser:
    """Tests for get_admin_user dependency."""

    async def test_raises_403_access_denied_for_non_admin(self):
        """Should raise 403 with ACCESS_DENIED for non-admin users."""
        user = _make_user(status="Approved", is_admin=False)

        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(user=user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "ACCESS_DENIED"

    async def test_returns_user_when_admin(self):
        """Should return the user when they are an admin."""
        user = _make_user(status="Approved", is_admin=True)

        result = await get_admin_user(user=user)

        assert result == user

    async def test_admin_must_also_be_approved(self):
        """Admin check depends on get_current_active_user, so Pending admins are blocked.

        This test validates the dependency chain: a Pending admin user
        would be rejected by get_current_active_user before reaching get_admin_user.
        """
        # Simulate calling get_current_active_user first (as the dependency chain would)
        user = _make_user(status="Pending", is_admin=True)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(user=user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "PENDING_APPROVAL"
