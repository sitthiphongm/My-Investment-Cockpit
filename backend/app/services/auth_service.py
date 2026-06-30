"""Authentication service handling OAuth flows, sessions, and user management."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from authlib.integrations.httpx_client import AsyncOAuth2Client
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.session import Session
from app.models.user import User


# Session token expiry: 7 days
SESSION_EXPIRY_DAYS = 7

# OAuth provider configurations
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

FACEBOOK_AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FACEBOOK_USERINFO_URL = "https://graph.facebook.com/v19.0/me"


def _hash_token(token: str) -> str:
    """Hash a session token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Service for OAuth authentication, session management, and user upsert."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # OAuth flow helpers
    # ------------------------------------------------------------------

    def get_oauth_client(self, provider: str) -> AsyncOAuth2Client:
        """Create an OAuth2 client for the given provider."""
        if provider == "google":
            return AsyncOAuth2Client(
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                redirect_uri=f"{settings.oauth_redirect_base_url}/api/auth/callback/google",
                scope="openid email profile",
            )
        elif provider == "facebook":
            return AsyncOAuth2Client(
                client_id=settings.facebook_client_id,
                client_secret=settings.facebook_client_secret,
                redirect_uri=f"{settings.oauth_redirect_base_url}/api/auth/callback/facebook",
                scope="email public_profile",
            )
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

    def get_authorization_url(self, provider: str) -> tuple[str, str]:
        """Generate an authorization URL and state for the given provider.

        Returns:
            Tuple of (authorization_url, state)
        """
        client = self.get_oauth_client(provider)
        if provider == "google":
            url, state = client.create_authorization_url(GOOGLE_AUTHORIZE_URL)
        elif provider == "facebook":
            url, state = client.create_authorization_url(FACEBOOK_AUTHORIZE_URL)
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
        return url, state

    async def handle_callback(
        self, provider: str, authorization_response_url: str
    ) -> tuple[User, str]:
        """Handle OAuth callback: exchange code for token, fetch user info, upsert user, create session.

        Args:
            provider: "google" or "facebook"
            authorization_response_url: The full callback URL with query params

        Returns:
            Tuple of (user, session_token)
        """
        client = self.get_oauth_client(provider)

        # Exchange authorization code for access token
        if provider == "google":
            token = await client.fetch_token(
                GOOGLE_TOKEN_URL,
                authorization_response=authorization_response_url,
            )
            # Fetch user info from Google
            resp = await client.get(GOOGLE_USERINFO_URL)
            resp.raise_for_status()
            userinfo = resp.json()
            oauth_id = userinfo.get("sub")
            display_name = userinfo.get("name", "")
            email = userinfo.get("email", "")
            picture = userinfo.get("picture")
        elif provider == "facebook":
            token = await client.fetch_token(
                FACEBOOK_TOKEN_URL,
                authorization_response=authorization_response_url,
            )
            # Fetch user info from Facebook
            resp = await client.get(
                FACEBOOK_USERINFO_URL,
                params={"fields": "id,name,email,picture.type(large)"},
            )
            resp.raise_for_status()
            userinfo = resp.json()
            oauth_id = userinfo.get("id")
            display_name = userinfo.get("name", "")
            email = userinfo.get("email", "")
            picture_data = userinfo.get("picture", {}).get("data", {})
            picture = picture_data.get("url")
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        await client.aclose()

        # Upsert user and create session
        user = await self._upsert_user(
            oauth_provider=provider,
            oauth_provider_id=oauth_id,
            display_name=display_name,
            email=email,
            profile_picture_url=picture,
        )
        session_token = await self._create_session(user.id)
        return user, session_token

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    async def _upsert_user(
        self,
        oauth_provider: str,
        oauth_provider_id: str,
        display_name: str,
        email: str,
        profile_picture_url: str | None,
    ) -> User:
        """Create or update user based on OAuth provider and ID.

        First registered user becomes Admin with Approved status.
        New users get Pending status by default.
        """
        # Look up existing user by oauth provider + id
        stmt = select(User).where(
            User.oauth_provider == oauth_provider,
            User.oauth_provider_id == oauth_provider_id,
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Update profile fields on each login
            user.display_name = display_name
            user.email = email
            user.profile_picture_url = profile_picture_url
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()
            return user

        # New user - check if this is the first user (becomes admin)
        count_stmt = select(func.count()).select_from(User)
        count_result = await self.db.execute(count_stmt)
        user_count = count_result.scalar()

        is_first_user = user_count == 0

        new_user = User(
            id=uuid.uuid4(),
            display_name=display_name,
            email=email,
            profile_picture_url=profile_picture_url,
            oauth_provider=oauth_provider,
            oauth_provider_id=oauth_provider_id,
            status="Approved" if is_first_user else "Pending",
            is_admin=is_first_user,
            registered_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )
        self.db.add(new_user)
        await self.db.flush()
        return new_user

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _create_session(self, user_id: uuid.UUID) -> str:
        """Create a new session for the user and return the raw token."""
        token = secrets.token_urlsafe(64)
        token_hash = _hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)

        session = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(session)
        await self.db.flush()
        return token

    async def validate_session(self, token: str) -> User | None:
        """Validate a session token and return the associated user if valid.

        Returns None if the token is invalid or expired.
        """
        token_hash = _hash_token(token)
        stmt = select(Session).where(
            Session.token_hash == token_hash,
            Session.expires_at > datetime.now(timezone.utc),
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return None

        # Fetch the user
        user_stmt = select(User).where(User.id == session.user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        return user

    async def logout(self, token: str) -> None:
        """Invalidate a session by deleting it from the database."""
        token_hash = _hash_token(token)
        stmt = select(Session).where(Session.token_hash == token_hash)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if session:
            await self.db.delete(session)
            await self.db.flush()
