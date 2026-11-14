"""
Transaction-boundary and concurrency tests for password reset (Task 10).

The requirement these pin down: a reset token must never end up spent while
the password is unchanged, and must be redeemable exactly once even when
several requests race for it. See
PasswordResetTokenRepository.consume_and_reset_password and
docs/decisions/0005-password-reset.md.
"""

import threading
from datetime import UTC, datetime, timedelta

import app.models  # noqa: F401  (registers every model on Base.metadata)
import pytest
from app.core.database import Base
from app.core.security import hash_password_reset_token
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.repositories.password_reset import PasswordResetTokenRepository
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

EMAIL = "atomic-user@example.com"
OLD_PASSWORD = "OldPassword-123"
NEW_PASSWORD = "BrandNewPassword-456"
RAW_TOKEN = "a-valid-raw-token-for-the-atomicity-tests"


def _future(minutes=30):
    return datetime.now(UTC) + timedelta(minutes=minutes)


def _seed(session, *, active=True, expires_at=None, extra_tokens=0, sessions=0):
    """A user with a reset token, optionally extra reset tokens and refresh sessions."""
    user = User(
        email=f"seed-{id(session)}@example.com", hashed_password="old-hash", is_active=active
    )
    session.add(user)
    session.flush()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(RAW_TOKEN),
            expires_at=expires_at or _future(),
        )
    )
    for i in range(extra_tokens):
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(f"other-token-{i}"),
                expires_at=_future(),
            )
        )
    for i in range(sessions):
        session.add(
            RefreshSession(
                user_id=user.id,
                family_id=f"family-{i}",
                token_hash=f"refresh-hash-{i}".ljust(64, "x"),
                expires_at=_future(60 * 24),
            )
        )
    session.commit()
    return user.id


# --- repository-level behavior ---------------------------------------------------


def test_success_sets_password_expires_other_links_and_revokes_sessions(db_session):
    user_id = _seed(db_session, extra_tokens=2, sessions=3)
    repo = PasswordResetTokenRepository(db_session)

    result = repo.consume_and_reset_password(hash_password_reset_token(RAW_TOKEN), "new-hash")

    assert result == user_id
    assert db_session.get(User, user_id).hashed_password == "new-hash"
    assert all(t.used_at is not None for t in db_session.query(PasswordResetToken).all())
    assert all(s.revoked_at is not None for s in db_session.query(RefreshSession).all())


def test_unknown_token_changes_nothing(db_session):
    user_id = _seed(db_session, sessions=1)
    repo = PasswordResetTokenRepository(db_session)

    assert repo.consume_and_reset_password(hash_password_reset_token("nope"), "new-hash") is None

    assert db_session.get(User, user_id).hashed_password == "old-hash"
    assert db_session.query(RefreshSession).one().revoked_at is None
    assert db_session.query(PasswordResetToken).one().used_at is None


def test_expired_token_changes_nothing(db_session):
    user_id = _seed(db_session, expires_at=datetime.now(UTC) - timedelta(seconds=1), sessions=1)
    repo = PasswordResetTokenRepository(db_session)

    assert repo.consume_and_reset_password(hash_password_reset_token(RAW_TOKEN), "new-hash") is None

    assert db_session.get(User, user_id).hashed_password == "old-hash"
    assert db_session.query(RefreshSession).one().revoked_at is None
    assert db_session.query(PasswordResetToken).one().used_at is None


def test_inactive_user_is_refused_and_the_token_is_not_consumed(db_session):
    """The token UPDATE runs first; refusing the user must roll it back, not leave it spent."""
    user_id = _seed(db_session, active=False)
    repo = PasswordResetTokenRepository(db_session)

    assert repo.consume_and_reset_password(hash_password_reset_token(RAW_TOKEN), "new-hash") is None

    assert db_session.get(User, user_id).hashed_password == "old-hash"
    assert db_session.query(PasswordResetToken).one().used_at is None


def test_the_same_token_cannot_be_consumed_twice(db_session):
    _seed(db_session)
    repo = PasswordResetTokenRepository(db_session)
    token_hash = hash_password_reset_token(RAW_TOKEN)

    assert repo.consume_and_reset_password(token_hash, "first-hash") is not None
    assert repo.consume_and_reset_password(token_hash, "second-hash") is None

    assert db_session.query(User).one().hashed_password == "first-hash"


# --- a failure partway must not spend the token ----------------------------------


def _register(client):
    response = client.post("/api/auth/register", json={"email": EMAIL, "password": OLD_PASSWORD})
    assert response.status_code == 201


def _login(client, password):
    return client.post("/api/auth/login", data={"username": EMAIL, "password": password})


@pytest.mark.parametrize(
    ("failing_statement", "occurrence"),
    [
        ("UPDATE users", 1),  # the password change itself fails
        ("UPDATE password_reset_tokens", 2),  # expiring the user's other links fails
        ("UPDATE refresh_sessions", 1),  # revoking sessions fails (last step)
    ],
)
def test_a_database_failure_midway_leaves_the_token_unspent_and_password_unchanged(
    client, db_session, failing_statement, occurrence
):
    _register(client)
    access_token = _login(client, OLD_PASSWORD).json()["access_token"]
    assert client.post("/api/auth/forgot-password", json={"email": EMAIL}).status_code == 202
    from app.integrations.email import get_email_sender

    body = get_email_sender().outbox[-1].body
    raw_token = body.split("#token=")[1].split()[0]

    # Fail the Nth matching statement INSIDE the reset transaction. The token
    # is consumed by the very first statement, so this proves it is rolled back.
    engine = db_session.get_bind()
    seen = {"count": 0}

    def fail_midway(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith(failing_statement):
            seen["count"] += 1
            if seen["count"] == occurrence:
                raise OperationalError(statement, parameters, Exception("simulated DB failure"))

    event.listen(engine, "before_cursor_execute", fail_midway)
    try:
        crashing_client = TestClient(client.app, raise_server_exceptions=False)
        failed = crashing_client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "new_password": NEW_PASSWORD},
        )
    finally:
        event.remove(engine, "before_cursor_execute", fail_midway)

    assert seen["count"] == occurrence, "the injected failure never fired"
    assert failed.status_code == 500
    assert failed.json() == {"detail": "Internal server error"}

    # Token still unspent...
    assert db_session.query(PasswordResetToken).one().used_at is None
    # ...password unchanged...
    assert _login(client, OLD_PASSWORD).status_code == 200
    assert _login(client, NEW_PASSWORD).status_code == 401
    # ...the user's existing session survived (revocation was rolled back too)...
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    # ...and the very same link still works once the database recovers.
    retry = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert retry.status_code == 200
    assert _login(client, NEW_PASSWORD).status_code == 200


# --- concurrency ------------------------------------------------------------------


def test_concurrent_redemptions_of_one_token_succeed_exactly_once(tmp_path):
    """
    Real threads, each with its OWN session/connection, against a file-backed
    SQLite database (the in-memory test DB shares one connection, which would
    serialize the threads and prove nothing). All start together at a barrier.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine, autoflush=False)
    with make_session() as seed_session:
        user_id = _seed(seed_session, sessions=2)

    attempts = 8
    barrier = threading.Barrier(attempts)
    results: list[str | None] = [None] * attempts
    errors: list[Exception] = []

    def attempt(index: int) -> None:
        session = make_session()
        try:
            barrier.wait(timeout=10)
            results[index] = PasswordResetTokenRepository(session).consume_and_reset_password(
                hash_password_reset_token(RAW_TOKEN), f"hash-from-attempt-{index}"
            )
        except Exception as exc:  # pragma: no cover - surfaced by the assertion below
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    winners = [i for i, result in enumerate(results) if result is not None]
    assert len(winners) == 1, f"token redeemed {len(winners)} times: {winners}"
    assert results[winners[0]] == user_id

    with make_session() as check:
        # The winner's password - and only the winner's - was applied.
        assert check.get(User, user_id).hashed_password == f"hash-from-attempt-{winners[0]}"
        assert check.query(PasswordResetToken).one().used_at is not None
        assert all(s.revoked_at is not None for s in check.query(RefreshSession).all())
    engine.dispose()
