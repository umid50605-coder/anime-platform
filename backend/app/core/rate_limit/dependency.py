from fastapi import Depends, HTTPException, Request, status

from app.core.logging import get_logger
from app.core.rate_limit.factory import get_rate_limiter
from app.core.rate_limit.limiter import RateLimiter

logger = get_logger(__name__)


def rate_limited(action: str, max_requests: int, window_seconds: float):
    """
    Dependency factory - returns a FastAPI dependency that enforces
    `max_requests` per `window_seconds` per client IP, namespaced by
    `action` (a short label like "register"/"login" - not sensitive, just
    keeps each route's counter independent of the others).

    Usage on a route:
        @router.post(
            "/login",
            dependencies=[Depends(rate_limited("login", max_requests=5, window_seconds=60))],
        )

    Using `dependencies=[...]` (rather than a parameter on the handler
    itself) keeps this out of the route function entirely - the router
    stays thin and never touches the limiter's internals, per
    PROJECT_RULES.md.
    """

    def dependency(
        request: Request,
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        # request.client.host only - no X-Forwarded-For / proxy header
        # handling yet (see the ADR: this app has no trusted-proxy config,
        # so honoring a client-supplied header here would let it be spoofed
        # to bypass the limit entirely).
        client_ip = request.client.host if request.client else "unknown"
        key = f"{action}:{client_ip}"

        allowed, retry_after = limiter.check(key, max_requests, window_seconds)
        if not allowed:
            logger.warning("rate limit exceeded action=%s client_ip=%s", action, client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
