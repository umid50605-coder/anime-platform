from app.core.security import hash_refresh_token
from app.models.refresh_session import RefreshSession


def _login(client) -> tuple[str, str]:
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "logout-endpoint@example.com",
            "password": "CorrectHorse123",
            "display_name": "Logout User",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/auth/login",
        data={
            "username": "logout-endpoint@example.com",
            "password": "CorrectHorse123",
        },
    )
    assert login.status_code == 200
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token is not None
    return refresh_token, login.json()["access_token"]


def test_logout_revokes_matching_session_and_clears_cookie(client, db_session):
    original_refresh_token, access_token = _login(client)
    original_session = db_session.query(RefreshSession).filter_by(
        token_hash=hash_refresh_token(original_refresh_token)
    ).one()
    family_id = original_session.family_id
    access_headers = {"Authorization": f"Bearer {access_token}"}
    assert client.get("/api/users/me", headers=access_headers).status_code == 200

    refresh_response = client.post(
        "/api/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
    )
    assert refresh_response.status_code == 200

    rotated_refresh_token = client.cookies.get("refresh_token")
    assert rotated_refresh_token is not None
    rotated_session = db_session.query(RefreshSession).filter_by(
        token_hash=hash_refresh_token(rotated_refresh_token)
    ).one()
    assert rotated_session.family_id == family_id
    headers = {"Origin": "http://localhost:5173"}

    response = client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    family_sessions = db_session.query(RefreshSession).filter_by(family_id=family_id).all()
    assert len(family_sessions) >= 2
    assert all(session.revoked_at is not None for session in family_sessions)
    assert client.get("/api/users/me", headers=access_headers).status_code == 401


def test_logout_without_cookie_is_idempotent_and_clears_cookie(client):
    response = client.post(
        "/api/auth/logout",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_logout_with_invalid_cookie_is_idempotent(client):
    client.cookies.set("refresh_token", "invalid-token", path="/api/auth")

    response = client.post(
        "/api/auth/logout",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_logout_requires_allowed_origin(client):
    response = client.post(
        "/api/auth/logout",
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403


def test_logout_requires_origin_header(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 403
