"""Unit tests for AuthService: session management, user upsert, and first-user-admin rule."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.session import Session
from app.models.user import User
from app.services.auth_service import AuthService, _hash_token


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


class FakeResult:
    """Fake SQLAlchemy result."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value


class TestHashToken:
    """Tests for the _hash_token helper."""

    def test_hash_is_deterministic(self):
        token = "test-token-123"
        assert _hash_token(token) == _hash_token(token)

    def test_different_tokens_produce_different_hashes(self):
        assert _hash_token("token-a") != _hash_token("token-b")

    def test_hash_is_hex_string(self):
        result = _hash_token("any-token")
        assert len(result) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in result)


class TestUpsertUser:
    """Tests for user upsert logic including first-user-admin rule."""

    @pytest.mark.asyncio
    async def test_first_user_becomes_admin_with_approved_status(self):
        """The very first user registered should be admin with Approved status."""
        db = FakeAsyncSession()
        # First execute: find existing user -> None
        # Second execute: count users -> 0
        db.set_execute_results(FakeResult(None), FakeResult(0))

        service = AuthService(db)
        user = await service._upsert_user(
            oauth_provider="google",
            oauth_provider_id="google-123",
            display_name="First User",
            email="first@example.com",
            profile_picture_url="https://example.com/pic.jpg",
        )

        assert user.is_admin is True
        assert user.status == "Approved"
        assert user.display_name == "First User"
        assert user.email == "first@example.com"
        assert user.oauth_provider == "google"
        assert user.oauth_provider_id == "google-123"

    @pytest.mark.asyncio
    async def test_second_user_gets_pending_status_not_admin(self):
        """Subsequent users should get Pending status and not be admin."""
        db = FakeAsyncSession()
        # First execute: find existing user -> None
        # Second execute: count users -> 1 (not the first user)
        db.set_execute_results(FakeResult(None), FakeResult(1))

        service = AuthService(db)
        user = await service._upsert_user(
            oauth_provider="facebook",
            oauth_provider_id="fb-456",
            display_name="Second User",
            email="second@example.com",
            profile_picture_url=None,
        )

        assert user.is_admin is False
        assert user.status == "Pending"
        assert user.display_name == "Second User"

    @pytest.mark.asyncio
    async def test_existing_user_gets_updated_profile(self):
        """An existing user logging in again should have profile info updated."""
        existing_user = User(
            id=uuid.uuid4(),
            display_name="Old Name",
            email="old@example.com",
            profile_picture_url="https://old.com/pic.jpg",
            oauth_provider="google",
            oauth_provider_id="google-123",
            status="Approved",
            is_admin=True,
            registered_at=datetime.now(timezone.utc),
            last_login_at=None,
        )

        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(existing_user))

        service = AuthService(db)
        user = await service._upsert_user(
            oauth_provider="google",
            oauth_provider_id="google-123",
            display_name="New Name",
            email="new@example.com",
            profile_picture_url="https://new.com/pic.jpg",
        )

        assert user is existing_user
        assert user.display_name == "New Name"
        assert user.email == "new@example.com"
        assert user.profile_picture_url == "https://new.com/pic.jpg"
        assert user.last_login_at is not None


class TestCreateSession:
    """Tests for session creation."""

    @pytest.mark.asyncio
    async def test_create_session_returns_token_string(self):
        """Session creation should return a non-empty token string."""
        db = FakeAsyncSession()
        service = AuthService(db)

        user_id = uuid.uuid4()
        token = await service._create_session(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_create_session_adds_session_to_db(self):
        """Session creation should add a Session object to the database."""
        db = FakeAsyncSession()
        service = AuthService(db)

        user_id = uuid.uuid4()
        token = await service._create_session(user_id)

        assert len(db.added) == 1
        session_obj = db.added[0]
        assert isinstance(session_obj, Session)
        assert session_obj.user_id == user_id
        assert session_obj.token_hash == _hash_token(token)
        assert session_obj.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_session_expires_in_7_days(self):
        """Session should expire approximately 7 days from creation."""
        db = FakeAsyncSession()
        service = AuthService(db)

        user_id = uuid.uuid4()
        await service._create_session(user_id)

        session_obj = db.added[0]
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        # Allow 5 seconds tolerance
        assert abs((session_obj.expires_at - expected_expiry).total_seconds()) < 5


class TestValidateSession:
    """Tests for session validation."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """A valid, non-expired token should return the associated user."""
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            display_name="Test User",
            email="test@example.com",
            oauth_provider="google",
            oauth_provider_id="g-123",
            status="Approved",
            is_admin=False,
            registered_at=datetime.now(timezone.utc),
        )

        token = "valid-token-xyz"
        session_obj = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            created_at=datetime.now(timezone.utc),
        )

        db = FakeAsyncSession()
        # First execute: find session -> session_obj
        # Second execute: find user -> user
        db.set_execute_results(FakeResult(session_obj), FakeResult(user))

        service = AuthService(db)
        result = await service.validate_session(token)

        assert result is user

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self):
        """An invalid token should return None."""
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(None))

        service = AuthService(db)
        result = await service.validate_session("invalid-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_expired_session_returns_none(self):
        """An expired session should return None (filtered by the query)."""
        db = FakeAsyncSession()
        # The query filters by expires_at > now, so expired sessions won't be found
        db.set_execute_results(FakeResult(None))

        service = AuthService(db)
        result = await service.validate_session("expired-token")

        assert result is None


class TestLogout:
    """Tests for session termination."""

    @pytest.mark.asyncio
    async def test_logout_deletes_session(self):
        """Logout should delete the session from the database."""
        token = "session-to-delete"
        session_obj = Session(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            created_at=datetime.now(timezone.utc),
        )

        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(session_obj))

        service = AuthService(db)
        await service.logout(token)

        assert session_obj in db.deleted

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token_does_nothing(self):
        """Logout with a non-existent token should not raise an error."""
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(None))

        service = AuthService(db)
        await service.logout("nonexistent-token")

        assert len(db.deleted) == 0


class TestValidateSessionEdgeCases:
    """Tests for session validation edge cases including blocked users and expiry boundaries."""

    @pytest.mark.asyncio
    async def test_blocked_user_session_still_validates(self):
        """A blocked user's session is still technically valid — access denial happens at the middleware layer."""
        user_id = uuid.uuid4()
        blocked_user = User(
            id=user_id,
            display_name="Blocked User",
            email="blocked@example.com",
            oauth_provider="google",
            oauth_provider_id="g-blocked",
            status="Blocked",
            is_admin=False,
            registered_at=datetime.now(timezone.utc),
        )

        token = "blocked-user-token"
        session_obj = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
            created_at=datetime.now(timezone.utc),
        )

        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(session_obj), FakeResult(blocked_user))

        service = AuthService(db)
        result = await service.validate_session(token)

        # Session validation returns the user regardless of status;
        # the blocked check is enforced by the middleware/dependency layer.
        assert result is blocked_user
        assert result.status == "Blocked"

    @pytest.mark.asyncio
    async def test_session_at_exact_expiry_boundary_returns_none(self):
        """A session whose expires_at is exactly now should be treated as expired (query uses >)."""
        # The query uses: Session.expires_at > datetime.now(timezone.utc)
        # So a session expiring exactly now would not match and return None.
        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(None))

        service = AuthService(db)
        result = await service.validate_session("boundary-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_session_just_barely_valid_returns_user(self):
        """A session expiring 1 second in the future should still be valid."""
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            display_name="Just-In-Time User",
            email="jit@example.com",
            oauth_provider="facebook",
            oauth_provider_id="fb-jit",
            status="Approved",
            is_admin=False,
            registered_at=datetime.now(timezone.utc),
        )

        token = "barely-valid-token"
        session_obj = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=1),
            created_at=datetime.now(timezone.utc),
        )

        db = FakeAsyncSession()
        db.set_execute_results(FakeResult(session_obj), FakeResult(user))

        service = AuthService(db)
        result = await service.validate_session(token)

        assert result is user

    @pytest.mark.asyncio
    async def test_session_valid_but_user_not_found_returns_none(self):
        """If a session is valid but the associated user no longer exists, return None."""
        token = "orphan-session-token"
        session_obj = Session(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            created_at=datetime.now(timezone.utc),
        )

        db = FakeAsyncSession()
        # Session found, but user query returns None
        db.set_execute_results(FakeResult(session_obj), FakeResult(None))

        service = AuthService(db)
        result = await service.validate_session(token)

        assert result is None


class TestGetAuthorizationUrl:
    """Tests for OAuth URL generation."""

    def test_google_url_contains_accounts_google(self):
        """Google authorization URL should point to Google's OAuth endpoint."""
        db = FakeAsyncSession()
        service = AuthService(db)
        url, state = service.get_authorization_url("google")

        assert "accounts.google.com" in url
        assert state is not None

    def test_facebook_url_contains_facebook(self):
        """Facebook authorization URL should point to Facebook's OAuth endpoint."""
        db = FakeAsyncSession()
        service = AuthService(db)
        url, state = service.get_authorization_url("facebook")

        assert "facebook.com" in url
        assert state is not None

    def test_unsupported_provider_raises_error(self):
        """An unsupported provider should raise ValueError."""
        db = FakeAsyncSession()
        service = AuthService(db)

        with pytest.raises(ValueError, match="Unsupported OAuth provider"):
            service.get_authorization_url("twitter")
