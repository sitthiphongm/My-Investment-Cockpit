"""Unit tests for AdminService: list users, approve, block, and status changes."""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.user import User
from app.services.admin_service import AdminService


class FakeScalarsResult:
    """Fake scalars() result that supports .all()."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeResult:
    """Fake SQLAlchemy result."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value

    def scalars(self):
        return FakeScalarsResult(self._value if isinstance(self._value, list) else [])


class FakeAsyncSession:
    """A minimal fake async database session for unit testing."""

    def __init__(self):
        self.added = []
        self.deleted = []
        self.flushed = False
        self._execute_results = []

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushed = True

    async def execute(self, stmt):
        if self._execute_results:
            return self._execute_results.pop(0)
        return FakeResult(None)

    def set_execute_results(self, *results):
        """Set a sequence of results for consecutive execute calls."""
        self._execute_results = list(results)


def _make_user(
    status="Pending",
    is_admin=False,
    display_name="Test User",
    email="test@example.com",
) -> User:
    """Helper to create a test User instance."""
    return User(
        id=uuid.uuid4(),
        display_name=display_name,
        email=email,
        profile_picture_url=None,
        oauth_provider="google",
        oauth_provider_id=f"google-{uuid.uuid4().hex[:8]}",
        status=status,
        is_admin=is_admin,
        registered_at=datetime.now(timezone.utc),
        last_login_at=None,
    )


class TestListUsers:
    """Tests for AdminService.list_users."""

    @pytest.mark.asyncio
    async def test_list_users_returns_all_users_and_count(self):
        """list_users should return all users and the total count."""
        user1 = _make_user(display_name="Alice")
        user2 = _make_user(display_name="Bob")

        db = FakeAsyncSession()
        # First execute: count -> 2
        # Second execute: select users -> [user1, user2]
        db.set_execute_results(FakeResult(2), FakeResult([user1, user2]))

        service = AdminService(db)
        users, total = await service.list_users()

        assert total == 2
        assert len(users) == 2
        assert users[0].display_name == "Alice"
        assert users[1].display_name == "Bob"

    @pytest.mark.asyncio
    async def test_list_users_empty(self):
        """list_users should return empty list and zero count when no users exist."""
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(0), FakeResult([]))

        service = AdminService(db)
        users, total = await service.list_users()

        assert total == 0
        assert users == []


class TestApproveUser:
    """Tests for AdminService.approve_user."""

    @pytest.mark.asyncio
    async def test_approve_pending_user(self):
        """Approving a pending user should change their status to Approved."""
        user = _make_user(status="Pending")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.approve_user(user.id)

        assert result is not None
        assert result.status == "Approved"
        assert db.flushed is True

    @pytest.mark.asyncio
    async def test_approve_blocked_user(self):
        """Approving a blocked user should change their status to Approved."""
        user = _make_user(status="Blocked")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.approve_user(user.id)

        assert result is not None
        assert result.status == "Approved"

    @pytest.mark.asyncio
    async def test_approve_nonexistent_user_returns_none(self):
        """Approving a user that doesn't exist should return None."""
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(None))

        service = AdminService(db)
        result = await service.approve_user(uuid.uuid4())

        assert result is None


class TestBlockUser:
    """Tests for AdminService.block_user."""

    @pytest.mark.asyncio
    async def test_block_approved_user(self):
        """Blocking an approved user should change their status to Blocked."""
        user = _make_user(status="Approved")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.block_user(user.id)

        assert result is not None
        assert result.status == "Blocked"
        assert db.flushed is True

    @pytest.mark.asyncio
    async def test_block_pending_user(self):
        """Blocking a pending user should change their status to Blocked."""
        user = _make_user(status="Pending")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.block_user(user.id)

        assert result is not None
        assert result.status == "Blocked"

    @pytest.mark.asyncio
    async def test_block_nonexistent_user_returns_none(self):
        """Blocking a user that doesn't exist should return None."""
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(None))

        service = AdminService(db)
        result = await service.block_user(uuid.uuid4())

        assert result is None


class TestSetUserStatus:
    """Tests for AdminService.set_user_status."""

    @pytest.mark.asyncio
    async def test_set_status_to_approved(self):
        """Setting status to Approved should update the user."""
        user = _make_user(status="Pending")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.set_user_status(user.id, "Approved")

        assert result is not None
        assert result.status == "Approved"

    @pytest.mark.asyncio
    async def test_set_status_to_blocked(self):
        """Setting status to Blocked should update the user."""
        user = _make_user(status="Approved")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.set_user_status(user.id, "Blocked")

        assert result is not None
        assert result.status == "Blocked"

    @pytest.mark.asyncio
    async def test_set_status_to_pending(self):
        """Setting status back to Pending should update the user."""
        user = _make_user(status="Approved")
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(user))

        service = AdminService(db)
        result = await service.set_user_status(user.id, "Pending")

        assert result is not None
        assert result.status == "Pending"

    @pytest.mark.asyncio
    async def test_set_invalid_status_raises_valueerror(self):
        """Setting an invalid status should raise ValueError."""
        db = FakeAsyncSession()

        service = AdminService(db)
        with pytest.raises(ValueError, match="Invalid status"):
            await service.set_user_status(uuid.uuid4(), "Suspended")

    @pytest.mark.asyncio
    async def test_set_status_nonexistent_user_returns_none(self):
        """Setting status on a user that doesn't exist should return None."""
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(None))

        service = AdminService(db)
        result = await service.set_user_status(uuid.uuid4(), "Approved")

        assert result is None


class TestAdminGuardBehavior:
    """Tests verifying admin-only access guard logic via the router dependency."""

    @pytest.mark.asyncio
    async def test_non_admin_user_is_denied(self):
        """A non-admin user should receive ACCESS_DENIED (403) from admin endpoints."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from fastapi import HTTPException

        from app.routers.admin import get_current_admin_user

        non_admin_user = _make_user(status="Approved", is_admin=False)

        # Mock request with a session cookie
        mock_request = MagicMock()
        mock_request.cookies = {"session_token": "valid-token"}

        # Mock db session
        mock_db = AsyncMock()

        with patch(
            "app.routers.admin.AuthService"
        ) as MockAuthService:
            mock_auth_instance = AsyncMock()
            mock_auth_instance.validate_session.return_value = non_admin_user
            MockAuthService.return_value = mock_auth_instance

            with pytest.raises(HTTPException) as exc_info:
                await get_current_admin_user(mock_request, mock_db)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_admin_user_passes_guard(self):
        """An admin user should pass the guard and be returned."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.routers.admin import get_current_admin_user

        admin_user = _make_user(status="Approved", is_admin=True)

        mock_request = MagicMock()
        mock_request.cookies = {"session_token": "valid-token"}

        mock_db = AsyncMock()

        with patch(
            "app.routers.admin.AuthService"
        ) as MockAuthService:
            mock_auth_instance = AsyncMock()
            mock_auth_instance.validate_session.return_value = admin_user
            MockAuthService.return_value = mock_auth_instance

            result = await get_current_admin_user(mock_request, mock_db)

            assert result is admin_user
            assert result.is_admin is True

    @pytest.mark.asyncio
    async def test_unauthenticated_user_is_rejected(self):
        """A request without a session token should receive 401."""
        from fastapi import HTTPException
        from unittest.mock import MagicMock, AsyncMock

        from app.routers.admin import get_current_admin_user

        mock_request = MagicMock()
        mock_request.cookies = {}

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(mock_request, mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"

    @pytest.mark.asyncio
    async def test_invalid_session_token_is_rejected(self):
        """A request with an invalid/expired session should receive 401."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from fastapi import HTTPException

        from app.routers.admin import get_current_admin_user

        mock_request = MagicMock()
        mock_request.cookies = {"session_token": "expired-token"}

        mock_db = AsyncMock()

        with patch(
            "app.routers.admin.AuthService"
        ) as MockAuthService:
            mock_auth_instance = AsyncMock()
            mock_auth_instance.validate_session.return_value = None
            MockAuthService.return_value = mock_auth_instance

            with pytest.raises(HTTPException) as exc_info:
                await get_current_admin_user(mock_request, mock_db)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid or expired session"
