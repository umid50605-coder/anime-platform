import logging

import pytest
from app.core.database import get_db
from app.core.logging.middleware import REQUEST_ID_HEADER
from sqlalchemy.exc import OperationalError


def test_plain_request_gets_a_request_id(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) > 0


def test_client_supplied_valid_request_id_is_echoed_back(client):
    response = client.get("/health", headers={REQUEST_ID_HEADER: "my-custom-id-123"})
    assert response.headers[REQUEST_ID_HEADER] == "my-custom-id-123"


def test_client_supplied_unsafe_request_id_is_replaced(client):
    """An unsafe value (would break header/log formatting) must not be reflected verbatim."""
    unsafe = "bad\r\nX-Injected: evil"
    response = client.get("/health", headers={REQUEST_ID_HEADER: unsafe})
    assert response.headers[REQUEST_ID_HEADER] != unsafe


def test_non_ascii_request_id_is_rejected_by_the_validator():
    """
    Charset is ASCII letters/digits and -_. only - NOT Python's str.isalnum(),
    which is Unicode-aware and would accept e.g. 'é' or Cyrillic. Tested
    directly against the validator rather than through an HTTP round-trip:
    httpx itself refuses to send a raw non-ASCII string as a header value
    (UnicodeEncodeError, client-side, before the request reaches the
    server) - that's httpx enforcing the HTTP spec, not this app's
    behavior, so it's the wrong thing to route this check through. This
    also means a value that's alphanumeric by Unicode's definition but not
    ASCII can only plausibly reach the server as already-decoded-by-the-ASGI-
    server bytes, not as a literal Python string an HTTP client sends - the
    validator itself is the right place to pin this down.
    """
    from app.core.logging.middleware import _is_safe_request_id

    assert _is_safe_request_id("héllo-id-123") is False
    assert _is_safe_request_id("тест-456") is False  # Cyrillic, also str.isalnum()
    assert _is_safe_request_id("plain-ascii-123") is True


def test_request_log_contains_method_path_status_duration_and_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.core.logging.middleware"):
        response = client.get("/health", headers={REQUEST_ID_HEADER: "req-abc-123"})

    request_logs = [
        r
        for r in caplog.records
        if r.name == "app.core.logging.middleware" and "request method=" in r.getMessage()
    ]
    assert len(request_logs) == 1
    record = request_logs[0]
    message = record.getMessage()

    assert "method=GET" in message
    assert "path=/health" in message
    assert f"status={response.status_code}" in message
    assert "duration_ms=" in message
    assert record.request_id == "req-abc-123"


def test_exception_log_contains_request_id(client, caplog):
    """
    Forces a real unhandled exception through the real request pipeline (by
    overriding get_db, the way the existing `client` fixture already does)
    rather than adding a new route, so this exercises the actual global
    exception handler in app.main.

    Uses a client with raise_server_exceptions=False: Starlette's TestClient
    re-raises a server-side exception into the test process by default (see
    ServerErrorMiddleware - "We always continue to raise the exception...
    allows test clients to optionally raise the error within the test
    case"), even though the app itself already handled it and sent a
    proper response. That default is for catching *accidental* exceptions;
    here the exception is the whole point of the test; without this flag
    the exception would come out of client.get() itself rather than being
    observable as a response.
    """
    from fastapi.testclient import TestClient

    def broken_get_db():
        raise RuntimeError("simulated database outage")
        yield  # pragma: no cover - unreachable, keeps this a generator

    client.app.dependency_overrides[get_db] = broken_get_db
    local_client = TestClient(client.app, raise_server_exceptions=False)
    try:
        with caplog.at_level(logging.ERROR):
            response = local_client.get("/api/anime/", headers={REQUEST_ID_HEADER: "req-error-1"})
    finally:
        # Restore the working override the `client` fixture installed.
        from tests.backend.conftest import db_session as _unused  # noqa: F401

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "req-error-1"
    assert response.json() == {"detail": "Internal server error"}

    exception_logs = [r for r in caplog.records if "unhandled exception" in r.getMessage()]
    assert len(exception_logs) == 1
    record = exception_logs[0]
    assert record.request_id == "req-error-1"
    assert "exception_type=RuntimeError" in record.getMessage()
    assert "path=/api/anime/" in record.getMessage()


def test_request_errored_log_contains_method_path_status_and_duration(client, caplog):
    """
    Distinct from test_exception_log_contains_request_id above: that test
    checks app.main's "unhandled exception" log line (the handler).
    This one checks RequestContextMiddleware's own "request errored" line -
    the request-lifecycle log for a request that ends in an exception,
    which must carry status=500 the same way a normal response's
    request-lifecycle log line carries its real status code.
    """
    from fastapi.testclient import TestClient

    def broken_get_db():
        raise RuntimeError("simulated database outage")
        yield  # pragma: no cover - unreachable, keeps this a generator

    client.app.dependency_overrides[get_db] = broken_get_db
    local_client = TestClient(client.app, raise_server_exceptions=False)
    try:
        with caplog.at_level(logging.ERROR, logger="app.core.logging.middleware"):
            local_client.get("/api/anime/", headers={REQUEST_ID_HEADER: "req-error-2"})
    finally:
        from tests.backend.conftest import db_session as _unused  # noqa: F401

    errored_logs = [r for r in caplog.records if "request errored" in r.getMessage()]
    assert len(errored_logs) == 1
    message = errored_logs[0].getMessage()
    assert "method=GET" in message
    assert "path=/api/anime/" in message
    assert "status=500" in message
    assert "duration_ms=" in message
    assert errored_logs[0].request_id == "req-error-2"


def test_sensitive_data_is_never_logged(client, caplog):
    password = "SuperSecretPassword123!"
    with caplog.at_level(logging.DEBUG):
        register_resp = client.post(
            "/api/auth/register",
            json={"email": "secretive@example.com", "password": password},
        )
        assert register_resp.status_code == 201

        login_resp = client.post(
            "/api/auth/login",
            data={"username": "secretive@example.com", "password": password},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})

    assert password not in caplog.text
    assert token not in caplog.text
    assert "Bearer " not in caplog.text


def test_sequential_requests_do_not_leak_request_ids(client):
    """
    Guards the specific mechanism change in middleware.py (no more
    reset_request_id() in a finally - see its comment for why): confirms
    that not resetting still can't leak one request's ID into the next.
    """
    first = client.get("/health", headers={REQUEST_ID_HEADER: "first-request"})
    second = client.get("/health")  # no header - server generates a fresh one
    third = client.get("/health", headers={REQUEST_ID_HEADER: "third-request"})

    assert first.headers[REQUEST_ID_HEADER] == "first-request"
    assert second.headers[REQUEST_ID_HEADER] != "first-request"
    assert third.headers[REQUEST_ID_HEADER] == "third-request"


def test_login_failure_is_logged_as_warning_without_credentials(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.api.auth.router"):
        response = client.post(
            "/api/auth/login",
            data={"username": "nobody@example.com", "password": "whatever-this-is"},
        )
    assert response.status_code == 401

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("login failed" in r.getMessage() for r in warnings)
    assert "whatever-this-is" not in caplog.text
    assert "nobody@example.com" not in caplog.text


def test_unauthorized_access_is_logged_as_warning(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.security.auth"):
        response = client.get("/api/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
    assert any("unauthorized access attempt" in r.getMessage() for r in caplog.records)


def test_db_session_logs_sqlalchemy_errors_and_reraises(caplog):
    """
    Exercises app.core.database.session.get_db directly as a generator
    (the same protocol FastAPI itself uses for a `yield`-based dependency):
    throwing an exception in at the `yield` point is exactly what happens
    when code using the yielded session raises. Unit-tested in isolation
    here rather than only through HTTP, since triggering a *real* DB
    constraint violation through the API would mean deliberately bypassing
    the application-level checks that already prevent one (see
    UserRepository/FavoriteRepository) - this is the correct scope for this
    test: the error-handling contract of get_db itself.
    """
    from app.core.database.session import get_db as raw_get_db

    gen = raw_get_db()
    next(gen)  # advance to `yield db`

    fake_error = OperationalError("SELECT 1", {}, Exception("connection refused"))
    with caplog.at_level(logging.ERROR, logger="app.core.database.session"):
        with pytest.raises(OperationalError):
            gen.throw(fake_error)

    db_error_logs = [r for r in caplog.records if "database error" in r.getMessage()]
    assert len(db_error_logs) == 1
    assert "exception_type=OperationalError" in db_error_logs[0].getMessage()
    # Never leak the query or the underlying driver error (which could
    # contain connection details) - only the exception type.
    assert "connection refused" not in caplog.text
    assert "SELECT 1" not in caplog.text


def test_db_session_does_not_special_case_non_sqlalchemy_errors(caplog):
    """A non-DB exception passing through get_db isn't relabeled as a DB error."""
    from app.core.database.session import get_db as raw_get_db

    gen = raw_get_db()
    next(gen)

    with caplog.at_level(logging.ERROR, logger="app.core.database.session"):
        with pytest.raises(ValueError):
            gen.throw(ValueError("not a database error"))

    assert [r for r in caplog.records if r.name == "app.core.database.session"] == []


def test_anime_provider_failure_is_logged_without_leaking_details(caplog):
    """
    LoggingAnimeProvider (app/integrations/anime_api/logging_provider.py) is
    a transparent decorator with no HTTP surface of its own, so it's unit
    tested directly against a fake failing delegate - the same approach
    test_watch_service.py uses for its fakes.
    """
    from app.integrations.anime_api.logging_provider import LoggingAnimeProvider
    from app.integrations.anime_api.provider import AnimeProvider

    class FailingAnimeProvider(AnimeProvider):
        name = "fake-vendor"

        def get_anime(self, external_id):
            raise RuntimeError("upstream said: api_key=super-secret-123 invalid")

        def search_anime(self, query):
            raise RuntimeError("boom")

        def list_episodes(self, external_id):
            raise RuntimeError("boom")

    provider = LoggingAnimeProvider(FailingAnimeProvider())

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            provider.get_anime("mock-1")

    failure_logs = [r for r in caplog.records if "anime provider failure" in r.getMessage()]
    assert len(failure_logs) == 1
    assert "provider=fake-vendor" in failure_logs[0].getMessage()
    assert "operation=get_anime" in failure_logs[0].getMessage()
    assert "external_id=mock-1" in failure_logs[0].getMessage()
    # The delegate's exception message (which could carry secrets from a real
    # vendor's error body) must never reach the log - only our own fields do.
    assert "super-secret-123" not in caplog.text


def test_video_provider_failure_is_logged_without_leaking_details(caplog):
    from app.integrations.video_source.logging_provider import LoggingVideoProvider
    from app.integrations.video_source.provider import VideoProvider

    class FailingVideoProvider(VideoProvider):
        def get_stream(self, external_episode_id):
            raise RuntimeError("upstream token=leaked-token-xyz rejected")

    provider = LoggingVideoProvider(FailingVideoProvider())

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            provider.get_stream("ep-1")

    failure_logs = [r for r in caplog.records if "video provider failure" in r.getMessage()]
    assert len(failure_logs) == 1
    assert "external_episode_id=ep-1" in failure_logs[0].getMessage()
    assert "leaked-token-xyz" not in caplog.text
