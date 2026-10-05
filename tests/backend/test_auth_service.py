from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.security import hash_refresh_token
from app.models.user import User
from app.repositories.refresh_session import RefreshSessionRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService, InvalidRefreshTokenError
from app.services.user import UserService
from jose import jwt


def test_create_login_session_persists_hashed_refresh_token_and_sets_sid(db_session):
    user_repository = UserRepository(db_session)
    user = user_repository.create(
        User(email="session@example.com", hashed_password="hashed-password")
    )
    refresh_session_repository = RefreshSessionRepository(db_session)
    auth_service = AuthService(
        UserService(user_repository),
        refresh_session_repository,
    )

    tokens = auth_service.create_login_session(user)

    access_payload = jwt.decode(
        tokens.access_token,
        get_settings().jwt_secret_key,
        algorithms=[get_settings().jwt_algorithm],
    )
    refresh_session = refresh_session_repository.get_by_token_hash(
        hash_refresh_token(tokens.refresh_token)
    )

    assert refresh_session is not None
    assert access_payload["sub"] == user.id
    assert access_payload["sid"] == refresh_session.family_id
    assert refresh_session.user_id == user.id
    assert refresh_session.token_hash == hash_refresh_token(tokens.refresh_token)
    assert refresh_session.token_hash != tokens.refresh_token
    assert tokens.refresh_token not in repr(tokens)
    assert tokens.access_token not in repr(tokens)


def test_refresh_login_session_rotates_token_and_preserves_family(db_session):
    user_repository = UserRepository(db_session)
    user = user_repository.create(
        User(email="refresh@example.com", hashed_password="hashed-password")
    )
    refresh_session_repository = RefreshSessionRepository(db_session)
    auth_service = AuthService(UserService(user_repository), refresh_session_repository)
    original_tokens = auth_service.create_login_session(user)

    original_session = refresh_session_repository.get_by_token_hash(
        hash_refresh_token(original_tokens.refresh_token)
    )
    assert original_session is not None
    assert original_session.expires_at.tzinfo is None

    refreshed_tokens = auth_service.refresh_session(original_tokens.refresh_token)

    old_session = refresh_session_repository.get_by_token_hash(
        hash_refresh_token(original_tokens.refresh_token)
    )
    new_session = refresh_session_repository.get_by_token_hash(
        hash_refresh_token(refreshed_tokens.refresh_token)
    )
    access_payload = jwt.decode(
        refreshed_tokens.access_token,
        get_settings().jwt_secret_key,
        algorithms=[get_settings().jwt_algorithm],
    )

    assert old_session is not None and old_session.revoked_at is not None
    assert new_session is not None
    assert new_session.family_id == original_session.family_id
    assert new_session.user_id == user.id
    assert access_payload["sub"] == user.id
    assert access_payload["sid"] == original_session.family_id


def test_reusing_revoked_refresh_token_revokes_its_family(db_session):
    user_repository = UserRepository(db_session)
    user = user_repository.create(
        User(email="reuse@example.com", hashed_password="hashed-password")
    )
    refresh_session_repository = RefreshSessionRepository(db_session)
    auth_service = AuthService(UserService(user_repository), refresh_session_repository)
    original_tokens = auth_service.create_login_session(user)
    refreshed_tokens = auth_service.refresh_session(original_tokens.refresh_token)

    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh_session(original_tokens.refresh_token)

    replacement_session = refresh_session_repository.get_by_token_hash(
        hash_refresh_token(refreshed_tokens.refresh_token)
    )
    assert replacement_session is not None
    assert replacement_session.revoked_at is not None


def test_expired_refresh_session_is_rejected(db_session):
    user_repository = UserRepository(db_session)
    user = user_repository.create(
        User(email="expired@example.com", hashed_password="hashed-password")
    )
    refresh_session_repository = RefreshSessionRepository(db_session)
    auth_service = AuthService(UserService(user_repository), refresh_session_repository)
    tokens = auth_service.create_login_session(user)
    session = refresh_session_repository.get_by_token_hash(hash_refresh_token(tokens.refresh_token))
    assert session is not None
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh_session(tokens.refresh_token)


def test_refresh_for_inactive_user_is_rejected(db_session):
    user_repository = UserRepository(db_session)
    user = user_repository.create(
        User(email="inactive-refresh@example.com", hashed_password="hashed-password")
    )
    refresh_session_repository = RefreshSessionRepository(db_session)
    auth_service = AuthService(UserService(user_repository), refresh_session_repository)
    tokens = auth_service.create_login_session(user)
    user.is_active = False
    db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh_session(tokens.refresh_token)


def test_unknown_refresh_token_is_rejected(db_session):
    auth_service = AuthService(
        UserService(UserRepository(db_session)),
        RefreshSessionRepository(db_session),
    )

    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh_session("unknown-refresh-token")