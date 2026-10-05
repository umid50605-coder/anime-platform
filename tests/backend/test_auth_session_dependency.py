from datetime import UTC, datetime, timedelta

from app.core.security import create_access_token
from app.models.refresh_session import RefreshSession


def _login(client, email: str = "session@example.com") -> tuple[str, str]:
    registration = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "CorrectHorse123",
            "display_name": "Session User",
        },
    )
    assert registration.status_code == 201

    login = client.post(
        "/api/auth/login",
        data={"username": email, "password": "CorrectHorse123"},
    )
    assert login.status_code == 200
    return registration.json()["id"], login.json()["access_token"]


def test_current_user_requires_active_session_family(client, db_session):
    _, access_token = _login(client)
    headers = {"Authorization": f"Bearer {access_token}"}

    assert client.get("/api/users/me", headers=headers).status_code == 200

    refresh_session = db_session.query(RefreshSession).one()
    refresh_session.revoked_at = datetime.now(UTC)
    db_session.commit()

    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_current_user_rejects_expired_session_family(client, db_session):
    user_id, access_token = _login(client)
    headers = {"Authorization": f"Bearer {access_token}"}

    refresh_session = db_session.query(RefreshSession).filter_by(user_id=user_id).one()
    refresh_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_current_user_rejects_access_token_without_session_id(client):
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "no-session@example.com",
            "password": "CorrectHorse123",
            "display_name": "No Session",
        },
    )
    assert registration.status_code == 201
    access_token = create_access_token(subject=registration.json()["id"])

    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401


def test_current_user_rejects_unrecognized_session_id(client):
    user_id, _ = _login(client)
    access_token = create_access_token(subject=user_id, sid="not-an-active-family")

    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401


def test_current_user_rejects_inactive_user_with_existing_access_token(client, db_session):
    from app.models.user import User

    user_id, access_token = _login(client)
    user = db_session.query(User).filter_by(id=user_id).one()
    user.is_active = False
    db_session.commit()

    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401
