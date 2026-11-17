"""
Shared fixtures for backend tests.

Each test gets a fresh, isolated in-memory SQLite database - not the
project's dev anime_platform.db file - so tests can never interfere with
each other or with real local data. Tables are created directly from
Base.metadata (not via Alembic) since that is the correct scope for
these tests: verifying application behavior, not the migration files
themselves (those were validated manually - see docs/decisions).
"""

import app.models  # noqa: F401 registers all models on Base.metadata
import pytest
from app.core.database import Base, get_db
from app.core.rate_limit import reset_rate_limiter
from app.integrations.email import reset_email_sender
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """
    Every test shares the same `app` object (imported once, module-level)
    and, by default, the same apparent client IP - Starlette's TestClient
    reports request.client.host as the fixed string "testclient" unless a
    test overrides it. Without this, rate-limit state would accumulate
    across unrelated tests in the same run (e.g. every test in
    test_auth_flow.py hitting /api/auth/register would count against one
    shared counter) rather than each test starting clean.
    """
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.fixture(autouse=True)
def _reset_email_outbox():
    """
    The email sender is a cached process-wide singleton (like the rate limiter),
    so its in-memory outbox would otherwise carry messages - including reset
    links - from one test into the next.
    """
    reset_email_sender()
    yield
    reset_email_sender()


@pytest.fixture(autouse=True)
def _no_verification_email_by_default(request, monkeypatch):
    """
    Registration (Task 11) now emails a verification link into the same
    process-wide outbox the password-reset tests (Task 10, closed) assert on
    ("outbox holds exactly the reset mail"). So that those tests keep their
    original meaning without being edited, sending is a no-op by default.
    Tests that exercise verification email request `real_verification_email`.
    """
    if "real_verification_email" in request.fixturenames:
        return
    from app.services.email_verification import EmailVerificationService

    monkeypatch.setattr(EmailVerificationService, "send_verification_email", lambda *a, **k: False)


@pytest.fixture()
def real_verification_email():
    """Opt-in marker: use the real EmailVerificationService.send_verification_email."""


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
