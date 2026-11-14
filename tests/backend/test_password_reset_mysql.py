"""
MySQL integration tests for Task 10 - Password Reset.

These tests run ONLY when MYSQL_TEST_DATABASE_URL is set, and ONLY against the
`anime_metadata_migration_test` database (the fixture refuses anything else).
They do not use the SQLite fixtures from conftest.py: they build their own
engine and give every thread / step its own Session, like production does.

Schema is NOT created here - run `alembic upgrade head` on the test database
first. Every row these tests create is tracked by id and deleted afterwards;
nothing else in the database is touched. No application code is modified.

Run (URL is read without echoing it to the terminal):

    read -rsp "MySQL test URL: " MYSQL_TEST_DATABASE_URL; echo
    export MYSQL_TEST_DATABASE_URL
    backend/.venv/bin/python -m pytest -v --tb=short \
        tests/backend/test_password_reset_mysql.py
"""

import os
import secrets
import threading
import uuid
from datetime import UTC, datetime, timedelta

import app.models  # noqa: F401 registers all models on Base.metadata
import pytest
from app.core.security.auth import (
    create_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.repositories.password_reset.repository import PasswordResetTokenRepository
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

TEST_DB_NAME = "anime_metadata_migration_test"
_URL = os.environ.get("MYSQL_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not _URL, reason="MYSQL_TEST_DATABASE_URL is not set")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    url = make_url(_URL)
    if not url.drivername.startswith("mysql") or url.database != TEST_DB_NAME:
        pytest.fail(
            f"Refusing to run: MYSQL_TEST_DATABASE_URL must be a MySQL URL for "
            f"the '{TEST_DB_NAME}' database.",
            pytrace=False,
        )
    eng = create_engine(url, pool_pre_ping=True)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture(scope="module")
def Session(engine):  # noqa: N802 - factory, named like a class on purpose
    return sessionmaker(autoflush=False, bind=engine)


class _World:
    """Creates test rows and removes exactly those rows afterwards."""

    def __init__(self, session_factory):
        self.Session = session_factory
        self.user_ids: list[str] = []

    def new_user(self, active: bool = True) -> tuple[str, str]:
        password = secrets.token_urlsafe(12)
        user = User(
            email=f"mysqlit_{uuid.uuid4().hex}@example.test",
            hashed_password=hash_password(password),
            display_name="mysql-it",
            is_active=active,
        )
        with self.Session() as s:
            s.add(user)
            s.commit()
            uid = user.id
        self.user_ids.append(uid)
        return uid, password

    def add_token(self, user_id: str, expires_in: timedelta = timedelta(minutes=30)):
        """Returns (raw_token, expires_at). expires_at has whole seconds only."""
        raw = create_password_reset_token()
        expires_at = datetime.now(UTC).replace(microsecond=0) + expires_in
        with self.Session() as s:
            PasswordResetTokenRepository(s).create(
                PasswordResetToken(
                    user_id=user_id,
                    token_hash=hash_password_reset_token(raw),
                    expires_at=expires_at,
                )
            )
        return raw, expires_at

    def add_refresh_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())
        with self.Session() as s:
            s.add(
                RefreshSession(
                    id=sid,
                    user_id=user_id,
                    family_id=str(uuid.uuid4()),
                    token_hash=secrets.token_hex(32),
                    expires_at=datetime.now(UTC).replace(microsecond=0) + timedelta(days=7),
                )
            )
            s.commit()
        return sid

    def cleanup(self):
        if not self.user_ids:
            return
        with self.Session() as s:
            s.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(self.user_ids)))
            s.execute(delete(RefreshSession).where(RefreshSession.user_id.in_(self.user_ids)))
            s.execute(delete(User).where(User.id.in_(self.user_ids)))
            s.commit()


@pytest.fixture()
def world(Session):  # noqa: N803
    w = _World(Session)
    try:
        yield w
    finally:
        w.cleanup()


# --------------------------------------------------------------------------
# Helpers (always read through a fresh session -> no identity-map staleness)
# --------------------------------------------------------------------------


def _utc(dt: datetime) -> datetime:
    """MySQL DATETIME comes back naive; our convention is that it holds UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _token_row(Session, raw: str):  # noqa: N803
    with Session() as s:
        return s.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_password_reset_token(raw)
            )
        ).scalar_one()


def _user_hash(Session, user_id: str) -> str:  # noqa: N803
    with Session() as s:
        return s.execute(select(User.hashed_password).where(User.id == user_id)).scalar_one()


def _revoked_at(Session, session_id: str):  # noqa: N803
    with Session() as s:
        return s.execute(
            select(RefreshSession.revoked_at).where(RefreshSession.id == session_id)
        ).scalar_one()


def _consume(Session, raw: str, new_hash: str, now=None):  # noqa: N803
    with Session() as s:
        return PasswordResetTokenRepository(s).consume_and_reset_password(
            hash_password_reset_token(raw), new_hash, now=now
        )


def _run_parallel(Session, jobs):  # noqa: N803
    """
    jobs: list of (raw_token, new_password_hash). Each job runs in its own thread
    with its own Session; a barrier releases them together. Returns a list of
    ("ok", user_id_or_None) / ("err", "ExcType:mysql_code") - never the SQL,
    parameters or connection details.
    """
    barrier = threading.Barrier(len(jobs))
    out: list = [None] * len(jobs)

    def worker(i: int, raw: str, new_hash: str):
        try:
            with Session() as s:
                repo = PasswordResetTokenRepository(s)
                barrier.wait(timeout=30)
                out[i] = (
                    "ok",
                    repo.consume_and_reset_password(hash_password_reset_token(raw), new_hash),
                )
        except Exception as exc:  # noqa: BLE001 - classify, don't leak details
            code = (getattr(getattr(exc, "orig", None), "args", None) or (None,))[0]
            out[i] = ("err", f"{type(exc).__name__}:{code}")

    threads = [threading.Thread(target=worker, args=(i, r, h)) for i, (r, h) in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert all(o is not None for o in out), "a worker thread did not finish"
    return out


# --------------------------------------------------------------------------
# 0. Environment
# --------------------------------------------------------------------------


def test_connected_to_mysql8_test_database(Session):  # noqa: N803
    with Session() as s:
        db_name, version = s.execute(text("SELECT DATABASE(), VERSION()")).one()
    assert db_name == TEST_DB_NAME
    assert version.startswith("8.0")


# --------------------------------------------------------------------------
# 1. CRUD / persistence
# --------------------------------------------------------------------------


def test_only_token_hash_is_persisted(world, Session):  # noqa: N803
    uid, _ = world.new_user()
    raw, _ = world.add_token(uid)
    with Session() as s:
        by_raw = s.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == raw)
        ).first()
    row = _token_row(Session, raw)
    assert by_raw is None
    assert len(row.token_hash) == 64
    assert row.token_hash != raw
    assert row.used_at is None
    assert row.user_id == uid


def test_successful_reset_end_to_end(world, Session):  # noqa: N803
    uid, old_pw = world.new_user()
    other_uid, other_pw = world.new_user()

    raw_a, _ = world.add_token(uid)
    raw_b, _ = world.add_token(uid)  # second outstanding link, same user
    other_raw, _ = world.add_token(other_uid)
    sess_1 = world.add_refresh_session(uid)
    sess_2 = world.add_refresh_session(uid)
    other_sess = world.add_refresh_session(other_uid)

    new_pw = secrets.token_urlsafe(12)
    result = _consume(Session, raw_a, hash_password(new_pw))

    assert result == uid
    # token spent, sibling token expired, other user's token untouched
    assert _token_row(Session, raw_a).used_at is not None
    assert _token_row(Session, raw_b).used_at is not None
    assert _token_row(Session, other_raw).used_at is None
    # refresh sessions revoked for this user only
    assert _revoked_at(Session, sess_1) is not None
    assert _revoked_at(Session, sess_2) is not None
    assert _revoked_at(Session, other_sess) is None
    # passwords: new works, old rejected, other user unaffected
    stored = _user_hash(Session, uid)
    assert verify_password(new_pw, stored) is True
    assert verify_password(old_pw, stored) is False
    assert verify_password(other_pw, _user_hash(Session, other_uid)) is True


def test_unknown_expired_used_and_inactive_return_none(world, Session):  # noqa: N803
    uid, pw = world.new_user()

    # unknown
    assert _consume(Session, create_password_reset_token(), hash_password("x" * 12)) is None

    # expired
    expired_raw, _ = world.add_token(uid, expires_in=-timedelta(minutes=1))
    assert _consume(Session, expired_raw, hash_password("x" * 12)) is None
    assert _token_row(Session, expired_raw).used_at is None

    # already used
    raw, _ = world.add_token(uid)
    assert _consume(Session, raw, hash_password(secrets.token_urlsafe(12))) == uid
    assert _consume(Session, raw, hash_password("y" * 12)) is None

    # inactive user: nothing may change, token must stay unused
    inactive_uid, inactive_pw = world.new_user(active=False)
    inactive_raw, _ = world.add_token(inactive_uid)
    before = _user_hash(Session, inactive_uid)
    assert _consume(Session, inactive_raw, hash_password("z" * 12)) is None
    assert _token_row(Session, inactive_raw).used_at is None
    assert _user_hash(Session, inactive_uid) == before
    assert verify_password(inactive_pw, before) is True


# --------------------------------------------------------------------------
# 2. Transaction rollback
# --------------------------------------------------------------------------


def test_rollback_when_password_update_fails(world, Session):  # noqa: N803
    """
    Fault injection without touching app code: a 300-char hash does not fit
    users.hashed_password (VARCHAR(255)). In MySQL strict mode (the 8.0 default)
    the user UPDATE then fails AFTER the token UPDATE already ran, so the whole
    transaction must roll back. (DID NOT RAISE here means sql_mode is not strict.)
    """
    uid, old_pw = world.new_user()
    raw, _ = world.add_token(uid)
    sess = world.add_refresh_session(uid)

    with pytest.raises(DBAPIError):
        _consume(Session, raw, "x" * 300)

    assert _token_row(Session, raw).used_at is None  # token NOT left spent
    assert verify_password(old_pw, _user_hash(Session, uid)) is True
    assert _revoked_at(Session, sess) is None

    # and the same token is still redeemable afterwards
    new_pw = secrets.token_urlsafe(12)
    assert _consume(Session, raw, hash_password(new_pw)) == uid
    assert verify_password(new_pw, _user_hash(Session, uid)) is True


# --------------------------------------------------------------------------
# 3. Concurrency
# --------------------------------------------------------------------------


def test_concurrent_redemption_of_one_token_has_single_winner(world, Session):  # noqa: N803
    uid, _ = world.new_user()
    raw, _ = world.add_token(uid)
    world.add_refresh_session(uid)

    n = 10
    passwords = [secrets.token_urlsafe(12) for _ in range(n)]
    jobs = [(raw, hash_password(p)) for p in passwords]  # Argon2 done BEFORE threads

    out = _run_parallel(Session, jobs)

    errors = [v for k, v in out if k == "err"]
    winners = [i for i, (k, v) in enumerate(out) if k == "ok" and v is not None]
    assert errors == [], f"unexpected DB errors: {errors}"
    assert len(winners) == 1, f"expected exactly one winner, got {len(winners)}"
    assert _token_row(Session, raw).used_at is not None
    assert verify_password(passwords[winners[0]], _user_hash(Session, uid)) is True


def test_concurrent_redemption_of_two_tokens_same_user_probe(world, Session):  # noqa: N803
    """
    Deadlock probe. Two DIFFERENT outstanding tokens of one user redeemed at the
    same time lock token rows and the user row in different orders, which InnoDB
    can resolve with error 1213 (deadlock). The expected outcome is exactly one
    winner and no database errors. A failure listing '1213' PROVES the issue; it
    is reported, not auto-fixed.
    """
    rounds = 15
    all_errors: list[str] = []
    bad_rounds = 0

    for _ in range(rounds):
        uid, _pw = world.new_user()
        raw_a, _ = world.add_token(uid)
        raw_b, _ = world.add_token(uid)
        sess = world.add_refresh_session(uid)
        jobs = [
            (raw_a, hash_password(secrets.token_urlsafe(12))),
            (raw_b, hash_password(secrets.token_urlsafe(12))),
        ]
        out = _run_parallel(Session, jobs)

        errors = [v for k, v in out if k == "err"]
        winners = [v for k, v in out if k == "ok" and v is not None]
        all_errors.extend(errors)
        if errors:
            bad_rounds += 1
            continue
        assert len(winners) == 1, "both tokens redeemed for one user"
        assert _token_row(Session, raw_a).used_at is not None
        assert _token_row(Session, raw_b).used_at is not None
        assert _revoked_at(Session, sess) is not None

    assert not all_errors, (
        f"{bad_rounds}/{rounds} rounds raised DB errors: "
        f"{sorted(set(all_errors))} (…:1213 means InnoDB deadlock)"
    )


# --------------------------------------------------------------------------
# 4. UTC / DATETIME
# --------------------------------------------------------------------------


def test_datetime_roundtrip_is_utc_not_local_time(world, Session):  # noqa: N803
    uid, _ = world.new_user()
    raw, expires_at = world.add_token(uid)
    row = _token_row(Session, raw)

    assert row.expires_at.tzinfo is None  # MySQL DATETIME has no tz: documents the gotcha
    assert _utc(row.expires_at) == expires_at  # same UTC wall-clock written and read
    # created_at default is generated in Python (UTC): a 5h (Tashkent) skew would show here
    assert abs(_utc(row.created_at) - datetime.now(UTC)) < timedelta(minutes=2)


def test_expiry_boundary_with_mysql_comparison(world, Session):  # noqa: N803
    uid, _ = world.new_user()
    raw, expires_at = world.add_token(uid)

    # exactly at expiry -> rejected (expires_at > now is False); token stays unused
    assert _consume(Session, raw, hash_password("a" * 12), now=expires_at) is None
    assert _token_row(Session, raw).used_at is None

    # one second before expiry -> accepted, and used_at round-trips as given
    used = expires_at - timedelta(seconds=1)
    new_pw = secrets.token_urlsafe(12)
    assert _consume(Session, raw, hash_password(new_pw), now=used) == uid
    assert _utc(_token_row(Session, raw).used_at) == used