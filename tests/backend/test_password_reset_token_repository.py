from datetime import UTC, datetime, timedelta

from app.core.security import create_password_reset_token, hash_password_reset_token
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset import PasswordResetTokenRepository
from app.repositories.user import UserRepository


def _create_user(user_repository: UserRepository, email: str) -> User:
    return user_repository.create(User(email=email, hashed_password="hashed-password"))


def _create_reset_token(
    repository: PasswordResetTokenRepository,
    user_id: str,
    raw_token: str,
    *,
    expires_at: datetime,
) -> PasswordResetToken:
    return repository.create(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_password_reset_token(raw_token),
            expires_at=expires_at,
        )
    )


def test_password_reset_token_persists_only_its_hash(db_session):
    user = _create_user(UserRepository(db_session), "reset-hash@example.com")
    repository = PasswordResetTokenRepository(db_session)
    raw_token = create_password_reset_token()
    token_hash = hash_password_reset_token(raw_token)

    token = _create_reset_token(
        repository,
        user.id,
        raw_token,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    stored_token = repository.get_by_token_hash(token_hash)
    assert stored_token is not None
    assert stored_token.token_hash == token_hash
    assert stored_token.token_hash != raw_token, "Raw reset token was persisted"
    assert raw_token not in repr(stored_token), "Raw reset token was exposed in the model repr"
    assert token.token_hash == token_hash


def test_active_password_reset_token_can_be_used_only_once(db_session):
    user = _create_user(UserRepository(db_session), "reset-once@example.com")
    repository = PasswordResetTokenRepository(db_session)
    now = datetime.now(UTC)
    token = _create_reset_token(
        repository,
        user.id,
        create_password_reset_token(),
        expires_at=now + timedelta(minutes=30),
    )

    assert repository.mark_used_if_active(token.token_hash, now=now)
    assert not repository.mark_used_if_active(token.token_hash, now=now)

    stored_token = repository.get_by_token_hash(token.token_hash)
    assert stored_token is not None
    assert stored_token.used_at is not None
    assert stored_token.used_at.replace(tzinfo=UTC) == now


def test_expired_password_reset_token_cannot_be_used(db_session):
    user = _create_user(UserRepository(db_session), "reset-expired@example.com")
    repository = PasswordResetTokenRepository(db_session)
    now = datetime.now(UTC)
    token = _create_reset_token(
        repository,
        user.id,
        create_password_reset_token(),
        expires_at=now - timedelta(seconds=1),
    )

    assert not repository.mark_used_if_active(token.token_hash, now=now)

    stored_token = repository.get_by_token_hash(token.token_hash)
    assert stored_token is not None
    assert stored_token.used_at is None


def test_using_one_users_token_does_not_change_another_users_token(db_session):
    user_repository = UserRepository(db_session)
    first_user = _create_user(user_repository, "reset-first@example.com")
    second_user = _create_user(user_repository, "reset-second@example.com")
    repository = PasswordResetTokenRepository(db_session)
    now = datetime.now(UTC)
    first_token = _create_reset_token(
        repository,
        first_user.id,
        create_password_reset_token(),
        expires_at=now + timedelta(minutes=30),
    )
    second_token = _create_reset_token(
        repository,
        second_user.id,
        create_password_reset_token(),
        expires_at=now + timedelta(minutes=30),
    )

    assert repository.mark_used_if_active(first_token.token_hash, now=now)

    untouched_token = repository.get_by_token_hash(second_token.token_hash)
    assert untouched_token is not None
    assert untouched_token.user_id == second_user.id
    assert untouched_token.used_at is None
