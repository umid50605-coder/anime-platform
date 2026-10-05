import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.repositories.refresh_session import RefreshSessionRepository
from app.services.user import UserService


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


@dataclass(frozen=True)
class LoginSessionTokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)


class AuthService:
    def __init__(
        self,
        user_service: UserService,
        refresh_session_repository: RefreshSessionRepository,
    ):
        self.user_service = user_service
        self.refresh_session_repository = refresh_session_repository

    def authenticate(self, email: str, password: str) -> User:
        user = self.user_service.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        if not user.is_active:
            raise InvalidCredentialsError("User account is inactive")
        return user

    def issue_token_for(self, user: User) -> str:
        return create_access_token(subject=user.id)

    def create_login_session(self, user: User) -> LoginSessionTokens:
        family_id = str(uuid.uuid4())
        refresh_token = create_refresh_token()
        now = datetime.now(UTC)
        refresh_session = RefreshSession(
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
        )
        access_token = create_access_token(subject=user.id, sid=family_id)

        self.refresh_session_repository.create(refresh_session)
        return LoginSessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def refresh_session(self, token: str) -> LoginSessionTokens:
        token_hash = hash_refresh_token(token)
        current_session = self.refresh_session_repository.get_by_token_hash(token_hash)
        if current_session is None:
            raise InvalidRefreshTokenError("Invalid refresh token")

        if current_session.revoked_at is not None:
            self.refresh_session_repository.revoke_family(current_session.family_id)
            raise InvalidRefreshTokenError("Invalid refresh token")

        now = datetime.now(UTC)
        expires_at = current_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        else:
            expires_at = expires_at.astimezone(UTC)
        if expires_at <= now:
            raise InvalidRefreshTokenError("Invalid refresh token")

        user = self.user_service.get_by_id(current_session.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError("Invalid refresh token")

        refresh_token = create_refresh_token()
        replacement = RefreshSession(
            user_id=user.id,
            family_id=current_session.family_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
        )
        access_token = create_access_token(subject=user.id, sid=current_session.family_id)

        if not self.rotate_refresh_session(token_hash, replacement):
            raise InvalidRefreshTokenError("Invalid refresh token")

        return LoginSessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def logout_session(self, token: str | None) -> None:
        """Revoke the refresh-token family referenced by a token, if it exists."""
        if token is None:
            return
        current_session = self.refresh_session_repository.get_by_token_hash(
            hash_refresh_token(token)
        )
        if current_session is not None:
            self.refresh_session_repository.revoke_family(current_session.family_id)

    def rotate_refresh_session(self, token_hash: str, replacement: RefreshSession) -> bool:
        """Rotate one refresh session; revoke its family if the token was reused."""
        if self.refresh_session_repository.rotate(token_hash, replacement):
            return True

        previous = self.refresh_session_repository.get_by_token_hash(token_hash)
        if previous is not None and previous.revoked_at is not None:
            self.refresh_session_repository.revoke_family(previous.family_id)
        return False
