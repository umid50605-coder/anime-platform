def test_register_then_login_then_me(client):
    register_resp = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "CorrectHorse123", "display_name": "User"},
    )
    assert register_resp.status_code == 201
    user_id = register_resp.json()["id"]

    login_resp = client.post(
        "/api/auth/login",
        data={"username": "user@example.com", "password": "CorrectHorse123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == user_id


def test_duplicate_registration_is_rejected(client):
    payload = {"email": "dupe@example.com", "password": "CorrectHorse123"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


def test_login_with_wrong_password_is_rejected(client):
    client.post(
        "/api/auth/register",
        json={"email": "wrongpw@example.com", "password": "CorrectHorse123"},
    )
    resp = client.post(
        "/api/auth/login",
        data={"username": "wrongpw@example.com", "password": "not-the-password"},
    )
    assert resp.status_code == 401


def test_me_without_token_is_rejected(client):
    resp = client.get("/api/users/me")
    assert resp.status_code == 401
