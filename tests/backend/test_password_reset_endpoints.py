"""
HTTP-level tests for the password-reset workflow (Task 10).
See docs/decisions/0005-password-reset.md.
"""

import logging
import re
from datetime import UTC, datetime, timedelta

from app.core.security import hash_password_reset_token
from app.integrations.email import get_email_sender
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset import PasswordResetTokenRepository
from fastapi.testclient import TestClient

EMAIL = "reset-user@example.com"
OLD_PASSWORD = "OldPassword-123"
NEW_PASSWORD = "BrandNewPassword-456"
ORIGIN = {"Origin": "http://localhost:5173"}
GENERIC_INVALID = {"detail": "Invalid or expired reset token"}


def _register(client, email=EMAIL, password=OLD_PASSWORD):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201
    return response.json()["id"]


def _login(client, password, email=EMAIL):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def _forgot(client, email=EMAIL):
    return client.post("/api/auth/forgot-password", json={"email": email})


def _reset(client, token, password=NEW_PASSWORD):
    return client.post("/api/auth/reset-password", json={"token": token, "new_password": password})


def _outbox():
    return get_email_sender().outbox


def _token_from(message) -> str:
    match = re.search(r"#token=([A-Za-z0-9_-]+)", message.body)
    assert match, "reset email must contain a #token= link"
    return match.group(1)


def _issue_token(client) -> str:
    """Register nothing; request a reset for EMAIL and return the raw token from the email."""
    assert _forgot(client).status_code == 202
    return _token_from(_outbox()[-1])


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- forgot-password ---------------------------------------------------------


def test_forgot_password_response_is_identical_for_existing_and_unknown_email(client):
    _register(client)

    existing = _forgot(client, EMAIL)
    unknown = _forgot(client, "nobody-registered@example.com")

    assert existing.status_code == unknown.status_code == 202
    assert existing.json() == unknown.json()
    assert existing.headers.get("content-type") == unknown.headers.get("content-type")
    # The response is generic, but mail still only goes to the real account.
    assert [m.to for m in _outbox()] == [EMAIL]


def test_forgot_password_does_not_email_inactive_accounts(client, db_session):
    _register(client)
    db_session.query(User).filter(User.email == EMAIL).update({User.is_active: False})
    db_session.commit()

    response = _forgot(client)

    assert response.status_code == 202
    assert len(_outbox()) == 0


def test_forgot_password_email_carries_a_fragment_link_not_a_query_string(client):
    _register(client)
    _forgot(client)

    body = _outbox()[-1].body
    assert "/reset-password#token=" in body
    assert "?token=" not in body and "&token=" not in body
    assert len(_token_from(_outbox()[-1])) >= 32


def test_forgot_password_stores_only_a_hash_of_the_token(client, db_session):
    _register(client)
    raw_token = _issue_token(client)

    rows = db_session.query(PasswordResetToken).all()

    assert len(rows) == 1
    assert rows[0].token_hash == hash_password_reset_token(raw_token)
    assert rows[0].token_hash != raw_token
    assert raw_token not in {str(v) for v in vars(rows[0]).values()}
    assert rows[0].used_at is None
    assert rows[0].expires_at > datetime.now(UTC).replace(tzinfo=None) or rows[0].expires_at.tzinfo


def test_forgot_password_rejects_a_malformed_email(client):
    response = client.post("/api/auth/forgot-password", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert len(_outbox()) == 0


def test_forgot_password_stays_generic_when_email_delivery_fails(client, monkeypatch):
    _register(client)
    unknown_response = _forgot(client, "nobody-registered@example.com")

    def failing_send(message):
        raise RuntimeError("smtp exploded")

    monkeypatch.setattr(get_email_sender(), "send", failing_send)
    failing_response = _forgot(client, EMAIL)

    # A delivery error that only real accounts could trigger would reveal them.
    assert failing_response.status_code == unknown_response.status_code == 202
    assert failing_response.json() == unknown_response.json()


# --- reset-password: success -------------------------------------------------


def test_valid_token_resets_the_password(client, db_session):
    _register(client)
    token = _issue_token(client)

    response = _reset(client, token)

    assert response.status_code == 200
    assert "reset" in response.json()["detail"].lower()
    row = db_session.query(PasswordResetToken).one()
    assert row.used_at is not None


def test_old_password_stops_working_and_new_password_works(client):
    _register(client)
    token = _issue_token(client)
    assert _login(client, OLD_PASSWORD).status_code == 200  # works before the reset

    assert _reset(client, token).status_code == 200

    assert _login(client, OLD_PASSWORD).status_code == 401
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_login_refresh_and_logout_still_work_after_a_reset(client):
    _register(client)
    assert _reset(client, _issue_token(client)).status_code == 200

    assert _login(client, NEW_PASSWORD).status_code == 200
    assert client.post("/api/auth/refresh", headers=ORIGIN).status_code == 200
    assert client.post("/api/auth/logout", headers=ORIGIN).status_code == 204


# --- reset-password: rejection ------------------------------------------------


def test_unknown_token_is_rejected(client):
    _register(client)

    response = _reset(client, "this-token-was-never-issued")

    assert response.status_code == 400
    assert response.json() == GENERIC_INVALID


def test_expired_token_is_rejected_and_password_is_unchanged(client, db_session):
    user_id = _register(client)
    raw_token = "an-expired-but-otherwise-valid-token"
    PasswordResetTokenRepository(db_session).create(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_password_reset_token(raw_token),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )

    response = _reset(client, raw_token)

    assert response.status_code == 400
    assert response.json() == GENERIC_INVALID
    assert _login(client, OLD_PASSWORD).status_code == 200


def test_used_token_cannot_be_used_a_second_time(client):
    _register(client)
    token = _issue_token(client)
    assert _reset(client, token, NEW_PASSWORD).status_code == 200

    second = _reset(client, token, "AttackerChosen-Password-9")

    assert second.status_code == 400
    assert second.json() == GENERIC_INVALID
    # The second attempt must not have changed the password a second time.
    assert _login(client, NEW_PASSWORD).status_code == 200
    assert _login(client, "AttackerChosen-Password-9").status_code == 401


def test_invalid_expired_and_used_tokens_are_indistinguishable(client, db_session):
    user_id = _register(client)
    used = _issue_token(client)
    _reset(client, used)
    PasswordResetTokenRepository(db_session).create(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_password_reset_token("expired-token"),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )

    responses = [_reset(client, t) for t in ("never-issued", "expired-token", used)]

    assert {r.status_code for r in responses} == {400}
    assert all(r.json() == GENERIC_INVALID for r in responses)


def test_a_too_short_password_is_rejected_without_spending_the_token(client):
    _register(client)
    token = _issue_token(client)

    short = _reset(client, token, "short")
    assert short.status_code == 422

    # The token is still good for a valid password.
    assert _reset(client, token, NEW_PASSWORD).status_code == 200


def test_password_over_the_maximum_length_is_rejected(client):
    _register(client)
    token = _issue_token(client)
    assert _reset(client, token, "x" * 129).status_code == 422


def test_reset_with_an_empty_token_is_a_validation_error(client):
    assert _reset(client, "").status_code == 422


# --- session invalidation -----------------------------------------------------


def test_reset_revokes_every_refresh_session_and_access_token_of_the_user(client):
    _register(client)
    login_a = _login(client, OLD_PASSWORD)  # browser A
    browser_b = TestClient(client.app)  # a second, independent browser
    login_b = _login(browser_b, OLD_PASSWORD)
    token_a, token_b = login_a.json()["access_token"], login_b.json()["access_token"]
    assert client.get("/api/users/me", headers=_bearer(token_a)).status_code == 200
    assert client.get("/api/users/me", headers=_bearer(token_b)).status_code == 200

    assert _reset(client, _issue_token(client)).status_code == 200

    # Existing access tokens are cut off immediately, not after they expire...
    assert client.get("/api/users/me", headers=_bearer(token_a)).status_code == 401
    assert client.get("/api/users/me", headers=_bearer(token_b)).status_code == 401
    # ...and neither browser can mint a new one from its refresh cookie.
    assert client.post("/api/auth/refresh", headers=ORIGIN).status_code == 401
    assert browser_b.post("/api/auth/refresh", headers=ORIGIN).status_code == 401


def test_reset_does_not_affect_other_users(client):
    _register(client)
    _register(client, email="bystander@example.com", password="Bystander-Pass-1")
    bystander = TestClient(client.app)
    bystander_login = _login(bystander, "Bystander-Pass-1", email="bystander@example.com")
    bystander_token = bystander_login.json()["access_token"]

    assert _reset(client, _issue_token(client)).status_code == 200

    assert bystander.get("/api/users/me", headers=_bearer(bystander_token)).status_code == 200
    assert bystander.post("/api/auth/refresh", headers=ORIGIN).status_code == 200
    assert _login(client, "Bystander-Pass-1", email="bystander@example.com").status_code == 200


def test_other_outstanding_reset_links_die_when_one_is_used(client):
    _register(client)
    first = _issue_token(client)
    second = _issue_token(client)
    assert first != second

    assert _reset(client, first).status_code == 200

    assert _reset(client, second, "Another-New-Password-7").status_code == 400
    assert _login(client, NEW_PASSWORD).status_code == 200


# --- logging -------------------------------------------------------------------


def test_raw_tokens_and_passwords_are_never_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    _register(client)
    _forgot(client, EMAIL)
    _forgot(client, "nobody-registered@example.com")
    raw_token = _token_from(_outbox()[-1])
    reset_url = re.search(r"https?://\S+", _outbox()[-1].body).group(0)

    _reset(client, "wrong-token-value-abc123")  # failure path
    _reset(client, raw_token, NEW_PASSWORD)  # success path
    _reset(client, raw_token, NEW_PASSWORD)  # reuse failure path

    secrets = [raw_token, reset_url, NEW_PASSWORD, OLD_PASSWORD, "wrong-token-value-abc123"]
    for secret in secrets:
        assert secret not in caplog.text, f"secret leaked into logs: {secret[:6]}..."
        for record in caplog.records:
            assert secret not in record.getMessage()
            assert secret not in str(record.args)
    # Not vacuous: the events themselves are logged.
    assert "password reset succeeded" in caplog.text
    assert "password reset failed" in caplog.text
    assert "password reset email sent" in caplog.text


def test_failed_email_delivery_logs_only_the_exception_type(client, caplog, monkeypatch):
    _register(client)

    def failing_send(message):
        raise RuntimeError(f"vendor rejected body: {message.body}")

    monkeypatch.setattr(get_email_sender(), "send", failing_send)
    with caplog.at_level(logging.ERROR):
        _forgot(client)

    assert "exception_type=RuntimeError" in caplog.text
    assert "vendor rejected body" not in caplog.text
    assert "#token=" not in caplog.text


# --- rate limiting ---------------------------------------------------------------


def test_forgot_password_is_rate_limited_per_ip(client):
    for _ in range(5):
        assert _forgot(client, "anyone@example.com").status_code == 202

    blocked = _forgot(client, "anyone@example.com")

    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60


def test_reset_password_is_rate_limited_per_ip(client):
    for _ in range(5):
        assert _reset(client, "guess").status_code == 400

    blocked = _reset(client, "guess")

    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60


def test_password_reset_limits_are_independent_of_each_other_and_of_login(client):
    for _ in range(5):
        _forgot(client, "anyone@example.com")
    assert _forgot(client, "anyone@example.com").status_code == 429

    assert _reset(client, "guess").status_code == 400  # reset has its own counter
    assert _login(client, "x", email="nobody@example.com").status_code == 401  # not 429


def test_a_different_ip_has_its_own_password_reset_limit(client):
    for _ in range(5):
        _forgot(client, "anyone@example.com")
    assert _forgot(client, "anyone@example.com").status_code == 429

    other_ip = TestClient(client.app, client=("9.9.9.9", 12345))
    assert _forgot(other_ip, "anyone@example.com").status_code == 202


def test_public_endpoints_are_unaffected_by_password_reset_rate_limits(client):
    for _ in range(6):
        _forgot(client, "anyone@example.com")

    assert client.get("/api/anime/").status_code == 200
    assert client.get("/health").status_code == 200
