"""
MySQL integration tests for Task 11 - Email Verification.

Run ONLY when MYSQL_TEST_DATABASE_URL is set, and ONLY against the
`anime_metadata_migration_test` database (the fixture refuses anything else).
Schema is NOT created here - run `alembic upgrade head` on the test database
first. Every row created is tracked by id and deleted afterwards.

    read -rsp "MySQL test URL: " MYSQL_TEST_DATABASE_URL; echo
    export MYSQL_TEST_DATABASE_URL
    python -m pytest -v --tb=short tests/backend/test_email_verification_mysql.py
"""

import os
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import app.models  # noqa: F401 registers all models on Base.metadata
import pytest
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_email_verification_token,
    hash_email_verification_token,
    hash_password,
)
from app.integrations.email import EmailMessage, EmailSender
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.repositories.email_verification import EmailVerificationTokenRepository
from app.repositories.user import UserRepository
from app.services.email_verification import EmailVerificationService
from app.services.user import UserService
from sqlalchemy import create_engine, delete, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

TEST_DB_NAME = "anime_metadata_migration_test"
_URL = os.environ.get("MYSQL_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not _URL, reason="MYSQL_TEST_DATABASE_URL is not set")


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
def Session(engine):  # noqa: N802
    return sessionmaker(autoflush=False, bind=engine)


class _World:
    def __init__(self, session_factory):
        self.Session = session_factory
        self.user_ids: list[str] = []

    def new_user(self, active=True, verified=False, email=None) -> str:
        user = User(
            email=email or f"mysqlit_{uuid.uuid4().hex}@example.test",
            hashed_password=hash_password("x" * 12),
            is_active=active,
            email_verified_at=datetime.now(UTC).replace(microsecond=0) if verified else None,
        )
        with self.Session() as s:
            s.add(user)
            s.commit()
            uid = user.id
        self.user_ids.append(uid)
        return uid

    def add_token(self, user_id, expires_in=timedelta(hours=1)) -> str:
        raw = create_email_verification_token()
        with self.Session() as s:
            EmailVerificationTokenRepository(s).create(
                EmailVerificationToken(
                    user_id=user_id,
                    token_hash=hash_email_verification_token(raw),
                    expires_at=datetime.now(UTC).replace(microsecond=0) + expires_in,
                )
            )
        return raw

    def cleanup(self):
        if not self.user_ids:
            return
        with self.Session() as s:
            s.execute(
                delete(EmailVerificationToken).where(
                    EmailVerificationToken.user_id.in_(self.user_ids)
                )
            )
            s.execute(delete(User).where(User.id.in_(self.user_ids)))
            s.commit()


@pytest.fixture()
def world(Session):  # noqa: N803
    w = _World(Session)
    try:
        yield w
    finally:
        w.cleanup()


def _verify(Session, raw):  # noqa: N803
    with Session() as s:
        return EmailVerificationTokenRepository(s).consume_and_verify(
            hash_email_verification_token(raw)
        )


def _state(Session, uid):  # noqa: N803
    with Session() as s:
        user = s.get(User, uid)
        tokens = s.scalars(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == uid)
        ).all()
        return user.email_verified_at, [t.used_at for t in tokens]


# ---- schema ---------------------------------------------------------------


def test_schema_matches_migration(engine):
    insp = inspect(engine)
    assert "email_verified_at" in {c["name"] for c in insp.get_columns("users")}
    cols = {c["name"] for c in insp.get_columns("email_verification_tokens")}
    assert cols == {"id", "user_id", "token_hash", "created_at", "expires_at", "used_at"}
    idx = {i["name"]: i for i in insp.get_indexes("email_verification_tokens")}
    assert idx["ix_email_verification_tokens_token_hash"]["unique"]
    assert "ix_email_verification_tokens_user_id" in idx
    assert insp.get_foreign_keys("email_verification_tokens")[0]["referred_table"] == "users"


def test_unique_token_hash_and_fk_are_enforced(world, Session):  # noqa: N803
    uid = world.new_user()
    raw = world.add_token(uid)
    with Session() as s, pytest.raises(IntegrityError):
        s.add(
            EmailVerificationToken(
                user_id=uid,
                token_hash=hash_email_verification_token(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        s.commit()
    with Session() as s, pytest.raises(IntegrityError):
        s.add(
            EmailVerificationToken(
                user_id=str(uuid.uuid4()),  # no such user
                token_hash="f" * 64,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        s.commit()


# ---- behaviour ------------------------------------------------------------


def test_verify_marks_user_and_consumes_token(world, Session):  # noqa: N803
    uid = world.new_user()
    raw = world.add_token(uid)
    assert _verify(Session, raw) == uid
    verified_at, used = _state(Session, uid)
    assert verified_at is not None and all(u is not None for u in used)
    assert _verify(Session, raw) is None  # single use


def test_expired_unknown_and_inactive_change_nothing(world, Session):  # noqa: N803
    uid = world.new_user()
    expired = world.add_token(uid, expires_in=timedelta(seconds=-5))
    assert _verify(Session, expired) is None
    assert _verify(Session, "unknown-token") is None
    assert _state(Session, uid) == (None, [None])
    inactive = world.new_user(active=False)
    raw = world.add_token(inactive)
    assert _verify(Session, raw) is None
    assert _state(Session, inactive) == (None, [None])  # token stays unspent (rolled back)


def test_other_outstanding_tokens_are_expired_on_success(world, Session):  # noqa: N803
    uid = world.new_user()
    first, second = world.add_token(uid), world.add_token(uid)
    assert _verify(Session, first) == uid
    assert _verify(Session, second) is None
    assert all(u is not None for u in _state(Session, uid)[1])


def test_verified_at_is_not_overwritten_when_already_verified(world, Session):  # noqa: N803
    uid = world.new_user(verified=True)
    before, _ = _state(Session, uid)
    raw = world.add_token(uid)
    assert _verify(Session, raw) == uid
    after, _ = _state(Session, uid)
    assert after == before


# ---- real concurrency (separate connections/threads) -----------------------


def _race(Session, raws, n_threads):  # noqa: N803
    barrier = threading.Barrier(n_threads)
    results, errors = [], []

    def worker(raw):
        try:
            barrier.wait(timeout=10)
            results.append(_verify(Session, raw))
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertions below
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(raws[i % len(raws)],)) for i in range(n_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results, errors


def test_concurrent_verification_same_token_exactly_one_wins(world, Session):  # noqa: N803
    uid = world.new_user()
    raw = world.add_token(uid)
    results, errors = _race(Session, [raw], 12)
    assert errors == []
    assert sum(r == uid for r in results) == 1
    assert sum(r is None for r in results) == 11
    verified_at, used = _state(Session, uid)
    assert verified_at is not None and all(u is not None for u in used)


def test_concurrent_verification_different_tokens_same_user_no_deadlock(world, Session):  # noqa: N803
    uid = world.new_user()
    raws = [world.add_token(uid) for _ in range(5)]
    results, errors = _race(Session, raws, 10)
    assert errors == [], f"unexpected DB errors (e.g. deadlock 1213): {errors}"
    assert sum(r == uid for r in results) == 1
    verified_at, used = _state(Session, uid)
    assert verified_at is not None and all(u is not None for u in used)


# ---- concurrent RESEND (W3) ------------------------------------------------
#
# Every worker thread has its OWN Session/connection (like production request
# handlers) and all threads are released together by a Barrier. They go through
# the public resend path (user lookup + throttling + token insert + send), so
# the InnoDB REPEATABLE READ snapshot behaviour is part of what is tested.
# These tests need the real send path: `real_verification_email` (opt-in marker
# from conftest.py).


class _CountingSender(EmailSender):
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self._lock = threading.Lock()

    def send(self, message: EmailMessage) -> None:
        with self._lock:
            self.sent.append(message)


class _BlockingSender(EmailSender):
    """Blocks inside send() until released - stands in for a slow SMTP server."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.sent = 0

    def send(self, message: EmailMessage) -> None:
        self.entered.set()
        assert self.release.wait(timeout=20), "test never released the sender"
        self.sent += 1


def _service(session, sender):
    return EmailVerificationService(
        UserService(UserRepository(session)), EmailVerificationTokenRepository(session), sender
    )


def _email_of(Session, uid):  # noqa: N803
    with Session() as s:
        return s.get(User, uid).email


def _token_count(Session, uid):  # noqa: N803
    with Session() as s:
        return s.scalar(
            select(func.count(EmailVerificationToken.id)).where(
                EmailVerificationToken.user_id == uid
            )
        )


def _age_tokens(Session, uid, seconds):  # noqa: N803
    with Session() as s:
        s.execute(
            update(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == uid)
            .values(
                created_at=datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=seconds)
            )
        )
        s.commit()


def _run_parallel(jobs):
    """Run callables in parallel threads released together; returns their errors."""
    barrier = threading.Barrier(len(jobs))
    errors: list[BaseException] = []

    def runner(job):
        try:
            job(barrier)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertions
            errors.append(exc)

    threads = [threading.Thread(target=runner, args=(job,)) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "worker thread hung"
    return errors


def _resend_job(Session, email, sender):  # noqa: N803
    def job(barrier):
        with Session() as s:
            svc = _service(s, sender)
            barrier.wait(timeout=10)
            svc.resend_for_email(email)

    return job


@pytest.mark.usefixtures("real_verification_email")
def test_concurrent_resend_cooldown_cannot_be_bypassed(world, Session):  # noqa: N803
    uid = world.new_user()
    sender = _CountingSender()
    errors = _run_parallel([_resend_job(Session, _email_of(Session, uid), sender)] * 12)
    assert errors == []
    assert _token_count(Session, uid) == 1  # 60 s cooldown: one winner
    assert len(sender.sent) == 1  # rejected requests send nothing


@pytest.mark.usefixtures("real_verification_email")
def test_concurrent_resend_hourly_cap_is_preserved(world, Session, monkeypatch):  # noqa: N803
    # Cooldown switched off so ONLY the hourly cap (default 5/hour) limits this
    # run. -5 rather than 0: MySQL DATETIME has no fractional seconds and rounds,
    # so a stored created_at can sit up to ~0.5 s ahead of the clock; a cooldown
    # of exactly 0 would sporadically reject on that rounding, not on the cap.
    monkeypatch.setattr(get_settings(), "email_verification_resend_cooldown_seconds", -5)
    cap = get_settings().email_verification_max_sends_per_hour
    uid = world.new_user()
    for _ in range(cap - 2):  # leave room for exactly 2 more
        world.add_token(uid)
    _age_tokens(Session, uid, 120)
    sender = _CountingSender()
    errors = _run_parallel([_resend_job(Session, _email_of(Session, uid), sender)] * 12)
    assert errors == []
    assert _token_count(Session, uid) == cap
    assert len(sender.sent) == 2


@pytest.mark.usefixtures("real_verification_email")
def test_concurrent_resend_at_the_hourly_cap_creates_and_sends_nothing(
    world, Session  # noqa: N803
):
    cap = get_settings().email_verification_max_sends_per_hour
    uid = world.new_user()
    for _ in range(cap):
        world.add_token(uid)
    _age_tokens(Session, uid, 120)  # outside the cooldown, inside the hour
    sender = _CountingSender()
    errors = _run_parallel([_resend_job(Session, _email_of(Session, uid), sender)] * 12)
    assert errors == []
    assert _token_count(Session, uid) == cap
    assert sender.sent == []


@pytest.mark.usefixtures("real_verification_email")
def test_concurrent_resend_for_different_users_each_get_exactly_one(world, Session):  # noqa: N803
    a, b = world.new_user(), world.new_user()
    sender = _CountingSender()
    jobs = []
    for uid in (a, b):
        jobs += [_resend_job(Session, _email_of(Session, uid), sender)] * 8
    assert _run_parallel(jobs) == []
    assert _token_count(Session, a) == 1 and _token_count(Session, b) == 1
    assert sorted(m.to for m in sender.sent) == sorted(
        [_email_of(Session, a), _email_of(Session, b)]
    )


@pytest.mark.usefixtures("real_verification_email")
def test_resend_serialises_on_the_user_row_without_blocking_other_users(
    world, Session  # noqa: N803
):
    a, b = world.new_user(), world.new_user()
    sender = _CountingSender()
    holder = Session()
    holder.execute(text("SELECT id FROM users WHERE id = :i FOR UPDATE"), {"i": a})  # hold A
    done_a, done_b = threading.Event(), threading.Event()

    def run(uid, done):
        with Session() as s:
            _service(s, sender).resend_for_email(_email_of(Session, uid))
        done.set()

    ta = threading.Thread(target=run, args=(a, done_a))
    tb = threading.Thread(target=run, args=(b, done_b))
    ta.start()
    tb.start()
    try:
        assert done_b.wait(timeout=10), "resend for another user was blocked by A's row lock"
        time.sleep(1.0)
        assert not done_a.is_set(), "resend for A did not wait for A's row lock"
    finally:
        holder.rollback()
        holder.close()
    assert done_a.wait(timeout=15)
    ta.join(timeout=5)
    tb.join(timeout=5)
    assert _token_count(Session, a) == 1 and _token_count(Session, b) == 1


@pytest.mark.usefixtures("real_verification_email")
def test_no_database_lock_is_held_while_the_email_is_being_sent(world, Session):  # noqa: N803
    uid = world.new_user()
    sender = _BlockingSender()
    worker = threading.Thread(
        target=lambda: _resend_job(Session, _email_of(Session, uid), sender)(
            threading.Barrier(1)
        )
    )
    worker.start()
    try:
        assert sender.entered.wait(timeout=15), "send() was never reached"
        with Session() as other:
            other.execute(text("SET SESSION innodb_lock_wait_timeout = 3"))
            started = time.monotonic()
            other.execute(text("SELECT id FROM users WHERE id = :i FOR UPDATE"), {"i": uid})
            elapsed = time.monotonic() - started
            other.rollback()
        assert elapsed < 2.0, f"user row was still locked while sending ({elapsed:.1f}s)"
    finally:
        sender.release.set()
        worker.join(timeout=20)
    assert sender.sent == 1 and _token_count(Session, uid) == 1


@pytest.mark.usefixtures("real_verification_email")
def test_concurrent_resend_and_verify_do_not_deadlock_and_end_consistent(
    world, Session  # noqa: N803
):
    uid = world.new_user()
    raw = world.add_token(uid)
    _age_tokens(Session, uid, 120)  # old enough that a resend is allowed
    email = _email_of(Session, uid)
    sender = _CountingSender()

    def verify_job(barrier):
        with Session() as s:
            repo = EmailVerificationTokenRepository(s)
            barrier.wait(timeout=10)
            repo.consume_and_verify(hash_email_verification_token(raw))

    errors = _run_parallel(
        [_resend_job(Session, email, sender)] * 4 + [verify_job] * 4
    )
    assert errors == [], f"unexpected DB errors (e.g. deadlock 1213): {errors}"
    verified_at, used = _state(Session, uid)
    assert verified_at is not None
    assert all(u is not None for u in used)  # nothing left redeemable after verification


@pytest.mark.usefixtures("real_verification_email")
def test_concurrent_resend_requests_over_http_send_one_email(world, Session):  # noqa: N803
    from app.api.deps import get_email_sender_dep
    from app.main import app
    from fastapi.testclient import TestClient

    # EmailStr rejects the reserved .test TLD used elsewhere in this file.
    uid = world.new_user(email=f"mysqlit_{uuid.uuid4().hex}@example.com")
    email = _email_of(Session, uid)
    sender = _CountingSender()

    def override_db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_email_sender_dep] = lambda: sender
    statuses: list[int] = []
    try:
        def job(barrier):
            with TestClient(app) as c:
                barrier.wait(timeout=10)
                r = c.post("/api/auth/resend-verification", json={"email": email})
                statuses.append(r.status_code)

        errors = _run_parallel([job] * 5)  # 5 = per-IP limit, so none are 429
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_email_sender_dep, None)
    assert errors == []
    assert statuses == [202] * 5
    assert _token_count(Session, uid) == 1
    assert len(sender.sent) == 1
