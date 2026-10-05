"""
Tests for TASK 8 (auth rate limiting). See docs/decisions/0004-auth-rate-limiting.md.

Uses the raw InMemoryRateLimiter directly for the algorithm-level tests
(fast, no HTTP/DB overhead - same approach as test_watch_service.py's
fakes), and the real HTTP client for the endpoint-level tests that need to
confirm the actual dependency wiring, headers, and status codes.
"""

from app.core.rate_limit.limiter import InMemoryRateLimiter

# --- Algorithm-level tests (direct against InMemoryRateLimiter) -------------


def test_requests_below_limit_succeed():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        allowed, _ = limiter.check("k", max_requests=5, window_seconds=60)
        assert allowed is True


def test_request_exceeding_limit_is_rejected():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.check("k", max_requests=5, window_seconds=60)

    allowed, retry_after = limiter.check("k", max_requests=5, window_seconds=60)

    assert allowed is False
    assert isinstance(retry_after, int)
    assert 1 <= retry_after <= 60


def test_different_keys_have_independent_limits():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.check("register:1.1.1.1", max_requests=5, window_seconds=60)

    # A different key (different action, or different IP) is untouched.
    allowed, _ = limiter.check("register:2.2.2.2", max_requests=5, window_seconds=60)
    assert allowed is True
    allowed, _ = limiter.check("login:1.1.1.1", max_requests=5, window_seconds=60)
    assert allowed is True


def test_reset_clears_state():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.check("k", max_requests=5, window_seconds=60)
    assert limiter.check("k", max_requests=5, window_seconds=60)[0] is False

    limiter.reset()

    assert limiter.check("k", max_requests=5, window_seconds=60)[0] is True


# --- Endpoint-level tests (real HTTP, via the `client` fixture) -------------


def _register_payload(email: str) -> dict:
    return {"email": email, "password": "CorrectHorse123"}


def test_register_endpoint_enforces_limit_and_returns_retry_after(client):
    for i in range(5):
        resp = client.post("/api/auth/register", json=_register_payload(f"user{i}@example.com"))
        assert resp.status_code == 201

    resp = client.post("/api/auth/register", json=_register_payload("user6@example.com"))

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    retry_after = int(resp.headers["Retry-After"])
    assert 1 <= retry_after <= 60


def test_login_endpoint_enforces_limit_independently_of_register(client):
    # Registering does not consume any of the login limit.
    client.post("/api/auth/register", json=_register_payload("independent@example.com"))

    for _ in range(5):
        resp = client.post(
            "/api/auth/login",
            data={"username": "independent@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 401  # wrong password, but not yet rate-limited

    resp = client.post(
        "/api/auth/login",
        data={"username": "independent@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_register_and_login_limits_are_independent(client):
    """Exhausting /register's limit must not affect /login for the same IP."""
    # Register the account we'll log in with FIRST - once /register's limit
    # is exhausted below, any further registration attempt (for any email)
    # is correctly blocked too, so this one must happen before that point.
    client.post("/api/auth/register", json=_register_payload("login-target@example.com"))

    for i in range(4):
        client.post("/api/auth/register", json=_register_payload(f"sep{i}@example.com"))
    exhausted = client.post("/api/auth/register", json=_register_payload("sep-extra@example.com"))
    assert exhausted.status_code == 429

    login_resp = client.post(
        "/api/auth/login",
        data={"username": "login-target@example.com", "password": "CorrectHorse123"},
    )
    assert login_resp.status_code == 200


def test_different_ips_have_independent_register_limits(client):
    from fastapi.testclient import TestClient

    other_ip_client = TestClient(client.app, client=("9.9.9.9", 12345))

    for i in range(5):
        resp = client.post("/api/auth/register", json=_register_payload(f"ipA{i}@example.com"))
        assert resp.status_code == 201
    exhausted = client.post("/api/auth/register", json=_register_payload("ipA-extra@example.com"))
    assert exhausted.status_code == 429

    # A different simulated client IP is unaffected by the first IP's limit.
    other_resp = other_ip_client.post(
        "/api/auth/register", json=_register_payload("ipB@example.com")
    )
    assert other_resp.status_code == 201


def test_public_catalog_search_watch_endpoints_are_unaffected(client):
    """
    The rate limiter is wired only onto /api/auth/register and
    /api/auth/login (via `dependencies=[...]` on those two routes) - it
    must never fire for public browsing/search/watch, no matter how many
    requests are made.
    """
    for _ in range(10):
        assert client.get("/api/anime/").status_code == 200
        assert client.get("/api/search/?q=neon").status_code == 200
    assert client.get("/health").status_code == 200
