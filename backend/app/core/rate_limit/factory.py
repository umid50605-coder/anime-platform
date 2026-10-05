from functools import lru_cache

from app.core.rate_limit.limiter import InMemoryRateLimiter, RateLimiter


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """
    Returns the configured RateLimiter implementation.

    Only in-memory exists today (no Redis/distributed backend - see the
    ADR). Cached so every dependency injection across the process shares
    one instance's state, the same pattern get_anime_provider/
    get_video_provider use.
    """
    return InMemoryRateLimiter()


def reset_rate_limiter() -> None:
    """
    Test-only: clears the shared limiter's state without discarding the
    cached instance. Production code never calls this - see
    tests/backend/conftest.py's autouse fixture.
    """
    get_rate_limiter().reset()
