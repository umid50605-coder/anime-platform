"""
HTTP-level tests for Task 11 - Email Verification.
See docs/decisions/0006-email-verification.md.
"""

import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import hash_email_verification_token
from app.integrations.email import get_email_sender
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User

EMAIL = "verify-user@example.com"
PASSWORD = "CorrectHorse123"
GENERIC_INVALID = {"detail": "Invalid or expired verification token"}

pytestmark = pytest.mark.usefixtures("real_verification_email")


def _register(client, email=EMAIL):
    r = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def _login_headers(client, email=EMAIL):
    r = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _outbox():
    return list(get_email_sender().outbox)


def _token_from(message) -> str:
    m = re.search(r"/verify-email#token=([A-Za-z0-9_-]+)", message.body)
    assert m, "verification email must contain a /verify-email#token= link"
    return m.group(1)


def _verify(client, token):
    return client.post("/api/auth/verify-email", json={"token": token})


def _resend(client, email=EMAIL):
    return client.post("/api/auth/resend-verification", json={"email": email})


def _age_tokens(db, seconds):
    """Make existing tokens look `seconds` old so cooldown logic can be exercised."""
    for t in db.query(EmailVerificationToken).all():
        t.created_at = datetime.now(UTC) - timedelta(seconds=seconds)
    db.commit()


# ---- registration ---------------------------------------------------------


def test_registration_sends_one_verification_email_and_returns_unverified(client):
    body = _register(client)
    assert body["email_verified"] is False
    box = _outbox()
    assert [m.to for m in box] == [EMAIL]
    assert box[0].subject.startswith("Verify")
    assert "/verify-email#token=" in box[0].body
    assert "?token=" not in box[0].body  # fragment, never a query string


def test_registration_contract_preserved_and_duplicate_still_409(client):
    first = _register(client)
    assert set(first) == {"id", "email", "display_name", "created_at", "email_verified"}
    dup = client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert dup.status_code == 409
    assert len(_outbox()) == 1  # a rejected duplicate sends nothing


def test_invalid_email_rejected_and_nothing_sent(client):
    r = client.post("/api/auth/register", json={"email": "not-an-email", "password": PASSWORD})
    assert r.status_code == 422
    assert _outbox() == []


def test_registration_survives_email_delivery_failure(client, monkeypatch):
    sender = get_email_sender()

    def boom(_message):
        raise ConnectionError("smtp down secret-host")

    monkeypatch.setattr(sender, "send", boom)
    r = client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 201  # account exists; user can resend


# ---- token properties -----------------------------------------------------


def test_only_hash_is_stored_and_token_belongs_to_user_with_expiry(client, db_session):
    user_id = _register(client)["id"]
    raw = _token_from(_outbox()[-1])
    rows = db_session.query(EmailVerificationToken).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user_id
    assert row.token_hash == hash_email_verification_token(raw)
    assert raw not in row.token_hash and len(row.token_hash) == 64
    assert row.used_at is None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    assert timedelta(hours=23, minutes=55) < expires - datetime.now(UTC) <= timedelta(hours=24)


def test_tokens_are_unique_and_high_entropy(client, db_session):
    _register(client)
    first = _token_from(_outbox()[-1])
    _age_tokens(db_session, 120)
    _resend(client)
    second = _token_from(_outbox()[-1])
    assert first != second
    assert len(first) >= 43 and len(second) >= 43  # token_urlsafe(32) = 256 bits


# ---- verification ---------------------------------------------------------


def test_valid_token_verifies_account_and_unlocks_gated_features(client):
    _register(client)
    headers = _login_headers(client)
    assert client.get("/api/favorites/", headers=headers).status_code == 403
    r = _verify(client, _token_from(_outbox()[-1]))
    assert r.status_code == 200
    assert client.get("/api/users/me", headers=headers).json()["email_verified"] is True
    # Same access token, no re-login needed: policy reads current DB state.
    assert client.get("/api/favorites/", headers=headers).status_code == 200


@pytest.mark.parametrize("bad", ["nonsense", "A" * 43, "x"])
def test_unknown_token_gets_generic_400(client, bad):
    r = _verify(client, bad)
    assert r.status_code == 400 and r.json() == GENERIC_INVALID


def test_empty_and_oversized_token_rejected_by_schema(client):
    assert _verify(client, "").status_code == 422
    assert _verify(client, "a" * 300).status_code == 422


def test_expired_token_is_rejected_and_account_stays_unverified(client, db_session):
    _register(client)
    token = _token_from(_outbox()[-1])
    db_session.query(EmailVerificationToken).update(
        {EmailVerificationToken.expires_at: datetime.now(UTC) - timedelta(seconds=1)}
    )
    db_session.commit()
    r = _verify(client, token)
    assert r.status_code == 400 and r.json() == GENERIC_INVALID
    assert db_session.query(User).one().email_verified_at is None


def test_token_is_single_use_and_repeat_gets_same_generic_400(client, db_session):
    _register(client)
    token = _token_from(_outbox()[-1])
    assert _verify(client, token).status_code == 200
    again = _verify(client, token)
    assert again.status_code == 400 and again.json() == GENERIC_INVALID
    assert db_session.query(User).one().email_verified_at is not None  # still verified


def test_token_cannot_verify_another_users_account(client, db_session):
    _register(client, "a@example.com")
    token_a = _token_from(_outbox()[-1])
    _register(client, "b@example.com")
    assert _verify(client, token_a).status_code == 200
    by_email = {u.email: u for u in db_session.query(User).all()}
    assert by_email["a@example.com"].email_verified_at is not None
    assert by_email["b@example.com"].email_verified_at is None


def test_successful_verification_invalidates_other_outstanding_tokens(client, db_session):
    _register(client)
    first = _token_from(_outbox()[-1])
    _age_tokens(db_session, 120)
    _resend(client)
    second = _token_from(_outbox()[-1])
    assert _verify(client, second).status_code == 200
    assert _verify(client, first).status_code == 400
    assert db_session.query(EmailVerificationToken).filter_by(used_at=None).count() == 0


def test_inactive_user_cannot_verify_and_token_stays_unspent(client, db_session):
    _register(client)
    token = _token_from(_outbox()[-1])
    db_session.query(User).update({User.is_active: False})
    db_session.commit()
    assert _verify(client, token).status_code == 400
    assert db_session.query(EmailVerificationToken).one().used_at is None
    assert db_session.query(User).one().email_verified_at is None


def test_verify_rolls_back_token_when_user_update_fails(client, db_session, monkeypatch):
    """Token consumption and the verified flag are one transaction."""
    from app.repositories.email_verification import repository as repo_mod

    _register(client)
    token = _token_from(_outbox()[-1])
    orig = db_session.commit

    def failing_commit():
        raise RuntimeError("simulated DB failure at commit")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError):
        repo_mod.EmailVerificationTokenRepository(db_session).consume_and_verify(
            hash_email_verification_token(token)
        )
    monkeypatch.setattr(db_session, "commit", orig)
    assert db_session.query(EmailVerificationToken).one().used_at is None
    assert db_session.query(User).one().email_verified_at is None
    assert _verify(client, token).status_code == 200  # still redeemable


def test_verify_endpoint_is_rate_limited_per_ip(client):
    codes = [_verify(client, f"bad-{i}").status_code for i in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429


# ---- resend ---------------------------------------------------------------


def test_resend_response_identical_for_known_unknown_verified_and_inactive(client, db_session):
    _register(client, "known@example.com")
    _register(client, "done@example.com")
    _verify(client, _token_from(_outbox()[-1]))
    _register(client, "inactive@example.com")
    db_session.query(User).filter_by(email="inactive@example.com").update({User.is_active: False})
    db_session.commit()
    _age_tokens(db_session, 120)

    responses = [
        _resend(client, e)
        for e in (
            "known@example.com",
            "nobody@example.com",
            "done@example.com",
            "inactive@example.com",
        )
    ]
    assert {r.status_code for r in responses} == {202}
    assert len({r.text for r in responses}) == 1


def test_resend_sends_only_for_active_unverified_account(client, db_session):
    _register(client, "known@example.com")
    _register(client, "done@example.com")
    _verify(client, _token_from(_outbox()[-1]))
    _age_tokens(db_session, 120)
    before = len(_outbox())
    _resend(client, "nobody@example.com")
    _resend(client, "done@example.com")
    assert len(_outbox()) == before
    _resend(client, "known@example.com")
    assert len(_outbox()) == before + 1 and _outbox()[-1].to == "known@example.com"


def test_resend_cooldown_blocks_immediate_second_email_silently(client):
    _register(client)
    assert len(_outbox()) == 1
    r = _resend(client)  # inside the 60s cooldown
    assert r.status_code == 202
    assert len(_outbox()) == 1


def test_resend_hourly_cap_bounds_emails_per_account(client, db_session):
    _register(client)
    for _ in range(10):
        _age_tokens(db_session, 120)  # defeat cooldown, keep within the hour
        assert _resend(client).status_code == 202
        db_session.expire_all()
        # Per-IP limiter would trip first; reset it so the per-account cap is what's tested.
        from app.core.rate_limit import reset_rate_limiter

        reset_rate_limiter()
    assert len(_outbox()) == 5  # settings default: max 5 sends per hour per account


def test_resend_is_rate_limited_per_ip(client):
    codes = [_resend(client, f"x{i}@example.com").status_code for i in range(6)]
    assert codes[:5] == [202] * 5 and codes[5] == 429


def test_resend_delivery_failure_is_contained_and_indistinguishable(
    client, db_session, monkeypatch
):
    _register(client)
    _age_tokens(db_session, 120)
    ok = _resend(client, "nobody@example.com")

    def boom(_m):
        raise TimeoutError("smtp timeout")

    monkeypatch.setattr(get_email_sender(), "send", boom)
    failed = _resend(client)
    assert failed.status_code == 202 and failed.text == ok.text


def test_resend_validates_email_shape(client):
    assert client.post("/api/auth/resend-verification", json={"email": "nope"}).status_code == 422


# ---- account policy -------------------------------------------------------


def test_unverified_user_can_login_see_me_and_browse_but_not_use_gated_features(client):
    _register(client)
    headers = _login_headers(client)
    me = client.get("/api/users/me", headers=headers)
    assert me.status_code == 200 and me.json()["email_verified"] is False
    assert client.get("/api/anime/").status_code == 200  # public catalog
    for method, url, kw in [
        ("get", "/api/favorites/", {}),
        ("post", "/api/favorites/", {"json": {"anime_id": "x"}}),
        ("delete", "/api/favorites/x", {}),
        ("get", "/api/watch/ep/progress", {}),
        ("put", "/api/watch/ep/progress", {"json": {"position_seconds": 1}}),
        ("get", "/api/watch/history", {}),
    ]:
        r = getattr(client, method)(url, headers=headers, **kw)
        assert r.status_code == 403, (method, url)
        assert r.json()["detail"]["code"] == "email_not_verified"


def test_gated_routes_still_401_without_a_token(client):
    assert client.get("/api/favorites/").status_code == 401
    assert client.get("/api/watch/history").status_code == 401


def test_stream_endpoints_stay_public_for_anonymous_and_unverified(client):
    # Not gated: anonymous gets 404 for an unknown episode, never 401/403.
    assert client.get("/api/watch/unknown-episode/stream").status_code == 404


def test_refresh_and_logout_work_for_unverified_user(client):
    _register(client)
    _login_headers(client)
    origin = {"Origin": "http://localhost:5173"}
    assert client.post("/api/auth/refresh", headers=origin).status_code == 200
    assert client.post("/api/auth/logout", headers=origin).status_code == 204


# ---- secrecy --------------------------------------------------------------


def test_raw_token_never_logged_or_returned(client, caplog):
    caplog.set_level(logging.DEBUG)
    reg = client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
    token = _token_from(_outbox()[-1])
    ver = _verify(client, token)
    _verify(client, token)
    _resend(client)
    for text in [reg.text, ver.text]:
        assert token not in text
    assert token not in caplog.text
    assert "verify-email#token" not in caplog.text


def test_delivery_failure_logs_exception_type_only(client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)

    def boom(m):
        raise ConnectionError(f"leaking body: {m.body}")

    monkeypatch.setattr(get_email_sender(), "send", boom)
    client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert "ConnectionError" in caplog.text
    assert "leaking body" not in caplog.text and "#token=" not in caplog.text


# ---- repository.issue_if_allowed (functional; SQLite ignores FOR UPDATE, so this
# proves the decision logic only - row-lock concurrency is covered on MySQL) ----


def _issue(db, user_id, **kw):
    from app.repositories.email_verification import EmailVerificationTokenRepository

    args = dict(ttl=timedelta(hours=1), cooldown_seconds=60, max_per_hour=5)
    args.update(kw)
    return EmailVerificationTokenRepository(db).issue_if_allowed(
        user_id, f"{len(db.query(EmailVerificationToken).all()):064d}", **args
    )


def test_issue_if_allowed_outcomes(client, db_session):
    user_id = _register(client)["id"]
    assert db_session.query(EmailVerificationToken).count() == 1  # registration token
    assert _issue(db_session, user_id) == "cooldown"
    _age_tokens(db_session, 120)
    assert _issue(db_session, user_id) == "issued"
    assert db_session.query(EmailVerificationToken).count() == 2
    for _ in range(3):  # reach the cap of 5 within the hour
        _age_tokens(db_session, 120)
        assert _issue(db_session, user_id) == "issued"
    _age_tokens(db_session, 120)
    assert _issue(db_session, user_id) == "hourly_cap"
    assert db_session.query(EmailVerificationToken).count() == 5


def test_issue_if_allowed_ineligible_users_get_no_token(client, db_session):
    user_id = _register(client)["id"]
    db_session.query(EmailVerificationToken).delete()
    db_session.commit()
    assert _issue(db_session, "no-such-user") == "ineligible"
    db_session.query(User).update({User.is_active: False})
    db_session.commit()
    assert _issue(db_session, user_id) == "ineligible"
    db_session.query(User).update({User.is_active: True, User.email_verified_at: datetime.now(UTC)})
    db_session.commit()
    assert _issue(db_session, user_id) == "ineligible"
    assert db_session.query(EmailVerificationToken).count() == 0
