def _login(client) -> None:
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "refresh-endpoint@example.com",
            "password": "CorrectHorse123",
            "display_name": "Refresh User",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/auth/login",
        data={
            "username": "refresh-endpoint@example.com",
            "password": "CorrectHorse123",
        },
    )
    assert login.status_code == 200


def test_refresh_endpoint_rotates_cookie_and_returns_only_access_token(client):
    _login(client)
    original_refresh_token = client.cookies.get("refresh_token")

    response = client.post(
        "/api/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["access_token"]
    assert response.cookies.get("refresh_token") != original_refresh_token
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "path=/api/auth" in response.headers["set-cookie"].lower()


def test_refresh_endpoint_clears_cookie_and_returns_401_for_invalid_token(client):
    client.cookies.set("refresh_token", "invalid-token", path="/api/auth")

    response = client.post(
        "/api/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 401
    assert response.headers["set-cookie"].startswith("refresh_token=")
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_refresh_endpoint_clears_missing_cookie_and_returns_401(client):
    response = client.post(
        "/api/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 401
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_refresh_endpoint_requires_allowed_origin(client):
    response = client.post(
        "/api/auth/refresh",
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403


def test_refresh_endpoint_requires_origin_header(client):
    response = client.post("/api/auth/refresh")

    assert response.status_code == 403


def test_refresh_endpoint_enforces_rate_limit(client):
    _login(client)
    headers = {"Origin": "http://localhost:5173"}

    for _ in range(5):
        assert client.post("/api/auth/refresh", headers=headers).status_code == 200

    response = client.post("/api/auth/refresh", headers=headers)

    assert response.status_code == 429
    assert "Retry-After" in response.headers
